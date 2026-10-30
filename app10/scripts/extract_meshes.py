#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app8.reconstruction import reconstruct_image
from morphing.backend.aligner import align_identity_mesh, pose_summary


def main():
    p = argparse.ArgumentParser(description="Извлечение мешей для калибровки на одном человеке")
    p.add_argument("--images", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--device", default="cpu")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    results = []
    for img in args.images:
        ip = Path(img)
        r = reconstruct_image(ip, device=args.device)
        if r is None:
            print(f"SKIP {ip}")
            continue
        v_al, ldm106, scale = align_identity_mesh(r)
        ps = pose_summary(r)
        meta = {
            "image": str(ip),
            "pose_bin": ps["pose_bin"],
            "yaw": ps["yaw"],
            "canonical_yaw": ps["canonical_yaw"],
            "angles_deg": ps["angles_deg"],
            "scale_model_units": float(scale),
            "shape_v_aligned": v_al.shape,
            "ldm106_shape": ldm106.shape,
        }
        np.savez_compressed(out / f"{ip.stem}.npz",
                            v_aligned=v_al,
                            ldm106_aligned=ldm106,
                            vertices_identity_only=np.asarray(r["vertices_identity_only"]),
                            **{k: np.array(v) if isinstance(v, list) else v for k,v in meta.items()})
        results.append(meta)
        print(json.dumps(meta))
    (out / "manifest.json").write_text(json.dumps(results, indent=2))
    print("WROTE", out / "manifest.json")


if __name__ == "__main__":
    main()
