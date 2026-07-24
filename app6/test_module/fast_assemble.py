"""⚡ FAST-режим: сборка stage1-выхода сценария из кэша БЕЗ инференса.
Копирует готовые папки photo_id из cache/stage1 и переписывает только даты/
последовательность/источник в main_timeline.csv и info.json.
Само сравнение (Stage 2→2B→3) всегда считается честно заново."""
from __future__ import annotations
import csv
import json
import shutil
from pathlib import Path


def _read_csv(p: Path):
    with p.open(encoding="utf-8") as f:
        rd = csv.DictReader(f)
        return list(rd), list(rd.fieldnames or [])


def assemble(manifest: dict, cache_stage1: Path, out_stage1: Path) -> None:
    rows, fields = _read_csv(cache_stage1 / "main_timeline.csv")
    by_tag: dict[str, dict] = {}
    for row in rows:
        pid = str(row.get("photo_id", ""))
        for fr in manifest["frames"]:
            if fr["tag"] in pid:
                by_tag.setdefault(fr["tag"], row)
    if out_stage1.exists():
        shutil.rmtree(out_stage1)
    out_stage1.mkdir(parents=True)
    new_rows = []
    for fr in manifest["frames"]:
        crow = by_tag.get(fr["tag"])
        if crow is None:
            raise RuntimeError(f"кадр {fr['tag']} отсутствует в кэше stage1 — выполните: python -m test_module.runner cache --run")
        cache_id = str(crow["photo_id"])
        # Keep the deterministic source tag in every scenario photo_id. The
        # checker uses it to map expected frame numbers to pair_metrics rows.
        new_id = f"{fr['stem']}__{fr['tag']}"
        shutil.copytree(cache_stage1 / cache_id, out_stage1 / new_id)
        y, m, d = fr["date"].split("_")
        rel = f"{fr['group']}/{fr['filename']}"
        info_path = out_stage1 / new_id / "info.json"
        info = json.loads(info_path.read_text(encoding="utf-8"))
        info.update({"photo_id": new_id, "date": fr["date_iso"], "date_year": int(y), "date_month": int(m),
                     "date_day": int(d), "same_date_sequence": fr["seq"],
                     "source_filename": fr["filename"], "source_relative_path": rel})
        info_path.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        nrow = dict(crow)
        for k, v in (("photo_id", new_id), ("date", fr["date_iso"]), ("date_year", y), ("date_month", m),
                     ("date_day", d), ("same_date_sequence", str(fr["seq"])),
                     ("source_filename", fr["filename"]), ("source_relative_path", rel)):
            if k in nrow or k in ("photo_id", "date", "same_date_sequence"):
                nrow[k] = v
        new_rows.append(nrow)
    new_rows.sort(key=lambda r: (r["date"], int(r["same_date_sequence"]), r["photo_id"]))
    pose_counts: dict[str, int] = {}
    for i, row in enumerate(new_rows, 1):
        if "chronology_index_global" in row:
            row["chronology_index_global"] = str(i)
        pb = str(row.get("pose_bin", ""))
        pose_counts[pb] = pose_counts.get(pb, 0) + 1
        if "chronology_index_in_pose" in row:
            row["chronology_index_in_pose"] = str(pose_counts[pb])
    fields2 = fields or list(new_rows[0].keys())
    for name in ("main_timeline.csv", "main_index.csv"):
        with (out_stage1 / name).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields2)
            w.writeheader()
            w.writerows(new_rows)
    (out_stage1 / "errors.csv").write_text("", encoding="utf-8")
    man_src = cache_stage1 / "stage1_manifest.json"
    man = json.loads(man_src.read_text(encoding="utf-8")) if man_src.is_file() else {"status": "complete"}
    man.update({"assembled_by": "test_module-fast-v1", "success_count": len(new_rows),
                "input_count": len(new_rows), "error_count": 0})
    (out_stage1 / "stage1_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
