#!/usr/bin/env python3
import argparse, json, sys, os, hashlib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app8.reconstruction import reconstruct_image
from morphing.backend.aligner import align_identity_mesh, pose_summary


def sha256_file(p: Path):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description="Экстракция фронтальных фото по людям")
    p.add_argument("--src", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--device", default="cpu")
    p.add_argument("--max-per-person", type=int, default=3)
    args = p.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # найти фронтальные фото
    imgs = []
    for person in sorted(src.iterdir()):
        if not person.is_dir(): continue
        for sub in ['frontal']:
            sp = person / sub
            if sp.exists():
                for f in sp.glob('*.jpg'):
                    imgs.append((person.name, f))
                for f in sp.glob('*.png'):
                    imgs.append((person.name, f))
                for f in sp.glob('*.jpeg'):
                    imgs.append((person.name, f))
    imgs = imgs[:args.max_per_person * 10]  # взять немного для превью

    count = 0
    for pid, ip in imgs:
        if count >= args.max_per_person * 6:  # ограничим
            pass
        r = reconstruct_image(ip, device=args.device)
        if r is None:
            print(f"SKIP {pid} {ip.name}")
            continue
        v_al, ldm106, scale = align_identity_mesh(r)
        ps = pose_summary(r)
        np.savez_compressed(out / f"{pid}_{ip.stem}.npz",
                            v_aligned=v_al,
                            ldm106_aligned=ldm106,
                            vertices_identity_only=np.asarray(r["vertices_identity_only"]),
                            alpha_id=np.asarray(r.get("alpha_id")),
                            alpha_exp=np.asarray(r.get("alpha_exp")),
                            rotation_matrix=np.asarray(r.get("rotation_matrix")),
                            translation=np.asarray(r.get("translation")),
                            trans_params=np.asarray(r.get("trans_params")),
                            person_id=pid,
                            image=str(ip),
                            yaw=float(ps["yaw"]),
                            pose_bin=ps["pose_bin"],
                            angles_deg=ps["angles_deg"])
        print(f"OK {pid} {ip.name} yaw={ps['yaw']:.2f}")
        count += 1
        if count >= args.max_per_person * 6:
            break

    print(f"DONE count={count}")


if __name__ == "__main__":
    main()
