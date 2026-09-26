"""🚀 Главный движок Stage 1 (app8): хронологическая сортировка и пакетная обработка.

Обрабатывает входную директорию с фотографиями, извлекает хронологические даты,
сортирует кадры во времени, выполняет 3D-реконструкцию и сохраняет
бинарные записи без избыточных файлов.
"""
from __future__ import annotations
import json, re, time
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from .config import Stage1Config, IMAGE_EXTENSIONS, SCHEMA_VERSION, POSE_BINS
from .reconstruction import reconstruct_image
from .storage import save_stage1_record

_DATE_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?P<y>19\d{2}|20\d{2})[_-](?P<m>\d{1,2})[_-](?P<d>\d{1,2})(?!\d)")


def parse_date(path: Path) -> str:
    """Извлекает дату YYYY-MM-DD из имени файла или возвращает пустую строку."""
    m = _DATE_PATTERN.search(path.stem)
    if m:
        try:
            d = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
            return d.isoformat()
        except ValueError:
            pass
    return ""


def run_stage1(config: Stage1Config) -> dict[str, Any]:
    """Выполняет Stage 1 пайплайн на входной директории."""
    input_dir = Path(config.input_dir).resolve()
    output_dir = Path(config.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Поиск изображений (пропускаем AppleDouble ._* и служебные файлы)
    raw_imgs = [
        p for p in input_dir.glob("*")
        if p.suffix.lower() in IMAGE_EXTENSIONS
        and not p.name.startswith("._")
        and p.name != ".DS_Store"
    ]
    if not raw_imgs:
        raw_imgs = [
            p for p in input_dir.rglob("*")
            if p.suffix.lower() in IMAGE_EXTENSIONS
            and not p.name.startswith("._")
            and p.name != ".DS_Store"
        ]
        
    print(f"[app8 Stage 1] Found {len(raw_imgs)} images in {input_dir}")
    
    # 2. Хронологическая сортировка (дата из имени, затем имя файла)
    parsed_items = []
    for img in raw_imgs:
        d_iso = parse_date(img)
        parsed_items.append((d_iso, img.stem, img))
        
    # Сортировка: сначала с датами по возрастанию, затем без дат по алфавиту
    parsed_items.sort(key=lambda x: (x[0] == "", x[0], x[1]))
    
    if config.limit > 0:
        parsed_items = parsed_items[:config.limit]
        
    # 3. Пакетная обработка
    t0 = time.time()
    manifest_records = []
    pose_bin_counts = {}
    success_count = 0
    fail_count = 0
    
    for idx, (d_iso, stem, img_path) in enumerate(parsed_items, start=1):
        # Быстрая проверка кэша до тяжелого инференса (resume).
        # С --group-by-pose ищем stem в любой подпапке бина позы, иначе — в корне.
        # Без --overwrite пропускаем уже готовые reconstruction.npz и подтягиваем
        # запись в манифест из сохранённого info.json.
        if not config.overwrite:
            cached_info = None
            is_cached = False
            if config.group_by_pose:
                for bin_name, _, _, _ in POSE_BINS:
                    cand_npz = output_dir / bin_name / stem / "reconstruction.npz"
                    cand_info = output_dir / bin_name / stem / "info.json"
                    if cand_npz.exists():
                        is_cached = True
                        if cand_info.exists():
                            try:
                                with open(cand_info, encoding="utf-8") as _f:
                                    cached_info = json.load(_f)
                            except Exception:
                                cached_info = None
                        break
                # legacy-раскладка без группировки (на случай смешанного вывода)
                if not is_cached and (output_dir / stem / "reconstruction.npz").exists():
                    is_cached = True
                    cand_info = output_dir / stem / "info.json"
                    if cand_info.exists():
                        try:
                            with open(cand_info, encoding="utf-8") as _f:
                                cached_info = json.load(_f)
                        except Exception:
                            cached_info = None
            else:
                target_dir = output_dir / stem
                if (target_dir / "reconstruction.npz").exists():
                    is_cached = True
                    cand_info = target_dir / "info.json"
                    if cand_info.exists():
                        try:
                            with open(cand_info, encoding="utf-8") as _f:
                                cached_info = json.load(_f)
                        except Exception:
                            cached_info = None
            if is_cached:
                print(f"  [{idx}/{len(parsed_items)}] Cached: {stem}")
                success_count += 1
                if cached_info is not None:
                    try:
                        pose = cached_info.get("pose", {})
                        p_bin_cached = str(pose.get("pose_bin", "unknown"))
                        pose_bin_counts[p_bin_cached] = pose_bin_counts.get(p_bin_cached, 0) + 1
                        out_rel = next(
                            (str((output_dir / b / stem).relative_to(output_dir))
                             for b, _, _, _ in POSE_BINS
                             if (output_dir / b / stem / "reconstruction.npz").exists()),
                            stem,
                        ) if config.group_by_pose else stem
                        manifest_records.append({
                            "photo_id": stem,
                            "date_iso": str(cached_info.get("date_iso", d_iso)),
                            "pose_bin": p_bin_cached,
                            "canonical_yaw": float(pose.get("canonical_yaw", 0.0)),
                            "yaw_deg": float(pose.get("yaw_deg", 0.0)),
                            "pitch_deg": float(pose.get("pitch_deg", 0.0)),
                            "roll_deg": float(pose.get("roll_deg", 0.0)),
                            "is_smiling": bool(cached_info.get("expression_qc", {}).get("is_smiling", False)),
                            "is_mouth_open": bool(cached_info.get("expression_qc", {}).get("is_mouth_open", False)),
                            "output_dir": out_rel,
                        })
                    except Exception:
                        pass
                continue
            
        print(f"  [{idx}/{len(parsed_items)}] Processing: {stem} (date: {d_iso or 'none'})...")
        try:
            res = reconstruct_image(img_path, device=config.device)
            if res is None:
                print(f"    NOFACE: {stem}")
                fail_count += 1
                continue
                
            p_bin = res["pose_bin"]
            pose_bin_counts[p_bin] = pose_bin_counts.get(p_bin, 0) + 1
            
            if config.group_by_pose:
                photo_dir = output_dir / p_bin / stem
            else:
                photo_dir = output_dir / stem
                
            res["date_iso"] = d_iso
            saved_files = save_stage1_record(photo_dir, stem, res)
            
            # Генерация визуальных, текстурных и 3D-ассетов (только если запрошено)
            # Пиксели берите тем же декодом, что и реконструкция (EXIF transpose),
            # иначе маска, UV и метрики считаются по другому изображению.
            from .imaging import decode_oriented_bgr
            try:
                bgr = decode_oriented_bgr(img_path)
            except Exception as dec_exc:
                bgr = None
                print(f"    DECODE: {stem} — {dec_exc}")
            if bgr is not None:
                from .assets import save_image_previews, save_uv_texture_and_3d_mesh, build_skin_texture
                
                # 1. Оригинал, Face Crop и Превью
                if config.save_original:
                    v2d = res.get("vertices_2d_orig")
                    bbox = None
                    if v2d is not None and len(v2d) > 0:
                        min_xy = np.min(v2d, axis=0)
                        max_xy = np.max(v2d, axis=0)
                        bw, bh = max_xy[0] - min_xy[0], max_xy[1] - min_xy[1]
                        margin_w, margin_h = bw * 0.15, bh * 0.15
                        bbox = [int(min_xy[0] - margin_w), int(min_xy[1] - margin_h), int(bw + 2 * margin_w), int(bh + 2 * margin_h)]
                    img_files = save_image_previews(img_path, bgr, bbox, photo_dir, save_original=True)
                    saved_files.update(img_files)
                    
                # 2. UV-Развертка текстуры и 3D Mesh (.obj + .mtl)
                if config.save_mesh:
                    uv_files = save_uv_texture_and_3d_mesh(bgr, res, photo_dir, uv_size=512, save_mesh=True)
                    saved_files.update(uv_files)
                    
                # 3. Текстурный анализ кожи — контракт app6: семантическая маска кожи +
                #    те же функции app6.stage1 (quality `q_*` + v12-панель, texture-v1).
                try:
                    skin_summary = build_skin_texture(bgr, res, photo_dir, photo_id=stem)
                    saved_files.update(skin_summary.get("files") or {})
                except Exception as skin_exc:
                    with open(photo_dir / "skin_failure.json", "w", encoding="utf-8") as sf:
                        json.dump({"state": "failed_retryable", "error": str(skin_exc),
                                   "source": "face_mask.png"}, sf, indent=2, ensure_ascii=False)
                    saved_files["skin_failure"] = "skin_failure.json"
                    print(f"    SKIN: {stem} — {skin_exc}")
                
            success_count += 1
            
            manifest_records.append({
                "photo_id": stem,
                "date_iso": d_iso,
                "pose_bin": p_bin,
                "canonical_yaw": float(res["canonical_yaw"]),
                "yaw_deg": float(res["angles_deg"][1]),
                "pitch_deg": float(res["angles_deg"][0]),
                "roll_deg": float(res["angles_deg"][2]),
                "is_smiling": bool(res["expression_qc"].get("is_smiling", False)),
                "is_mouth_open": bool(res["expression_qc"].get("is_mouth_open", False)),
                "output_dir": str(photo_dir.relative_to(output_dir)),
            })
            
        except Exception as exc:
            print(f"    ERROR on {stem}: {exc}")
            fail_count += 1
            if not config.continue_on_error:
                raise
                
    elapsed = time.time() - t0
    fps = success_count / max(elapsed, 1e-3)
    
    # 4. Итоговый манифест выполнения
    manifest = {
        "schema": SCHEMA_VERSION,
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total_images": len(parsed_items),
        "processed_success": success_count,
        "processed_failed": fail_count,
        "elapsed_seconds": round(elapsed, 2),
        "processing_fps": round(fps, 2),
        "pose_bin_distribution": pose_bin_counts,
        "chronological_records": manifest_records,
    }
    
    manifest_path = output_dir / "stage1_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        
    print(f"\n[app8 Stage 1 Complete] Success: {success_count}/{len(parsed_items)}, Elapsed: {elapsed:.1f}s ({fps:.1f} fps)")
    print(f"Manifest written to {manifest_path}")
    return manifest
