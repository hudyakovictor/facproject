#!/usr/bin/env python
"""НУЛЛ-КАЛИБРОВКА шума метрик по /Volumes/SDCARD/calibration_rakurs.

В каждом bin заведомо ОДИН человек -> разброс метрики по кадрам внутри
(person,bin) = чистый шум (микро-поза + мимика + recon-джиттер), без сигнала
личности. Отсюда заранее знаем, как «шумит» каждая метрика на каждом ракурсе, и
можем строить inverse-variance веса и честные пороги для put/vas/udmurt.

Метрики считаем в V_can = vertices_identity_only (exp=0, без R/t) + center/scale,
как в основном пайплайне. Три блока: form_vector(17), form_vector на
СИММЕТРИЗОВАННЫХ точках, geometry-univariate гипотезы (hc.univariate).

Фаза A: evenly-spaced <=K кадров на (person,bin), recon -> фичи в кэш (resumable).
Фаза B: шум (медиана within-std по людям) и сигнал (std межличностных средних),
        ICC и inflation относительно frontal, по каждому бину.
"""
from __future__ import annotations
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
HERE = Path(__file__).resolve().parent
DATA = Path("/Volumes/SDCARD/calibration_rakurs")
CACHE = ROOT / ".runtime" / "rakurs_cache"
ROWS = CACHE / "features.jsonl"
OUT = ROOT / ".runtime" / "rakurs_noise.json"
BINS = ("frontal", "left_light", "right_light", "left_mid", "right_mid",
        "left_deep", "right_deep", "left_profile", "right_profile")
K = 10
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")

spec = importlib.util.spec_from_file_location("hc", HERE / "hypotheses_check.py")
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
from morphing.backend import identity as I
from morphing.backend.aligner import align_identity_mesh

PAIRS = [(0, 31), (1, 29), (3, 27), (5, 25), (7, 23), (9, 21), (11, 19), (13, 17),
         (33, 46), (34, 45), (35, 44), (36, 43), (37, 42), (57, 63), (59, 61),
         (66, 79), (67, 78), (69, 76), (70, 75), (71, 82), (73, 80),
         (84, 90), (85, 89), (86, 88), (91, 95), (92, 94), (96, 100), (97, 99), (101, 103)]
MIDLINE = [15, 51, 52, 53, 54, 60, 87, 93]


def symmetrize(p):
    cx = float(p[:, 0].mean())
    refl = lambda q: np.array([2 * cx - q[0], q[1], q[2]])
    out = p.copy()
    for i, j in PAIRS:
        mi = (p[i] + refl(p[j])) / 2.0
        out[i] = mi
        out[j] = refl(mi)
    for k in MIDLINE:
        out[k] = (p[k] + refl(p[k])) / 2.0
    return out


def persons():
    return sorted(p.name for p in DATA.glob("person_*") if p.is_dir())


def pick_frames(folder: Path):
    files = sorted([f for f in folder.iterdir()
                    if f.suffix.lower() in IMG_EXT and not f.name.startswith("._") and not f.name.startswith(".")])
    if not files:
        return []
    if len(files) <= K:
        return files
    idx = np.linspace(0, len(files) - 1, K).round().astype(int)
    return [files[i] for i in idx]


def phase_a():
    from app8.reconstruction import reconstruct_image
    CACHE.mkdir(parents=True, exist_ok=True)
    done = set()
    if ROWS.exists():
        for line in ROWS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done.add((rec["person"], rec["bin"], rec["frame"]))
    fh = ROWS.open("a", encoding="utf-8")
    started = time.time()
    new = fail = 0
    for person in persons():
        for b in BINS:
            folder = DATA / person / b
            if not folder.is_dir():
                continue
            for fpath in pick_frames(folder):
                if (person, b, fpath.name) in done:
                    continue
                try:
                    rec = reconstruct_image(fpath, device="cpu")
                    _, pts, _ = align_identity_mesh(rec)   # V_can, exp=0, center+scale
                    angles = np.asarray(rec["angles_deg"], float)
                    v17 = np.asarray(I.form_vector(pts), float)
                    v17s = np.asarray(I.form_vector(symmetrize(pts)), float)
                    univ = {k: float(val) for k, val in hc.univariate(pts).items()}
                    row = {"person": person, "bin": b, "frame": fpath.name,
                           "yaw": float(angles[1]), "pitch": float(angles[0]), "roll": float(angles[2]),
                           "v17": [float(x) for x in v17], "v17sym": [float(x) for x in v17s],
                           "univ": univ}
                except Exception as exc:  # noqa: BLE001
                    fail += 1
                    row = {"person": person, "bin": b, "frame": fpath.name, "fail": type(exc).__name__}
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                if "fail" not in row:
                    new += 1
                if (new + fail) % 30 == 0:
                    print(f"A ok={new} fail={fail} {time.time()-started:.0f}s", flush=True)
    fh.close()
    print(f"фаза A: ok={new} fail={fail}", flush=True)


def _rows():
    out = []
    for line in ROWS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if "fail" not in r:
                out.append(r)
    return out


def phase_b():
    rows = _rows()
    keys17 = list(I.FEATURE_ORDER)
    univ_keys = sorted(rows[0]["univ"].keys()) if rows else []
    print("фаза B: строк фич =", len(rows), " fail=", )
    result = {}
    # индекс: (person,bin) -> list of metric vec
    def block(name, getter):
        per = {}
        for r in rows:
            per.setdefault((r["person"], r["bin"]), []).append(getter(r))
        out = {}
        for b in BINS:
            people = [p for (p, bb) in per if bb == b]
            noise, signal = [], []
            for m in range(len(keys17) if name.startswith("v17") else len(univ_keys)):
                within = []
                means = []
                for p in people:
                    vals = np.array([x[m] for x in per[(p, b)]], float)
                    vals = vals[np.isfinite(vals)]
                    if len(vals) >= 3:
                        within.append(float(np.std(vals, ddof=1)))
                        means.append(float(np.mean(vals)))
                if within:
                    noise.append(float(np.median(within)))
                    signal.append(float(np.std(means, ddof=1)) if len(means) >= 3 else float("nan"))
            out[b] = {"noise": noise, "signal": signal, "n_people": len(people)}
        result[name] = out

    block("v17", lambda r: r["v17"])
    block("v17sym", lambda r: r["v17sym"])
    block("univ", lambda r: [r["univ"][k] for k in univ_keys])

    # inflation шума относительно frontal + сводка по v17
    def inflation(name, names):
        front = result[name].get("frontal", {}).get("noise") or []
        if not front:
            return {}
        inf = {}
        for b in BINS:
            nz = result[name][b]["noise"]
            if len(nz) == len(front) and front:
                inf[b] = round(float(np.median([nz[i] / (front[i] + 1e-9) for i in range(len(nz))])), 2)
        return inf

    summary = {
        "n_frames_ok": len(rows),
        "bins_people": {b: result["v17"][b]["n_people"] for b in BINS},
        "yaw_jitter_within_bin": {b: round(float(np.std([r["yaw"] for r in rows if r["bin"] == b])), 1) for b in BINS},
        "noise_inflation_v17": inflation("v17", keys17),
        "noise_inflation_v17sym": inflation("v17sym", keys17),
        "noise_inflation_univ": inflation("univ", univ_keys),
    }
    # таблица v17: шум по бинам (медиана within-std) для каждой метрики
    v17_tab = {}
    for i, nm in enumerate(keys17):
        v17_tab[nm] = {b: (round(result["v17"][b]["noise"][i], 4) if i < len(result["v17"][b]["noise"]) else None) for b in BINS}

    report = {"summary": summary, "v17_noise_by_bin": v17_tab,
              "v17_signal_by_bin": {nm: {b: (round(result["v17"][b]["signal"][i], 4) if i < len(result["v17"][b]["signal"]) else None) for b in BINS} for i, nm in enumerate(keys17)}}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== медианный ШУМ метрик v17 по бинам (within-person std) ===")
    print(f"{'metric':22s}" + "".join(f"{b[:5]:>7s}" for b in BINS))
    for nm in keys17:
        print(f"{nm:22s}" + "".join(f"{(v17_tab[nm][b] if v17_tab[nm][b] is not None else 0):>7.3f}" for b in BINS))
    print("\ninflation шума v17 (к frontal):", summary["noise_inflation_v17"])
    print("inflation шума v17sym(к frontal):", summary["noise_inflation_v17sym"])
    print("inflation шума univ (к frontal):", summary["noise_inflation_univ"])
    print("n_people/бин:", summary["bins_people"], "\nyaw jitter:", summary["yaw_jitter_within_bin"])
    print(f"\nОтчёт: {OUT}")


if __name__ == "__main__":
    phase_a()
    phase_b()
