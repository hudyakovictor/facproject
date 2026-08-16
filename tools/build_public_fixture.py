#!/usr/bin/env python3
"""Build a small, real-data review fixture without publishing the full run.

The fixture intentionally contains three complete Stage 1 artifact folders,
including OBJ meshes and NPZ outputs, plus the Stage 2 pair rows touching those
photos. Model weights and the full 1,909-photo / full pair matrix stay local.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path


def _copy_tree_files(source: Path, target: Path) -> list[str]:
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for item in sorted(source.iterdir()):
        if not item.is_file() or item.name.startswith("._"):
            continue
        destination = target / item.name
        shutil.copy2(item, destination)
        copied.append(item.name)
    return copied


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage1", type=Path, default=Path("/Volumes/SDCARD/storage/stage1"))
    parser.add_argument("--stage2", type=Path, default=Path("/Volumes/SDCARD/storage/stage2_resumable_20260816"))
    parser.add_argument("--output", type=Path, default=Path("fixtures/public-sample"))
    args = parser.parse_args()

    timeline_path = args.stage1 / "main_timeline.csv"
    pair_path = args.stage2 / "pair_metrics.csv"
    if not timeline_path.is_file() or not pair_path.is_file():
        raise SystemExit("Stage1 main_timeline.csv или Stage2 pair_metrics.csv не найден")

    with timeline_path.open(newline="", encoding="utf-8") as handle:
        timeline_rows = sorted(csv.DictReader(handle), key=lambda row: (row.get("date") or "", row.get("photo_id") or ""))
    candidates = [row for row in timeline_rows if (args.stage1 / str(row.get("photo_id"))).is_dir()]
    if len(candidates) < 3:
        raise SystemExit("Для fixture найдено меньше трёх папок Stage1")
    selected_rows = [candidates[0], candidates[len(candidates) // 2], candidates[-1]]
    selected_ids = [str(row["photo_id"]) for row in selected_rows]

    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)
    photos_root = args.output / "stage1"
    for photo_id in selected_ids:
        copied = _copy_tree_files(args.stage1 / photo_id, photos_root / photo_id)
        (photos_root / photo_id / "_fixture_contents.json").write_text(
            json.dumps({"photo_id": photo_id, "copied_files": copied, "note": "Полный набор артефактов этого тестового кадра, включая 3D mesh и NPZ."}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    selected_pairs: list[dict[str, str]] = []
    with pair_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("photo_a") in selected_ids or row.get("photo_b") in selected_ids:
                selected_pairs.append(row)
    with (args.output / "stage2_pairs.json").open("w", encoding="utf-8") as handle:
        json.dump(selected_pairs, handle, ensure_ascii=False, indent=2)

    # Import the same projection used by the real API, so the fixture does not
    # invent UI values that differ from the local application.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app6.api.research_timeline import build_research_timeline

    full_projection = build_research_timeline(args.stage2, args.stage1)
    full_projection["photos"] = [row for row in full_projection.get("photos", []) if row.get("id") in selected_ids]
    full_projection["fixture"] = {"selected_photo_ids": selected_ids, "is_reduced": True}
    (args.output / "timeline.json").write_text(json.dumps(full_projection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "fixture_schema": "facproject-public-review-fixture-v1",
        "selected_photo_ids": selected_ids,
        "selected_dates": [row.get("date") for row in selected_rows],
        "stage1_artifacts": "complete for the three selected photos, including original/derived images, masks, UV texture, OBJ/MTL, NPZ, CSV and JSON metadata",
        "stage2_artifacts": {"pair_rows_touching_selected_photos": len(selected_pairs), "full_pair_matrix_included": False},
        "omitted_from_github": ["model weights", "full Stage1 storage", "full Stage2 pair_metrics.csv", "full local run outputs"],
        "local_full_data": {"stage1": str(args.stage1), "stage2": str(args.stage2)},
        "review_note": "Это намеренно урезанный публичный набор для анализа ошибок; локальная версия содержит полный прогон.",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "selected_ids": selected_ids, "pair_rows": len(selected_pairs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
