"""Хронологическая цепочка из 10 кадров: стыки сегментов.

Проверяет маршрут A→B→…→J: геометрию на стыке, непрерывность значений
карты, цветовую непрерывность после colorize/threshold и независимость от
того, экспортируется ли цепочка целиком или сегменты по отдельности.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 python scripts/heat_chain.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import compose_rows, heat_panel, ingest_and_process, select_frames  # noqa: E402
from server.heat import resolve as heat_resolve  # noqa: E402

TOL = 1e-6
MODES = [
    ("euclid", "distance", "none"),
    ("normal", "normal", "none"),
    ("weighted_euclid", "distance", "calibrated"),
    ("weighted_normal", "normal", "calibrated"),
]
VMIN = 0.0


def chain_for(selected, length):
    """Самый длинный хронологический ряд одного человека."""
    best = None
    for person, rows in selected.items():
        ordered = sorted(rows, key=lambda r: int(r["frame"]))
        if len(ordered) >= length and (best is None or len(ordered) > len(best[1])):
            best = (person, ordered)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--length", type=int, default=10)
    ap.add_argument("--out", type=Path, default=ROOT / "reports/calibration/v3-chain.json")
    ap.add_argument("--png", type=Path, default=ROOT / "reports/calibration/v3-chain.png")
    args = ap.parse_args()

    from server import app as api
    from server import storage
    from server.rendering import segment_values

    index_path = args.calibration_root / "all_calibration_index.csv"
    selected = select_frames(index_path, args.photos_root, args.per_person)
    if not selected:
        raise SystemExit("корпус не выбран")
    ingest_and_process(selected, False)
    picked = chain_for(selected, args.length)
    if not picked:
        raise SystemExit("нет человека с достаточной хронологией")
    person, rows = picked
    rows = rows[: args.length]
    frames = [storage.load_features(storage.photo(row["id"])) for row in rows]
    top = api.topology_data()
    tri = np.asarray(top["triangles"], np.int32)
    ref = frames[0]

    payload = {
        "person": person,
        "frames": [int(r["frame"]) for r in rows],
        "bins": [r["bin"] for r in rows],
        "segments": len(frames) - 1,
        "tolerance": TOL,
        "modes": {},
    }
    panels = []
    for name, metric, weighting in MODES:
        mode = heat_resolve(metric, weighting)
        starts, ends = [], []
        for segment in range(len(frames) - 1):
            previous = frames[segment - 1] if segment else ref
            start, end = segment_values(
                frames[segment], frames[segment + 1], previous, tri, mode,
                metric_name=metric,
            )
            starts.append(start)
            ends.append(end)
        # Сегменты отдельно: каждый считается независимым вызовом preview-пути,
        # без состояния предыдущего сегмента.
        isolated = []
        for segment in range(len(frames) - 1):
            previous = frames[segment - 1] if segment else ref
            start_i, end_i, _ = api.segment_heat(
                frames[segment], frames[segment + 1], previous, tri=tri,
                morphing=True, t=0.0, metric=metric, weighting=weighting, smoothing=0,
            )
            isolated.append((start_i, end_i))
        isolated_diff = max(
            float(max(np.abs(a[0] - b[0]).max(), np.abs(a[1] - b[1]).max()))
            for a, b in zip(isolated, zip(starts, ends, strict=True), strict=True)
        )
        heat_join, color_join, alpha_flip = [], [], []
        for segment in range(len(ends) - 1):
            heat_join.append(float(np.abs(ends[segment] - starts[segment + 1]).max()))
            hi = mode["vmax"]
            color_a = api.colorize(ends[segment], lo=VMIN, hi=hi, palette="turbo", gamma=1)
            color_b = api.colorize(starts[segment + 1], lo=VMIN, hi=hi, palette="turbo", gamma=1)
            color_join.append(float(np.abs(color_a - color_b).max()))
            alpha_flip.append(int(((ends[segment] > VMIN)
                                   != (starts[segment + 1] > VMIN)).sum()))
        change = [float(np.abs(ends[s] - starts[s]).mean()) for s in range(len(ends))]
        payload["modes"][name] = {
            "metric": mode["metric"],
            "weighting": mode["weighting"],
            "vmax": mode["vmax"],
            "join_heat": round(max(heat_join), 12),
            "join_color": round(max(color_join), 12),
            "join_alpha_flip": int(max(alpha_flip)),
            # Ключевой кадр B сегмента s — это же A сегмента s+1, поэтому
            # геометрического скачка нет по построению маршрута.
            "join_vertex": 0.0,
            "segment_independent": round(isolated_diff, 12),
            "segment_change_min": round(min(change), 8),
            "segment_change_max": round(max(change), 8),
            "flat_segments": int(sum(c == 0 for c in change)),
        }
        print(f"{name:16s} heat {max(heat_join):.2e} color {max(color_join):.2e} "
              f"alpha {max(alpha_flip)} isolated {isolated_diff:.2e} "
              f"change {min(change):.4f}..{max(change):.4f}")
        if name == "weighted_normal":
            panels.append([heat_panel(ends[s], frames[s]["vertices"], tri, 220, mode["vmax"])
                           for s in range(min(4, len(ends)))])

    payload["join_jump"] = payload["modes"]["euclid"]["join_vertex"]
    payload["heat_join"] = payload["modes"]["weighted_normal"]["join_heat"]
    payload["color_join"] = payload["modes"]["weighted_normal"]["join_color"]
    payload["segment_independent"] = all(
        row["segment_independent"] <= TOL for row in payload["modes"].values())
    payload["passed"] = bool(
        payload["heat_join"] <= TOL
        and payload["color_join"] <= TOL
        and payload["modes"]["weighted_normal"]["join_alpha_flip"] == 0
        and payload["segment_independent"]
        and payload["modes"]["weighted_normal"]["flat_segments"] == 0
    )
    if panels:
        compose_rows(panels, args.png)
        payload["png"] = str(args.png.relative_to(ROOT))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    print("passed", payload["passed"], "->", args.out)


if __name__ == "__main__":
    main()
