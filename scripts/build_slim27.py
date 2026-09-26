"""Slim v2.7 архив для facresults (без инференса, из сохранённых alpha).

На фото: копия raw/original/texture/validation + вычисленные identity_normalized,
targetonly, expression_delta (106/134) + info.json v2.7 + detector2d где есть.
Читает старый storage read-only. Пишет в stage1_json_only_v27 (НОВАЯ папка).
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np

WORK = Path(os.environ.get("FAC_WORK", "/Users/victorkhudyakov/work"))
OLD = Path(os.environ.get("FAC_STAGE1", "/Volumes/SDCARD/storage/stage1"))
DET = WORK / "stage1_detonly_output"
NEW = Path(os.environ.get("FAC_SLIM27", "/Volumes/SDCARD/storage/stage1_json_only_v27"))


def row_rot(p, y, r):
    p, y, r = np.radians([p, y, r])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1]])
    return ((rz @ ry @ rx).T).astype(np.float64)


def wcsv(path, pts, idx, vis=None):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["landmark_id", "x", "y", "z", "vertex_index"])
        for i in range(len(idx)):
            w.writerow([i, f"{pts[i,0]:.6f}", f"{pts[i,1]:.6f}", f"{pts[i,2]:.6f}", int(idx[i])])


def main():
    m = np.load(WORK / "assets" / "face_model.npy", allow_pickle=True).item()
    u = np.asarray(m["u"], np.float64).reshape(-1)
    BID = np.asarray(m["id"], np.float64)
    BEXP = np.asarray(m["exp"], np.float64)
    tl = list(csv.DictReader(open(OLD / "main_timeline.csv")))
    NEW.mkdir(parents=True, exist_ok=True)
    ok = skip = 0
    for n, r in enumerate(tl, 1):
        d = OLD / r["photo_id"]
        out = NEW / r["photo_id"]
        if (out / "info.json").is_file():
            ok += 1
            continue
        try:
            z = np.load(d / "reconstruction.npz", allow_pickle=False)
            info = json.load(open(d / "info.json"))
            aid = np.asarray(z["alpha_id"], np.float64).reshape(-1)
            aexp = np.asarray(z["alpha_exp"], np.float64).reshape(-1)
            Vid = (u + BID @ aid).reshape(35709, 3)
            Vob = (u + BID @ aid + BEXP @ aexp).reshape(35709, 3)
            c_id = Vid.mean(0)
            S_id = float(np.sqrt(np.mean(np.sum((Vid - c_id) ** 2, 1))))
            c_ob = Vob.mean(0)
            S_ob = float(np.sqrt(np.mean(np.sum((Vob - c_ob) ** 2, 1))))
            nrm = (Vid - c_id) / S_id
            canon = float(info["chronology"]["canonical_yaw"])
            T = nrm @ row_rot(0.0, canon, 0.0)
            i106 = np.asarray(z["ldm106_vertex_indices"], np.int64).reshape(-1)
            i134 = np.asarray(z["ldm134_vertex_indices"], np.int64).reshape(-1)
            out.mkdir(parents=True, exist_ok=True)
            for f in ("ldm106_raw.csv", "ldm134_raw.csv", "ldm106_original.csv",
                      "ldm134_original.csv", "texture.json", "validation.json"):
                s = d / f
                if s.is_file():
                    shutil.copy(s, out / f)
            wcsv(out / "ldm106_identity_normalized.csv", nrm[i106], i106)
            wcsv(out / "ldm134_identity_normalized.csv", nrm[i134], i134)
            wcsv(out / "ldm106_chronology_targetonly.csv", T[i106], i106)
            wcsv(out / "ldm134_chronology_targetonly.csv", T[i134], i134)
            wcsv(out / "ldm106_expression_delta.csv", (Vob - Vid)[i106], i106)
            wcsv(out / "ldm134_expression_delta.csv", (Vob - Vid)[i134], i134)
            # detector2d где есть (по stem имени файла)
            stem = Path(r["source_filename"]).stem
            dd = DET / stem
            det_files = []
            if (dd / "ldm106_detector2d.csv").is_file():
                shutil.copy(dd / "ldm106_detector2d.csv", out / "ldm106_detector2d.csv")
                shutil.copy(dd / "detector_info.json", out / "detector_info.json")
                det_files = ["ldm106_detector2d.csv", "detector_info.json"]
            ch = info["chronology"]
            ch["applied_scale"] = S_id
            ch["applied_center"] = c_id.tolist()
            ch["applied_scale_legacy_object"] = S_ob
            ch["applied_center_legacy_object"] = c_ob.tolist()
            ch["identity_scale"] = S_id
            ch["identity_center"] = c_id.tolist()
            ch["object_scale"] = S_ob
            ch["object_center"] = c_ob.tolist()
            ch["scale_ratio_object_over_identity"] = S_ob / max(S_id, 1e-12)
            info["schema_version"] = "deeputin-photo-v2.7-contracts"
            info["deprecated_files"] = ["ldm106_chronology.csv", "ldm134_chronology.csv",
                                        "ldm106_aligned.csv", "ldm134_aligned.csv"]
            info["canonical_chronology"] = ["ldm106_chronology_targetonly.csv",
                                            "ldm134_chronology_targetonly.csv"]
            info["files"].update({
                "ldm106_identity_normalized": "ldm106_identity_normalized.csv",
                "ldm134_identity_normalized": "ldm134_identity_normalized.csv",
                "ldm106_chronology_targetonly": "ldm106_chronology_targetonly.csv",
                "ldm134_chronology_targetonly": "ldm134_chronology_targetonly.csv",
                "ldm106_expression_delta": "ldm106_expression_delta.csv",
                "ldm134_expression_delta": "ldm134_expression_delta.csv",
            })
            if det_files:
                info["files"]["ldm106_detector2d"] = det_files[0]
            json.dump(info, open(out / "info.json", "w"), ensure_ascii=False)
            ok += 1
        except Exception as exc:
            print(f"ERROR {r['photo_id']}: {exc}", flush=True)
            skip += 1
        if n % 300 == 0:
            print(f"[{n}/{len(tl)}] ok={ok} skip={skip}", flush=True)
    print(f"DONE ok={ok} skip={skip}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
