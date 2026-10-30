#!/usr/bin/env python3
import argparse, json, sys, os, hashlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # app10

from app8.reconstruction import reconstruct_image
from morphing.backend.aligner import align_identity_mesh, pose_summary
from src.pose_bins import classify_pose


def sha256_file(p: Path):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description="Извлечение мешей из списка с журналом")
    p.add_argument("--list", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--device", default="cpu")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "extract_log.jsonl"

    done = set()
    if log.exists():
        for line in log.read_text().splitlines():
            try:
                rec = json.loads(line)
                if rec.get("status") == "ok" and rec.get("image"):
                    done.add(Path(rec["image"]).resolve())
            except Exception:
                pass

    imgs = [Path(x.strip()) for x in Path(args.list).read_text().splitlines() if x.strip()]
    with log.open('a') as lf:
        for ip in imgs:
            ipr = ip.resolve()
            if ipr in done:
                print(f"SKIP_DONE {ip}"); continue
            if not ip.exists():
                lf.write(json.dumps({"image": str(ip), "status": "rejected", "reason": "missing_file"})+"\n"); lf.flush()
                print(f"MISS {ip}"); continue
            try:
                r = reconstruct_image(ip, device=args.device)
                if r is None:
                    lf.write(json.dumps({"image": str(ip), "status": "rejected", "reason": "no_face_or_decode_failed"})+"\n"); lf.flush()
                    print(f"SKIP {ip}"); continue
                v_al, ldm106, scale = align_identity_mesh(r)
                ps = pose_summary(r)
                yaw = float(ps["yaw"])
                pbin, cYaw = classify_pose(yaw)
                meta = {
                    "image": str(ip),
                    "pose_bin": pbin,
                    "yaw": yaw,
                    "canonical_yaw": float(cYaw),
                    "angles_deg": ps["angles_deg"],
                    "scale_model_units": float(scale),
                    "shape_v_aligned": list(v_al.shape),
                    "ldm106_shape": list(ldm106.shape),
                    "sha256": sha256_file(ip),
                }
                np.savez_compressed(out / f"{ip.stem}.npz",
                                    v_aligned=v_al,
                                    ldm106_aligned=ldm106,
                                    vertices_identity_only=np.asarray(r["vertices_identity_only"]),
                                    alpha_id=np.asarray(r.get("alpha_id")),
                                    alpha_exp=np.asarray(r.get("alpha_exp")),
                                    rotation_matrix=np.asarray(r.get("rotation_matrix")),
                                    translation=np.asarray(r.get("translation")),
                                    trans_params=np.asarray(r.get("trans_params")),
                                    pose_bin=pbin,
                                    yaw=yaw)
                rec = {"image": str(ip), "status": "ok", "npz": str(out / f"{ip.stem}.npz"), **meta}
                lf.write(json.dumps(rec)+"\n"); lf.flush()
                print(json.dumps(meta))
            except Exception as e:
                lf.write(json.dumps({"image": str(ip), "status": "error", "reason": str(e)})+"\n"); lf.flush()
                print(f"ERR {ip} {e}"); continue

    # rebuild manifest from log
    results = []
    for line in log.read_text().splitlines():
        try:
            rec = json.loads(line)
            if rec.get("status") == "ok":
                results.append(rec)
        except Exception:
            pass
    (out / "manifest.json").write_text(json.dumps(results, indent=2))
    print("WROTE", out / "manifest.json", "count", len(results))


if __name__ == "__main__":
    main()
