"""app6/scripts/render_skin_zone_atlas.py

Генерирует КАНОНИЧЕСКИЙ атлас зон кожи лица ОДИН РАЗ на версию атласа:
  app6/atlas/skin_zone_atlas_v1/
    skin_zone_atlas_v1.json
    skin_zone_atlas_triangles.npz
    skin_zone_atlas_uv.png
    skin_zone_atlas_pose_policy.csv

UV-координаты и треугольники берутся из любой реконструкции (reconstruction.npz)
на топологии BFM-35709. Атлас НЕ зависит от конкретного фото — он строится
один раз и затем проецируется на каждое фото в Stage 1 (см. skin_zone_atlas.py).

Использование:
  python app6/scripts/render_skin_zone_atlas.py \
      --recon /tmp/stage1_test/2000_06_14__21263917/reconstruction.npz \
      --atlas-dir app6/atlas/skin_zone_atlas_v1
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from app6.stage1.skin_zone_atlas import generate_canonical_atlas


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate canonical skin zone atlas (once).")
    ap.add_argument("--recon", required=True, help="Path to a reconstruction.npz with uv_coords + triangles")
    ap.add_argument("--face-model", default="3ddfa_v3/assets/face_model.npy", help="face_model.npy for the 3D mesh UV unwrap background")
    ap.add_argument("--atlas-dir", default="app6/atlas/skin_zone_atlas_v1")
    ap.add_argument("--png-size", type=int, default=1024)
    args = ap.parse_args()

    recon = np.load(args.recon, allow_pickle=True)
    uv_coords = recon["uv_coords"].astype(np.float32)
    triangles = recon["triangles"].astype(np.int64)

    atlas_dir = Path(args.atlas_dir)
    result = generate_canonical_atlas(
        atlas_dir, uv_coords, triangles, png_size=args.png_size,
        face_model_path=Path(args.face_model),
    )
    primary = result["primary_triangle_zone"]
    covered = int(np.count_nonzero(primary))
    print(f"Atlas written to {atlas_dir}")
    print(f"  triangles total: {triangles.shape[0]}")
    print(f"  triangles assigned to a zone: {covered}")
    print(f"  background triangles: {triangles.shape[0] - covered}")
    print(f"  zone count: {len(result['zone_names'])}")


if __name__ == "__main__":
    main()
