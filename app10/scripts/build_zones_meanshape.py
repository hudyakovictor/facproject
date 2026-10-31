#!/usr/bin/env python3
"""Зоны на СРЕДНЕЙ форме BFM (ключ `u` в face_model.npy) + приёмка правил и таблица чувствительности.

Зачем средняя форма. Она почти симметрична и не принадлежит ни одному человеку, поэтому на ней
проверяется сам алгоритм зон (симметрия щёк и челюсти, покрытие, устойчивость к сдвигу плоскости),
а не асимметрия конкретного лица. Индексы зон потом применяются ко всем сеткам: топология одна.
На реальных лицах отношение левой и правой сторон — справочное число, не порог.

Нормировка как у остальных сеток: центр = среднее по ldm106, масштаб = RMS по ldm106.
Код возврата 1, если приёмка не пройдена (порог --max-asym).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.face_model_io import load_face_model  # noqa: E402
from src.mesh_geometry import vertex_areas  # noqa: E402
from src.zones import check_disjoint, save_zones, zones_sha256  # noqa: E402
from src.zones_annotation import NON_FACE_ZONES, zones_from_annotation  # noqa: E402

PAIRS = (("cheek_r", "cheek_l"), ("jaw_r", "jaw_l"))
SHIFTS = (-0.01, -0.005, 0.0, 0.005, 0.01)


def normalize_ldm106(v, ldm106):
    p = v[ldm106]
    center = p.mean(axis=0)
    scale = float(np.sqrt(np.mean(np.sum((p - center) ** 2, axis=1))))
    return (v - center) / scale


def asym(zones, area, a, b):
    """Относительная разница левой и правой зон: по числу вершин и по площади, в процентах."""
    na, nb = len(zones[a]), len(zones[b])
    aa, ab = float(area[zones[a]].sum()), float(area[zones[b]].sum())
    return {"vertices_pct": 100.0 * abs(na - nb) / max(na, nb, 1),
            "area_pct": 100.0 * abs(aa - ab) / max(aa, ab, 1e-12), "n": [na, nb]}


def main():
    p = argparse.ArgumentParser(description="Зоны на средней форме BFM + приёмка")
    p.add_argument("--face-model", required=True)
    p.add_argument("--out-json", default="app10/configs/zones_meanshape.json")
    p.add_argument("--report", default="app10/reports/zones_meanshape_acceptance.json")
    p.add_argument("--max-asym", type=float, default=5.0, help="порог симметрии щёк и челюсти, % (вершины и площадь)")
    args = p.parse_args()

    fm = load_face_model(args.face_model)
    for key in ("mean_shape", "annotation", "ldm106"):
        if key not in fm:
            sys.exit(f"в face_model.npy нет {'u' if key == 'mean_shape' else key}")
    v = normalize_ldm106(fm["mean_shape"], fm["ldm106"])
    if v.shape[0] != fm["tri"].max() + 1:
        print(f"ВНИМАНИЕ: вершин {v.shape[0]}, максимальный индекс в tri {fm['tri'].max()}")
    area = vertex_areas(v, fm["tri"])

    zones, info = zones_from_annotation(fm["annotation"], v, fm["ldm106"], tri=fm["tri"], return_info=True)
    covered = sum(len(z) for z in zones.values())
    checks = {"disjoint": bool(check_disjoint(zones)), "covered": covered, "n_vertices": int(len(v))}
    sens = {}
    for dx in SHIFTS:
        z = zones_from_annotation(fm["annotation"], v, fm["ldm106"], tri=fm["tri"], plane_shift=dx)
        sens[f"{dx:+.3f}"] = {f"{a}/{b}": asym(z, area, a, b) for a, b in PAIRS}
    base = {f"{a}/{b}": asym(zones, area, a, b) for a, b in PAIRS}
    worst = max(max(r["vertices_pct"], r["area_pct"]) for r in base.values())
    worst_shift = max(max(r["vertices_pct"], r["area_pct"]) for s in sens.values() for r in s.values())
    ok = checks["disjoint"] and covered == len(v) and worst <= args.max_asym
    report = {
        "zones_sha256": zones_sha256(zones), "max_asym_pct": args.max_asym, "passed": bool(ok),
        "plane": info["plane"], "midline_offset": info["midline_offset"], "checks": checks,
        "asymmetry_pct": base, "sensitivity_to_plane_shift": sens,
        "worst_asym_pct": worst, "worst_asym_pct_with_shifts": worst_shift,
        "fractions": {k: len(v_) / len(v) for k, v_ in zones.items()},
        "non_face_zones": [z for z in NON_FACE_ZONES if z in zones],
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    save_zones(args.out_json, zones, len(v), rules={"method": "meanshape+symmetry_pairs+polygon"},
               source={"base": "bfm_mean_shape", "face_model": str(args.face_model)})
    print("WROTE", args.out_json, "и", args.report)
    print("симметрия, %:", {k: (round(r["vertices_pct"], 2), round(r["area_pct"], 2)) for k, r in base.items()})
    print("худшая при сдвиге плоскости ±0.01, %:", round(worst_shift, 2), "| приёмка:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
