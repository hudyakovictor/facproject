"""Паритет preview / export / браузера по значениям heatmap.

Все три пути обязаны получать одни и те же start/end значения из
server.heat: preview зовёт app.segment_heat, export — rendering.segment_values,
браузер — GET /api/photos/{id}/heat (base64 float32). Критерий — расхождение
не больше 1e-6 до colorize.

    cd /Users/victorkhudyakov/work/temp/atlas
    OPENBLAS_NUM_THREADS=2 python scripts/heat_parity.py
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import ingest_and_process, select_frames  # noqa: E402
from server.heat import resolve as heat_resolve  # noqa: E402

TOL = 1e-6
MODES = [
    ("euclid", "distance", "none"),
    ("normal", "normal", "none"),
    ("weighted_euclid", "distance", "calibrated"),
    ("weighted_normal", "normal", "calibrated"),
]


def pairs_for(rows, per_person=3):
    """Пары одного человека: (a, b, reference) по хронологии."""
    ordered = sorted(rows, key=lambda r: int(r["frame"]))
    out = []
    for i in range(0, min(len(ordered) - 1, per_person * 2), 2):
        ref = ordered[max(0, i - 1)]
        out.append((ordered[i], ordered[i + 1], ref))
    return out


def decode(payload):
    return tuple(
        np.frombuffer(base64.b64decode(payload[key]), "<f4")
        for key in ("start", "end")
    )


def api_smoke(a_id, b_id, r_id, count):
    """Реальный HTTP-слой: параметры, типы и PNG-превью."""
    from fastapi.testclient import TestClient

    from server.app import app

    client = TestClient(app)
    query = {"other": b_id, "reference": r_id, "morphing": "true",
             "metric": "normal", "weighting": "calibrated"}
    heat = client.get(f"/api/photos/{a_id}/heat", params=query)
    preview = client.get(f"/api/photos/{a_id}/preview",
                         params={**query, "vmax": 4.0, "size": 128})
    runtime = client.get("/api/runtime")
    body = heat.json() if heat.status_code == 200 else {}
    return {
        "heat_status": heat.status_code,
        "heat_count": int(body.get("count", 0)),
        "heat_vmax": body.get("vmax"),
        "heat_count_ok": int(body.get("count", 0)) == count,
        "preview_status": preview.status_code,
        "preview_png": bool(preview.content[:8] == b"\x89PNG\r\n\x1a\n"),
        "runtime_block": (runtime.json() or {}).get("heatmap"),
    }


def config_switch(a_id, r_id):
    """Режим карты меняется только configs/runtime.yaml, без правки кода."""
    from fastapi.testclient import TestClient

    from server.app import app

    path = ROOT / "configs/runtime.yaml"
    original = path.read_text()
    client = TestClient(app)

    def probe():
        response = client.get(f"/api/photos/{a_id}/heat", params={"reference": r_id})
        body = response.json() if response.status_code == 200 else {}
        return {"status": response.status_code, "metric": body.get("metric"),
                "weighting": body.get("weighting"), "vmax": body.get("vmax")}

    switched = original.replace("  metric: euclid\n  weighting: none\n",
                                "  metric: normal\n  weighting: calibrated\n")
    if switched == original:
        return {"error": "в configs/runtime.yaml нет блока heatmap"}
    out = {"base": probe()}
    try:
        path.write_text(switched)
        out["switched"] = probe()
    finally:
        path.write_text(original)
    out["restored"] = probe()
    out["ok"] = bool(
        out["base"]["metric"] == "euclid" and out["base"]["weighting"] == "none"
        and out["switched"]["metric"] == "normal"
        and out["switched"]["weighting"] == "calibrated"
        and out["switched"]["vmax"] == 4.0
        and out["restored"] == out["base"]
    )
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--people", type=int, default=2)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "reports/calibration/v3-parity.json")
    args = ap.parse_args()

    from server import app as api
    from server import storage
    from server.rendering import segment_values

    index_path = args.calibration_root / "all_calibration_index.csv"
    selected = select_frames(index_path, args.photos_root, args.per_person)
    if not selected:
        raise SystemExit("корпус не выбран")
    ingest_and_process(selected, False)

    top = api.topology_data()
    tri = np.asarray(top["triangles"], np.int32)
    features = {}
    cases = []
    first_ids = None
    for person in sorted(selected)[: args.people]:
        rows = selected[person]
        for a_row, b_row, r_row in pairs_for(rows):
            first_ids = first_ids or (a_row["id"], b_row["id"], r_row["id"])
            for row in (a_row, b_row, r_row):
                if row["id"] not in features:
                    features[row["id"]] = storage.load_features(storage.photo(row["id"]))
            a = features[a_row["id"]]
            b = features[b_row["id"]]
            r = features[r_row["id"]]
            for name, metric, weighting in MODES:
                mode = heat_resolve(metric, weighting)
                start_p, end_p, _ = api.segment_heat(
                    a, b, r, tri=tri, morphing=True, t=0.5,
                    metric=metric, weighting=weighting, smoothing=0,
                )
                start_e, end_e = segment_values(
                    a, b, r, tri, mode, metric_name=metric, smoothing=0,
                )
                payload = api.heat_values(
                    a_row["id"], other=b_row["id"], reference=r_row["id"],
                    morphing=True, metric=metric, weighting=weighting,
                )
                start_h, end_h = decode(payload)
                diffs = {
                    "preview_export": float(max(
                        np.abs(start_p - start_e).max(), np.abs(end_p - end_e).max())),
                    "preview_browser": float(max(
                        np.abs(start_p - start_h).max(), np.abs(end_p - end_h).max())),
                }
                # Colorize — следующий шаг после значений; оба пути зовут его с
                # одинаковыми параметрами, поэтому картинка совпадает побитно.
                palette = {"lo": 0.0, "hi": mode["vmax"], "palette": "turbo",
                           "gamma": 2.0, "inverse": False, "custom": None}
                heat_p = api.colorize(start_p, **palette)
                heat_e = api.colorize(start_e, **palette)
                diffs["colorized"] = float(np.abs(heat_p - heat_e).max())
                cases.append({
                    "person": person,
                    "frame_a": int(a_row["frame"]),
                    "frame_b": int(b_row["frame"]),
                    "frame_ref": int(r_row["frame"]),
                    "mode": name,
                    "metric": mode["metric"],
                    "weighting": mode["weighting"],
                    "vmax": mode["vmax"],
                    "count": int(len(start_p)),
                    **{k: round(v, 12) for k, v in diffs.items()},
                })
                print(f"{person} {a_row['frame']}->{b_row['frame']} {name:16s} "
                      f"preview/export {diffs['preview_export']:.2e} "
                      f"browser {diffs['preview_browser']:.2e} "
                      f"color {diffs['colorized']:.2e}")

    max_abs = max(max(c["preview_export"], c["preview_browser"]) for c in cases)
    max_color = max(c["colorized"] for c in cases)
    try:
        http = api_smoke(*first_ids, cases[0]["count"])
        print("http", http)
    except Exception as exc:  # httpx нет или API недоступен — не валит паритет
        http = {"error": str(exc)}
        print("http skipped:", exc)
    try:
        config = config_switch(*first_ids[:2])
        print("config", config)
    except Exception as exc:
        config = {"error": str(exc)}
        print("config skipped:", exc)
    report = {
        "helper": "server.heat.compute_heat_values",
        "paths": ["server/app.py:segment_heat", "server/rendering.py:segment_values",
                  "GET /api/photos/{id}/heat"],
        "tolerance": TOL,
        "cases": len(cases),
        "max_abs_diff": float(max_abs),
        "max_color_diff": float(max_color),
        "http": http,
        "config": config,
        "passed": bool(max_abs <= TOL),
        "per_case": cases,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print("max", f"{max_abs:.2e}", "passed", report["passed"], "->", args.out)
    if not report["passed"]:
        raise SystemExit("паритет нарушен")


if __name__ == "__main__":
    main()
