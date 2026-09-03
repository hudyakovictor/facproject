#!/usr/bin/env python3
"""
Переизвлечение калибровочного датасета через актуальный Stage 1 pipeline.

Проблема: оригинальные фото в calibration_dataset/photos/ имеют имена
frame_000205.jpg, не содержащие даты. Stage 1 требует формат YYYY_MM_DD[_N].

Решение: скрипт создаёт временную структуру с симлинками, где каждому кадру
назначается synthetic date на основе (dataset_id, frame_index), запускает Stage 1,
а затем организует вывод в иерархическую структуру:

  calibration_dataset_new/
    person_01/
      frame_000205/
        info.json
        ldm106_raw.csv
        ldm106_chronology.csv
        ldm134_raw.csv
        ldm134_chronology.csv
        reconstruction.npz
        ...

Использование:
  /Users/victorkhudyakov/work/.venv/bin/python app6/run_calibration_re_extract.py
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from pathlib import Path

# ── путь к проекту ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

PYTHON = "/Users/victorkhudyakov/work/.venv/bin/python"

# ── константы ───────────────────────────────────────────────────────────
DEFAULT_INPUT_PHOTOS = ROOT / "calibration_dataset" / "photos"
DEFAULT_INDEX = ROOT / "calibration_dataset" / "all_calibration_index.csv"
DEFAULT_OUTPUT = Path("/Volumes/SDCARD/storage/calibration_dataset_new")

# Стартовая synthetic date (ISO). Каждый следующий кадр личности +1 день.
# Это сохраняет хронологический порядок внутри person, не претендуя на реальную дату.
BASE_DATE = "1999-01-11"

# Временная директория для symlink'ов — на SDCARD чтобы не забивать корневой диск
SYMLINK_TMP = Path("/Volumes/SDCARD/storage/_symlinks_for_stage1")
# Временный вывод Stage 1 — туда же
STAGE1_TMP = Path("/Volumes/SDCARD/storage/_stage1_output")

# ── функции ─────────────────────────────────────────────────────────────
def load_index(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def assign_synthetic_dates(rows: list[dict[str, str]]) -> dict[str, str]:
    """photo_id → synthetic ISO date, сохраняя порядок внутри dataset_id."""
    from datetime import date, timedelta

    by_person: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        by_person.setdefault(r["dataset_id"], []).append(r)

    assigned: dict[str, str] = {}
    base = date.fromisoformat(BASE_DATE)
    pid = 1
    for _, frames in sorted(by_person.items()):
        frames.sort(key=lambda x: int(x["frame_index"]))
        # Каждой персоне — своя эпоха, внутри — порядковый день.
        for fi, frame in enumerate(frames):
            d = base + timedelta(days=(pid * 1000) + fi)
            assigned[frame["record_id"]] = d.isoformat()
        pid += 1
    return assigned


def create_temp_symlinks(
    photos_root: Path,
    rows: list[dict[str, str]],
    date_map: dict[str, str],
    symlink_dir: Path,
) -> Path:
    """Создать директорию с симлинками вида YYYY_MM_DD__person_frame.jpg."""
    tmp = symlink_dir
    tmp.mkdir(parents=True, exist_ok=True)
    # Очищаем предыдущие symlink'и
    for f in tmp.iterdir():
        f.unlink()
    for r in rows:
        src = photos_root / r["dataset_id"] / r["source_filename"]
        if not src.is_file():
            print(f"  ⚠ пропущен {r['source_filename']}: файл не найден")
            continue
        iso_date = date_map.get(r["record_id"], BASE_DATE)
        # формат: YYYY_MM_DD__person_XX_frame_000205.jpg
        stem = f"{iso_date.replace('-', '_')}__{r['dataset_id']}_{r['record_id']}"
        link_name = tmp / f"{stem}{src.suffix}"
        link_name.symlink_to(src.resolve())
    return tmp


def run_stage1(input_dir: Path, output_dir: Path) -> None:
    """Запустить Stage 1 pipeline через subprocess."""
    import subprocess

    cmd = [
        PYTHON, "app6/run_calibration.py",
        "--input", str(input_dir),
        "--output", str(output_dir),
    ]
    print(f"\n{'='*70}")
    print(f"Запуск Stage 1: {' '.join(cmd)}")
    print(f"{'='*70}\n")
    result = subprocess.run(cmd, cwd=ROOT)  # noqa: S603 — фиксированный внутренний не-shell вызов, без untrusted input
    if result.returncode != 0:
        print(f"\n❌ Stage 1 завершился с кодом {result.returncode}")
        sys.exit(result.returncode)
    print("\n✅ Stage 1 завершён")


def reorganize_output(
    stage1_output: Path,
    rows: list[dict[str, str]],
    final_output: Path,
) -> None:
    """Переложить Stage 1 вывод в иерархическую структуру.

    Stage 1 создаёт: output_dir/YYYY_MM_DD[_]person_XX_frame_000205__hash12/
                    (нормализует __ в _ между датой и person)
    Нам нужно:     calibration_dataset_new/person_XX/frame_000205/
    """
    import re

    print(f"\n{'='*70}")
    print("Реорганизация вывода в иерархическую структуру...")
    print(f"{'='*70}\n")

    final_output.mkdir(parents=True, exist_ok=True)

    # Собираем маппинг: record_id → (dataset_id, frame_index)
    record_map: dict[str, tuple[str, str]] = {}
    for r in rows:
        record_map[r["record_id"]] = (r["dataset_id"], r["record_id"])

    moved = 0
    skipped = 0
    for src_dir in sorted(stage1_output.iterdir()):
        if not src_dir.is_dir() or src_dir.name.startswith("_"):
            continue
        # Извлекаем person_id и frame_id из имени директории Stage 1.
        # Stage 1 нормализует __ → _, поэтому имена выглядят так:
        #   2004_11_20_person_01_frame_000253__cbbcee98aff5
        # Ищем паттерн person_XX_frame_XXXXXX через regex (устойчиво к формату).
        m = re.search(r'(person_\d+)_(frame_\d+)', src_dir.name)
        if not m:
            skipped += 1
            continue
        person_id = m.group(1)  # person_01
        frame_id = m.group(2)   # frame_000205

        dest = final_output / person_id / frame_id
        dest.mkdir(parents=True, exist_ok=True)

        # Копируем все файлы (кроме изображений — original, thumb, face_crop)
        for f in src_dir.iterdir():
            if f.is_file():
                # Пропускаем большие изображения и UV-текстуру
                if f.name in ("original.jpg", "original.jpeg", "original.png",
                              "thumb.jpg", "face_crop.jpg"):
                    continue
                shutil.copy2(f, dest / f.name)

        moved += 1
        print(f"  ✓ {person_id}/{frame_id} ({moved})")

    print(f"\n✅ Перенесено: {moved}, пропущено: {skipped}")


def main():
    parser = argparse.ArgumentParser(description="Переизвлечение калибровочного датасета")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PHOTOS,
                        help="каталог с сырыми фото (calibration_dataset/photos)")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX,
                        help="путь к all_calibration_index.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="каталог для нового вывода")
    parser.add_argument("--skip-stage1", action="store_true",
                        help="пропустить Stage 1 (если уже запущен)")
    args = parser.parse_args()

    input_photos = args.input.resolve()
    index_path = args.index.resolve()
    output_dir = args.output.resolve()
    symlink_dir = SYMLINK_TMP
    stage1_tmp = STAGE1_TMP

    print(f"📸 Входные фото: {input_photos}")
    print(f"📇 Индекс: {index_path}")
    print(f"📦 Выход: {output_dir}")

    # 1. Загружаем индекс
    rows = load_index(index_path)
    print(f"\nЗаписей в индексе: {len(rows)}")

    # 2. Назначаем synthetic dates
    date_map = assign_synthetic_dates(rows)
    print(f"Назначено synthetic dates: {len(date_map)}")

    # 3. Создаём symlink директорию
    if not args.skip_stage1:
        symlink_dir = create_temp_symlinks(input_photos, rows, date_map, symlink_dir)
        print(f"\nСозданы symlink'и в: {symlink_dir}")
        n_links = len(list(symlink_dir.iterdir()))
        print(f"  Всего ссылок: {n_links}")

        # 4. Запускаем Stage 1
        if stage1_tmp.exists():
            print(f"  🧹 Очищаем предыдущий временный вывод: {stage1_tmp}")
            shutil.rmtree(stage1_tmp)
        run_stage1(symlink_dir, stage1_tmp)

        # 5. Symlink'и пока оставляем (на SDCARD место есть)
    else:
        print("\n⏭ Stage 1 пропущен (--skip-stage1)")

    # 6. Реорганизуем вывод
    if stage1_tmp.exists():
        if output_dir.exists():
            print(f"  🧹 Очищаем предыдущий вывод: {output_dir}")
            shutil.rmtree(output_dir)
        reorganize_output(stage1_tmp, rows, output_dir)

        print(f"\n{'='*70}")
        print(f"✅ Готово! Результат: {output_dir}")
        print(f"{'='*70}")
    else:
        print(f"\n❌ Временный вывод Stage 1 не найден: {stage1_tmp}")


if __name__ == "__main__":
    main()
