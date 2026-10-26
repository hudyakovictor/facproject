#!/usr/bin/env python
"""Этап A: выгрузка по ВСЕМ фронтальным кадрам /Volumes/SDCARD/calibration_rakurs.

Для каждого кадра сохраняем 106 точек в трёх состояниях юстировки (это и есть
«до/после выравнивания» без каких-либо допущений):
  cam    = vertices_camera[idx]        поза НЕ убрана (камерное пространство)
  two_d  = vertices_2d_orig[idx]       плоскость фото (z=0)
  canon  = vertices_identity_only[idx] текущий пайплайн: поза убрана + центр/масштаб
Все три пропускаем через одну и ту же нормировку (центр в 0, max-радиус = 1), чтобы
расстояния между ними имели смысл. Плюс углы и rotation_matrix (нужны для вариантов
с доворотом). Кэш resumable: строки ключуются по (person, frame).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path("/Users/victorkhudyakov/work")
DATA = Path("/Volumes/SDCARD/calibration_rakurs")
CACHE = ROOT / ".runtime" / "level_cache"
ROWS = CACHE / "frames.jsonl"
# фронтал брали целиком (нужны ровные кадры), остальные бины - равномерно по 12
BIN_CAP = {"frontal": 0, "left_light": 12, "right_light": 12, "left_mid": 12, "right_mid": 12,
           "left_deep": 12, "right_deep": 12, "left_profile": 12, "right_profile": 12}
BINS = list(BIN_CAP)


def norm(p):
    p = np.asarray(p, float)
    p = p - p.mean(axis=0)
    s = float(np.max(np.linalg.norm(p, axis=1)))
    return (p / s if s > 1e-6 else p), [round(x, 5) for x in p.ravel().tolist()]


def frames_for(person, bin_name):
    folder = DATA / person / bin_name
    out = [f for f in sorted(folder.iterdir())
           if f.suffix.lower() in (".jpg", ".jpeg", ".png") and not f.name.startswith(".")]
    cap = BIN_CAP.get(bin_name, 0)
    if cap and len(out) > cap:
        idx = np.linspace(0, len(out) - 1, cap).round().astype(int)
        out = [out[i] for i in idx]
    return out


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    done = set()
    if ROWS.exists():
        for line in ROWS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["person"], r.get("bin", "frontal"), r["frame"]))
    people = sorted(p.name for p in DATA.glob("person_*") if p.is_dir())
    fh = ROWS.open("a", encoding="utf-8")
    t0 = time.time()
    new = fail = 0
    from app8.reconstruction import reconstruct_image
    from morphing.backend import identity as I
    from morphing.backend.aligner import align_identity_mesh
    only = set(sys.argv[1:])
    for person in people:
        for bin_name in BINS:
            if only and bin_name not in only:
                continue
            if not (DATA / person / bin_name).is_dir():
                continue
            for f in frames_for(person, bin_name):
                if (person, bin_name, f.name) in done:
                    continue
                try:
                    rec = reconstruct_image(f, device="cpu")
                    idx = np.asarray(rec["ldm106_indices"], np.int64)
                    ang = np.asarray(rec["angles_deg"], float)
                    row = {"person": person, "bin": bin_name, "frame": f.name,
                           "yaw": float(ang[1]), "pitch": float(ang[0]), "roll": float(ang[2]),
                           "R": [round(float(x), 5) for x in np.asarray(rec["rotation_matrix"], float).ravel()]}
                    p2d = np.asarray(rec["vertices_2d_orig"], float)[idx]
                    p2d = np.hstack([p2d[:, :1], -p2d[:, 1:2], np.zeros((len(p2d), 1))])
                    for key, arr in (("cam", np.asarray(rec["vertices_camera"], float)[idx]),
                                     ("two_d", p2d),
                                     ("canon", np.asarray(rec["vertices_identity_only"], float)[idx])):
                        _, row[key] = norm(arr)
                    _, vcan, _ = align_identity_mesh(rec)
                    row["v17"] = [float(x) for x in np.asarray(I.form_vector(vcan), float)]
                except Exception as exc:  # noqa: BLE001
                    fail += 1
                    row = {"person": person, "bin": bin_name, "frame": f.name, "fail": type(exc).__name__}
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                if "fail" not in row:
                    new += 1
                if (new + fail) % 20 == 0:
                    print(f"ok={new} fail={fail} {time.time()-t0:.0f}s", flush=True)
    fh.close()
    print(f"готово: ok={new} fail={fail} за {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
