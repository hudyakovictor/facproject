"""📅 Модуль группировки по ракурсам и хронологического анализа (app8).

Предоставляет функции для автоматической группировки фотографий по 9 бинам ракурсов
(POSE_BINS) и построения временных рядов (хронологии) внутри каждого ракурса.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .reader import load_record, App8Record, get_ldm134


def load_chronology_dataset(stage1_output_dir: str | Path) -> dict[str, list[App8Record]]:
    """Сканирует результаты Stage 1 и группирует записи по корзинам ракурсов (pose bins).
    
    Каждая корзина отсортирована строго во времени по дате (date_iso).
    
    Возвращает:
        dict: {
            "frontal": [rec1 (1999), rec2 (2000), rec3 (2004)...],
            "left_mid": [recA (1999), recB (2001)...],
            "right_profile": [...],
            ...
        }
    """
    out_dir = Path(stage1_output_dir).resolve()
    manifest_file = out_dir / "stage1_manifest.json"
    
    records_by_bin: dict[str, list[App8Record]] = {}
    
    # Ищем все файлы reconstruction.npz рекурсивно (поддерживает и плоскую, и вложенную структуру)
    npz_files = sorted(out_dir.rglob("reconstruction.npz"))
    
    # Загружаем все записи
    all_recs = []
    for npz_p in npz_files:
        try:
            rec = load_record(npz_p)
            all_recs.append(rec)
        except Exception as e:
            print(f"Warning: could not load {npz_p}: {e}")
            
    # Сортировка всех записей по дате (хронологии)
    all_recs.sort(key=lambda r: (r.date_iso == "", r.date_iso, r.photo_id))
    
    # Группировка по корзинам ракурсов
    for r in all_recs:
        p_bin = r.pose_bin
        if p_bin not in records_by_bin:
            records_by_bin[p_bin] = []
        records_by_bin[p_bin].append(r)
        
    return records_by_bin


def print_chronology_summary(records_by_bin: dict[str, list[App8Record]]) -> None:
    """Выводит наглядную сводку хронологии по всем ракурсам."""
    print("\n" + "=" * 70)
    print("📊 СВОДКА ХРОНОЛОГИИ ПО ГРУППАМ РАКУРСОВ (POSE BINS)")
    print("=" * 70)
    
    for bin_name, recs in sorted(records_by_bin.items()):
        dates = [r.date_iso or r.photo_id for r in recs]
        date_range = f"{dates[0]} → {dates[-1]}" if len(dates) > 1 else (dates[0] if dates else "нет")
        print(f"\n🏷️  Ракурс: [{bin_name.upper()}] (Канонический yaw: {recs[0].canonical_yaw:+.1f}°)")
        print(f"   • Количество кадров: {len(recs)}")
        print(f"   • Временной диапазон: {date_range}")
        print("   • Список кадров по хронологии:")
        for idx, r in enumerate(recs, start=1):
            y = r.angles_deg[1]
            p = r.angles_deg[0]
            print(f"      {idx:02d}. [{r.date_iso or 'БЕЗ ДАТЫ':10s}] {r.photo_id:30s} (yaw={y:+.1f}°, pitch={p:+.1f}°)")
    print("=" * 70 + "\n")
