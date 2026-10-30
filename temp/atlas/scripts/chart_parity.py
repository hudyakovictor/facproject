"""B7: parity ряда графика.

1. Ряд из API (`/api/chart/series`) совпадает с harness
   (`chart.step` по кадрам `calibration_v3.load_frames`) побитово.
2. Цепочка из 10 кадров: ряд не зависит от того, считается маршрут целиком
   или двумя сегментами с общим кадром.
3. Стык сегментов: значение шага на стыке одно и то же (join = 0).
4. Агрегат графика сходится с per-vertex `end` из /api/photos/{id}/heat:
   один helper `compute_heat_values`, одна калибровка.

    python scripts/chart_parity.py

Пишет reports/calibration/chart-parity.json. Ненулевой код возврата —
любая расхождение.
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from calibration_check import select_frames  # noqa: E402
from calibration_v3 import index_rows, load_frames, topology  # noqa: E402
from chart_score import ids_into, rows_for  # noqa: E402
from server import chart, storage  # noqa: E402
from server.app import app  # noqa: E402

MODES = ("euclid", "normal", "weighted_euclid", "weighted_normal")
# value_display проверяется отдельно: harness хранит raw, а отображение —
# результат медианного окна поверх этого raw.
FIELDS = ("value_raw", "band", "z_mean", "z_p95",
          "frac_z_gt3", "low_confidence_fraction", "significance")


def bits(value) -> bytes:
    return b"none" if value is None else struct.pack("<d", float(value))


def same(a, b) -> bool:
    return bits(a) == bits(b)


def parity(person, mode, frames, tri, client):
    """API ↔ harness на одном человеке: все поля шага побитово."""
    api = client.get("/api/chart/series",
                     params={"group": person, "metric": mode})
    api.raise_for_status()
    payload = api.json()
    _, harness = rows_for(frames, tri, mode)
    names_by_id = {p["id"]: p["name"] for p in storage.read_db()["photos"]}
    name_by_frame = {f["frame"]: names_by_id[f["id"]] for f in frames}
    names = {f["id"]: f["name"] for f in payload["frames"]}
    by_pair = {(name_by_frame[r["from"]], name_by_frame[r["to"]]): r
               for r in harness}
    missing, mismatch, max_delta = 0, 0, 0.0
    for row in payload["rows"]:
        key = (names[row["from"]], names[row["to"]])
        ref = by_pair.get(key)
        if ref is None:
            missing += 1
            continue
        for field in FIELDS:
            a, b = row.get(field), ref.get(field)
            if not same(a, b):
                mismatch += 1
                if isinstance(a, float) and isinstance(b, float):
                    max_delta = max(max_delta, abs(a - b))
    raws = [r["value_raw"] for r in payload["rows"]]
    mode_cfg = payload["mode"]
    expected = (raws if mode_cfg["temporal_filter"] == "none"
                else chart.median_window(raws, mode_cfg["filter_window"]))
    display_ok = all(same(r["value_display"], v) for r, v
                     in zip(payload["rows"], expected, strict=True))
    return {
        "steps": len(payload["rows"]),
        "harness_steps": len(harness),
        "missing_pairs": missing,
        "mismatched_fields": mismatch,
        "max_abs_delta": max_delta,
        "display_ok": display_ok,
        "mode": mode_cfg,
        "pass": missing == 0 and mismatch == 0 and display_ok
                and len(payload["rows"]) == len(harness),
    }


def chain(frames, tri, mode, cut=6):
    """10 кадров: целиком == два сегмента с общим кадром; join = 0."""
    cfg = chart.mode(mode)
    full = chart.series(frames, tri, cfg, temporal_filter="none")
    left = chart.series(frames[:cut], tri, cfg, temporal_filter="none")
    right = chart.series(frames[cut - 1:], tri, cfg, temporal_filter="none")
    exp_left, exp_right = full[:cut - 1], full[cut - 1:]
    mismatch = 0
    for a, b in zip(exp_left, left, strict=False):
        mismatch += sum(not same(a[f], b[f]) for f in FIELDS)
    for a, b in zip(exp_right, right, strict=False):
        mismatch += sum(not same(a[f], b[f]) for f in FIELDS)
    join = max(
        abs(full[cut - 2]["value_raw"] - left[-1]["value_raw"]),
        abs(full[cut - 1]["value_raw"] - right[0]["value_raw"]),
    )
    med = chart.series(frames, tri, cfg, temporal_filter="median", window=3)
    raw_kept = all(same(a["value_raw"], b["value_raw"])
                   for a, b in zip(full, med, strict=True))
    display_changed = any(not same(a["value_display"], b["value_display"])
                          for a, b in zip(full, med, strict=True))
    return {
        "mode": mode,
        "frames": len(frames),
        "steps": len(full),
        "segments": [[0, cut], [cut - 1, len(frames)]],
        "mismatched_fields": mismatch,
        "join_max_abs_delta": join,
        "median_keeps_raw": raw_kept,
        "median_changes_display": display_changed,
        "pass": mismatch == 0 and join == 0.0 and raw_kept,
    }


def heat_crosscheck(person, mode, frames, tri, client):
    """Агрегат строки графика == агрегат per-vertex `end` из heat-эндпоинта."""
    payload = client.get("/api/chart/series",
                         params={"group": person, "metric": mode}).json()
    pair = payload["rows"][0]
    ids = {f["id"]: f for f in payload["frames"]}
    response = client.get(
        f"/api/photos/{pair['from']}/heat",
        params={"other": pair["to"], "reference": pair["from"],
                "morphing": "true", "metric": "normal" if "normal" in mode else "distance",
                "weighting": "calibrated" if mode.startswith("weighted") else "none",
                "normalizeScale": "true"},
    )
    response.raise_for_status()
    out = response.json()
    end = np.frombuffer(base64.b64decode(out["end"]), dtype="<f4").astype(np.float64)
    cfg = chart.mode(mode)
    helper = chart.step(frames[0]["vertices"], frames[1]["vertices"], tri, cfg)
    cal = cfg["calibration"]
    if mode.startswith("weighted"):
        total = cal.weight_normal_sum if "normal" in mode else cal.weight_sum
        value = float(end.sum() / total)
    else:
        value = float(end.mean())
    return {
        "mode": mode,
        "pair": [ids[pair["from"]]["name"], ids[pair["to"]]["name"]],
        "heat_aggregate": value,
        "chart_value_raw": pair["value_raw"],
        "helper_value_raw": helper["value_raw"],
        "max_abs_delta": max(abs(value - pair["value_raw"]),
                             abs(value - helper["value_raw"])),
        "pass": same(value, pair["value_raw"]) and same(value, helper["value_raw"]),
    }


def config_switch(person):
    """Смена блока chart видна без рестарта: кэш ключуется конфигом.

    Патчим `chart.settings` в процессе, файл конфига не трогаем. Проверяем
    три вещи: temporal_filter меняет только value_display, metric меняет
    value_raw и band, возврат конфига возвращает исходную подпись.
    """
    import server.app as app_mod
    from server import chart as chart_mod

    original = chart_mod.settings

    def patched(**over):
        def inner():
            base = dict(original())
            base.update(over)
            return base
        return inner

    _, series_sig = app_mod.chart_sequence(person)
    sig_base = app_mod.chart_config_signature()
    base = app_mod.chart_payload(person, "", series_sig, sig_base)
    try:
        chart_mod.settings = patched(temporal_filter="median", filter_window=3)
        sig_med = app_mod.chart_config_signature()
        med = app_mod.chart_payload(person, "", series_sig, sig_med)
        chart_mod.settings = patched(metric="weighted_normal")
        sig_wn = app_mod.chart_config_signature()
        wn = app_mod.chart_payload(person, "", series_sig, sig_wn)
    finally:
        chart_mod.settings = original
    restored = app_mod.chart_config_signature() == sig_base
    raw_kept = all(same(a["value_raw"], b["value_raw"])
                   for a, b in zip(base["rows"], med["rows"], strict=True))
    display_changed = any(not same(a["value_display"], b["value_display"])
                          for a, b in zip(base["rows"], med["rows"], strict=True))
    band_changed = (wn["rows"][0]["band"] is not None
                    and not same(wn["rows"][0]["band"], base["rows"][0]["band"]))
    metric_changed = (wn["mode"]["name"] == "weighted_normal"
                      and not same(base["rows"][0]["value_raw"],
                                   wn["rows"][0]["value_raw"])
                      and band_changed)
    return {
        "base_mode": base["mode"],
        "median_mode": med["mode"],
        "weighted_mode": wn["mode"],
        "signature_changes": sig_med != sig_base and sig_wn != sig_base,
        "raw_kept": raw_kept,
        "display_changed": display_changed,
        "metric_changed": metric_changed,
        "restored": restored,
        "pass": (sig_med != sig_base and sig_wn != sig_base and raw_kept
                 and display_changed and metric_changed and restored),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calibration-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"))
    ap.add_argument("--photos-root", type=Path,
                    default=Path("/Volumes/SDCARD/photo/calibration_dataset/photos"))
    ap.add_argument("--per-person", type=int, default=30)
    ap.add_argument("--people", default="person_04,person_02")
    ap.add_argument("--json", type=Path,
                    default=ROOT / "reports/calibration/chart-parity.json")
    args = ap.parse_args()

    from fastapi.testclient import TestClient

    client = TestClient(app)
    index_path = args.calibration_root / "all_calibration_index.csv"
    index = index_rows(index_path)
    selected = ids_into(select_frames(index_path, args.photos_root, args.per_person))
    tri, lm = topology()

    result = {"endpoint": "/api/chart/series", "parity": {}, "chain": {},
              "heat": {}, "config": {}, "pass": True}
    first_frames = None
    for person in args.people.split(","):
        frames = [f for f in load_frames({person: selected[person]}, index, tri, lm, {})
                  if f["valid"]]
        if len(frames) < 11:
            raise SystemExit(f"{person}: мало валидных кадров ({len(frames)})")
        if first_frames is None:
            first_frames = frames
        result["parity"][person] = {}
        for mode in MODES:
            row = parity(person, mode, frames, tri, client)
            result["parity"][person][mode] = row
            result["pass"] &= row["pass"]
            print(f"parity {person:10s} {mode:17s} шагов {row['steps']:3d} "
                  f"mismatch {row['mismatched_fields']} "
                  f"max|Δ| {row['max_abs_delta']:.3g}")
        if first_frames is frames:
            for mode in ("euclid", "weighted_normal"):
                row = heat_crosscheck(person, mode, frames, tri, client)
                result["heat"][mode] = row
                result["pass"] &= row["pass"]
                print(f"heat   {person:10s} {mode:17s} "
                      f"Δ {row['max_abs_delta']:.3g}")

    chain_frames = first_frames[:10]
    for mode in MODES:
        row = chain(chain_frames, tri, mode)
        result["chain"][mode] = row
        result["pass"] &= row["pass"]
        print(f"chain  {mode:17s} шагов {row['steps']} "
              f"mismatch {row['mismatched_fields']} join {row['join_max_abs_delta']:.3g} "
              f"raw_kept {row['median_keeps_raw']}")
    config = config_switch(args.people.split(",")[0])
    result["config"] = config
    result["pass"] &= config["pass"]
    print(f"config {config['base_mode']['name']:15s} → median raw_kept "
          f"{config['raw_kept']} display_changed {config['display_changed']} "
          f"metric_changed {config['metric_changed']} restored {config['restored']}")
    result["all_pass"] = bool(result["pass"])
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    print("PASS" if result["all_pass"] else "FAIL", "->", args.json)
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
