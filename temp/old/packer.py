"""📦 Модуль упаковки и агрегации 9 ракурсов (app8 Packer).

Объединяет хронологические данные Stage 1 в 9 компактных пакетов по ракурсам БЕЗ тяжелых 3D-моделей:
- landmarks_106_chronology.csv — координаты 106 канонических точек лица (контур, глаза, брови, нос, губы);
- landmarks_134_chronology.csv — координаты 134 точек (+28 краниометрических ориентиров черепа/ушей);
- skin_texture_chronology.csv  — динамика параметров текстуры кожи (схема texture-v1:
  quality `q_*` + v12-панель аутентичности, тот же набор, что и в app6);
- timeline_summary.txt         — текстовый хронологический паспорт ракурса;
- info.json                    — машиночитаемые метаданные;
- <bin_name>.npz              — компактный бинарный архив точек (106, 134), коэффициентов ID/EXP и текстуры.
"""
from __future__ import annotations
import csv, json
from pathlib import Path
from typing import Any
import numpy as np

from .config import POSE_BINS, SCHEMA_VERSION
from .reader import load_record, get_ldm134, get_ldm106, App8Record
from .chronology import load_chronology_dataset

# Секции/ключи texture-v1, не являющиеся метриками (константные разделы модели и provenance)
_TEX_SKIP_KEYS = frozenset({
    "source", "model", "rule", "thresholds", "decision_rule", "aggregation",
    "libraries", "interpretation", "semantics", "schema", "photo_id",
})


def flatten_texture(tex_data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Разворачивает вложенный `texture.json` (schema texture-v1) в плоские скалярные колонки.

    Плоский legacy-формат (словарь скаляров) проходит через ту же функцию без изменений,
    поэтому старые выходы Stage 1 остаются читаемыми.
    """
    flat: dict[str, Any] = {}
    for key, value in tex_data.items():
        if key in _TEX_SKIP_KEYS:
            continue
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten_texture(value, prefix=f"{name}."))
        elif isinstance(value, bool):
            flat[name] = int(value)
        elif isinstance(value, int | float | str):
            flat[name] = value
    return flat


def pack_pose_bins(stage1_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Агрегирует результаты Stage 1 в 9 унифицированных пакетов ракурсов без тяжелых 3D сеток."""
    stage1_path = Path(stage1_dir).resolve()
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    
    records_by_bin = load_chronology_dataset(stage1_path)
    summary_report: dict[str, Any] = {
        "schema": "deeputin-app8-packed-9bins-v1.0",
        "source_stage1_dir": str(stage1_path),
        "total_bins": len(POSE_BINS),
        "active_bins_count": len([b for b, r in records_by_bin.items() if len(r) > 0]),
        "packed_bins": {},
    }
    
    for bin_tuple in POSE_BINS:
        bin_name = bin_tuple[0]
        canonical_yaw = bin_tuple[3]
        recs = records_by_bin.get(bin_name, [])
        bin_dir = out_path / bin_name
        bin_dir.mkdir(parents=True, exist_ok=True)
        
        if not recs:
            empty_info = {
                "bin_name": bin_name,
                "canonical_yaw": canonical_yaw,
                "status": "empty_no_photos",
                "frame_count": 0,
            }
            with open(bin_dir / "info.json", "w", encoding="utf-8") as f:
                json.dump(empty_info, f, indent=2)
            (bin_dir / "timeline_summary.txt").write_text(
                f"Ракурс {bin_name.upper()} (канонический yaw: {canonical_yaw:+.1f}°): фото отсутствуют.\n",
                encoding="utf-8"
            )
            continue
            
        print(f"[app8 Packer] Packing [{bin_name.upper()}] with {len(recs)} chronological frames (landmarks & texture only)...")
        
        # Сортировка записей строго во времени
        recs.sort(key=lambda r: (r.date_iso == "", r.date_iso, r.photo_id))
        
        n_frames = len(recs)
        photo_ids = [r.photo_id for r in recs]
        dates_iso = [r.date_iso for r in recs]
        
        angles_deg = np.stack([r.angles_deg for r in recs], axis=0)                # (N, 3)
        alpha_id = np.stack([r.alpha_id for r in recs], axis=0)                    # (N, 80)
        alpha_exp = np.stack([r.alpha_exp for r in recs], axis=0)                  # (N, 64)
        
        # Извлечение 134 и 106 ключевых точек
        ldm134_chrono = np.stack([get_ldm134(r, "chronology") for r in recs], axis=0) # (N, 134, 3)
        ldm106_chrono = np.stack([get_ldm106(r, "chronology") for r in recs], axis=0) # (N, 106, 3)
        
        ldm134_idx = recs[0].ldm134_indices
        ldm106_idx = recs[0].ldm106_indices
        
        # Уверенности для ключевых точек
        conf_134 = np.stack([r.vertex_confidence[ldm134_idx] for r in recs], axis=0) # (N, 134)
        conf_106 = np.stack([r.vertex_confidence[ldm106_idx] for r in recs], axis=0) # (N, 106)
        
        # Чтение текстурных метрик (берём ВСЕ скалярные ключи texture.json динамически;
        # вложенная схема texture-v1 разворачивается в колонки вида "quality.q_noise_mad")
        skin_rows = []
        tex_keys: list[str] = []
        for f_idx, r in enumerate(recs):
            photo_src_dir = stage1_path / r.photo_id
            if not photo_src_dir.exists():
                photo_src_dir = stage1_path / bin_name / r.photo_id
            tex_json_path = photo_src_dir / "texture.json"

            tex_data = {}
            if tex_json_path.is_file():
                try:
                    with open(tex_json_path, encoding="utf-8") as tf:
                        raw_tex = json.load(tf)
                    if isinstance(raw_tex, dict):
                        tex_data = flatten_texture(raw_tex)
                except Exception:
                    tex_data = {}

            for k in tex_data:
                if k not in tex_keys:
                    tex_keys.append(k)

            row = {
                "frame_idx": f_idx + 1,
                "photo_id": r.photo_id,
                "date_iso": r.date_iso or "none",
                "yaw_deg": round(float(r.angles_deg[1]), 2),
                "pitch_deg": round(float(r.angles_deg[0]), 2),
            }
            row.update(tex_data)
            skin_rows.append(row)

        # 1. КОМПАКТНЫЙ NPZ РАКУРСА (БЕЗ 35k СЕТОК - только точки 106/134, коэффициенты и уверенности)
        npz_path = bin_dir / f"{bin_name}.npz"
        np.savez_compressed(
            npz_path,
            bin_name=np.asarray(bin_name),
            canonical_yaw=np.asarray([canonical_yaw], np.float32),
            photo_ids=np.asarray(photo_ids),
            dates_iso=np.asarray(dates_iso),
            angles_deg=angles_deg.astype(np.float32),
            alpha_id=alpha_id.astype(np.float32),
            alpha_exp=alpha_exp.astype(np.float32),
            ldm106_chronology=ldm106_chrono.astype(np.float32),
            ldm134_chronology=ldm134_chrono.astype(np.float32),
            ldm106_confidence=conf_106.astype(np.float32),
            ldm134_confidence=conf_134.astype(np.float32),
            ldm106_indices=ldm106_idx.astype(np.int64),
            ldm134_indices=ldm134_idx.astype(np.int64),
        )
        
        # 2. ТАБЛИЧНЫЙ CSV: 106 КАНОНИЧЕСКИХ ТОЧЕК
        csv_106_path = bin_dir / "landmarks_106_chronology.csv"
        with open(csv_106_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["frame_idx", "photo_id", "date_iso", "yaw_deg", "pitch_deg", "landmark_idx", "x_chrono", "y_chrono", "z_chrono", "confidence"])
            for f_idx, r in enumerate(recs):
                l_pts = ldm106_chrono[f_idx]
                c_pts = conf_106[f_idx]
                for l_idx in range(106):
                    writer.writerow([
                        f_idx + 1,
                        r.photo_id,
                        r.date_iso or "none",
                        f"{r.angles_deg[1]:.2f}",
                        f"{r.angles_deg[0]:.2f}",
                        l_idx,
                        f"{l_pts[l_idx, 0]:.6f}",
                        f"{l_pts[l_idx, 1]:.6f}",
                        f"{l_pts[l_idx, 2]:.6f}",
                        f"{c_pts[l_idx]:.3f}",
                    ])

        # 3. ТАБЛИЧНЫЙ CSV: 134 РАСШИРЕННЫХ ТОЧЕК (+28 КРАНИОМЕТРИЧЕСКИХ)
        csv_134_path = bin_dir / "landmarks_134_chronology.csv"
        with open(csv_134_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["frame_idx", "photo_id", "date_iso", "yaw_deg", "pitch_deg", "landmark_idx", "x_chrono", "y_chrono", "z_chrono", "confidence"])
            for f_idx, r in enumerate(recs):
                l_pts = ldm134_chrono[f_idx]
                c_pts = conf_134[f_idx]
                for l_idx in range(134):
                    writer.writerow([
                        f_idx + 1,
                        r.photo_id,
                        r.date_iso or "none",
                        f"{r.angles_deg[1]:.2f}",
                        f"{r.angles_deg[0]:.2f}",
                        l_idx,
                        f"{l_pts[l_idx, 0]:.6f}",
                        f"{l_pts[l_idx, 1]:.6f}",
                        f"{l_pts[l_idx, 2]:.6f}",
                        f"{c_pts[l_idx]:.3f}",
                    ])
                    
        # 4. ТАБЛИЧНЫЙ CSV: ХРОНОЛОГИЯ ТЕКСТУРЫ КОЖИ
        csv_skin_path = bin_dir / "skin_texture_chronology.csv"
        with open(csv_skin_path, "w", newline="", encoding="utf-8") as f:
            if skin_rows:
                base_keys = ["frame_idx", "photo_id", "date_iso", "yaw_deg", "pitch_deg"]
                fieldnames = base_keys + [k for k in tex_keys if k not in base_keys]
                writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
                writer.writeheader()
                writer.writerows(skin_rows)
                
        # 5. ТЕКСТОВЫЙ ПАСПОРТ РАКУРСА (TIMELINE_SUMMARY.TXT)
        txt_path = bin_dir / "timeline_summary.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write(f"ХРОНОЛОГИЧЕСКИЙ ПАСПОРТ РАКУРСА: [{bin_name.upper()}]\n")
            f.write(f"Канонический угол Yaw: {canonical_yaw:+.1f}° | Всего кадров: {n_frames}\n")
            dates_str = f"{dates_iso[0] or photo_ids[0]} → {dates_iso[-1] or photo_ids[-1]}"
            f.write(f"Временной охват: {dates_str}\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"{'№':<3} | {'Дата':<10} | {'Photo ID':<25} | {'Yaw (факт)':<10} | {'Pitch':<8}\n")
            f.write("-" * 70 + "\n")
            for idx, r in enumerate(recs, 1):
                f.write(f"{idx:02d}  | {r.date_iso or 'БЕЗ ДАТЫ':<10} | {r.photo_id:<25} | {r.angles_deg[1]:+6.1f}°     | {r.angles_deg[0]:+5.1f}°\n")
            f.write("-" * 70 + "\n")
            f.write(f"\nСодержимое пакета ракурса (только точки и текстура):\n")
            f.write(f"  • {bin_name}.npz                 — Компактный архив (106 и 134 точки, ID/EXP векторы)\n")
            f.write(f"  • landmarks_106_chronology.csv  — Канонические 106 точек лица по времени\n")
            f.write(f"  • landmarks_134_chronology.csv  — 134 точки (+28 краниометрических ориентиров)\n")
            f.write(f"  • skin_texture_chronology.csv   — Динамика метрик кожи (texture-v1: quality + v12-панель)\n")
            f.write(f"  • info.json                     — Метаданные ракурса\n")
            
        # 6. JSON МЕТАДАННЫЕ РАКУРСА
        info_json_path = bin_dir / "info.json"
        bin_info = {
            "bin_name": bin_name,
            "canonical_yaw": canonical_yaw,
            "frame_count": n_frames,
            "date_range": [dates_iso[0], dates_iso[-1]],
            "photo_ids": photo_ids,
            "files": {
                "unified_npz": f"{bin_name}.npz",
                "landmarks_106_csv": "landmarks_106_chronology.csv",
                "landmarks_134_csv": "landmarks_134_chronology.csv",
                "skin_texture_csv": "skin_texture_chronology.csv",
                "summary_txt": "timeline_summary.txt",
                "info_json": "info.json",
            }
        }
        with open(info_json_path, "w", encoding="utf-8") as f:
            json.dump(bin_info, f, indent=2, ensure_ascii=False)
            
        summary_report["packed_bins"][bin_name] = bin_info
        
    # Итоговый манифест всех 9 ракурсов
    with open(out_path / "packed_manifest.json", "w", encoding="utf-8") as f:
        json.dump(summary_report, f, indent=2, ensure_ascii=False)
        
    print(f"\n[app8 Packer Complete] Successfully packaged 9 canonical pose bins into {out_path}")
    return summary_report
