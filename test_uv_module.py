#!/usr/bin/env python3
"""Test uv_module v3 with 3DDFA-V3 reconstruction on 1.jpg and 2.jpg."""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "3ddfav3"))

import cv2
import numpy as np
from PIL import Image

from face_box import face_box
from model.recon import face_model

sys.path.insert(0, str(Path(__file__).parent))
from uv_module.config import HDUVConfig
from uv_module.generator import HDUVTextureGenerator


def extract_recon_dict(results, trans_params, original_img):
    H0, W0 = original_img.size[1], original_img.size[0]
    v2d_224 = results['v2d'][0]
    w0, h0, s, t, target_size = (
        trans_params[0], trans_params[1], trans_params[2],
        [trans_params[3], trans_params[4]], 224
    )
    w = int(w0 * s)
    h = int(h0 * s)
    left = int(w / 2 - target_size / 2 + float((t[0] - w0 / 2) * s))
    up = int(h / 2 - target_size / 2 + float((h0 / 2 - t[1]) * s))
    # v2d from 3DDFA is bottom-origin (y=0 at bottom) in 224x224 crop space.
    # The crop offset (left, up) is in top-origin resized-image space.
    # Steps: flip y to top-origin in crop -> add offset -> scale to orig -> flip back to bottom-origin.
    v2d_original = v2d_224.copy()
    v2d_original[:, 0] = (v2d_224[:, 0] + left) / w * W0
    y_top_224 = (target_size - 1) - v2d_224[:, 1]
    y_top_orig = (y_top_224 + up) / h * H0
    v2d_original[:, 1] = (H0 - 1) - y_top_orig

    v3d = results['v3d'][0]
    triangles = results['tri']
    uv_coords = results['uv_coords']

    def compute_normals(vertices, triangles):
        v1 = vertices[triangles[:, 0]]
        v2 = vertices[triangles[:, 1]]
        v3 = vertices[triangles[:, 2]]
        e1 = v2 - v1
        e2 = v3 - v1
        fn = np.cross(e1, e2)
        fn = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-9)
        vn = np.zeros_like(vertices)
        for i in range(triangles.shape[0]):
            for j in range(3):
                vn[triangles[i, j]] += fn[i]
        vn = vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-9)
        return vn

    normals = compute_normals(v3d, triangles)
    return {
        'vertices_2d': v2d_original,
        'vertices_3d': v3d,
        'vertices': v3d,
        'triangles': triangles,
        'uv_coords': uv_coords,
        'normals_3d': normals,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', nargs='+', default=sorted(
        p.as_posix() for p in Path('/Users/victorkhudyakov/work/testphoto').glob('*.jpg')
    ) if Path('/Users/victorkhudyakov/work/testphoto').exists() else [
        '/Users/victorkhudyakov/work/1.jpg',
        '/Users/victorkhudyakov/work/2.jpg',
    ])
    parser.add_argument('--output', default='/Users/victorkhudyakov/work/tests')
    parser.add_argument('--uv_size', type=int, default=1000)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--detector', default='retinaface')
    parser.add_argument('--iscrop', type=lambda x: x.lower() in ['true', '1'], default=True)
    parser.add_argument('--backbone', default='resnet50')
    parser.add_argument('--ldm68', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--ldm106', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--ldm106_2d', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--ldm134', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--seg', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--seg_visible', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--useTex', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--extractTex', type=lambda x: x.lower() in ['true', '1'], default=False)
    args = parser.parse_args()

    print("Initializing 3DDFA-V3 recon model...")
    recon_model = face_model(args)
    facebox_detector = face_box(args).detector

    cfg = HDUVConfig(uv_size=args.uv_size, super_sample=2)
    gen = HDUVTextureGenerator(cfg)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for img_path in args.input:
        print(f"\n{'='*60}")
        print(f"Processing: {img_path}")
        name = Path(img_path).stem

        im = Image.open(img_path).convert('RGB')
        print(f"  Image size: {im.size}")

        trans_params, im_tensor = facebox_detector(im)
        print(f"  Trans params: {trans_params}")

        recon_model.input_img = im_tensor.to(args.device)
        results = recon_model.forward()
        print(f"  Reconstruction done. Keys: {list(results.keys())}")

        recon_dict = extract_recon_dict(results, trans_params, im)
        img_bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

        print(f"  Generating UV textures ({cfg.uv_size}x{cfg.uv_size})...")
        analysis, beauty, observed, confidence, aux = gen.generate(img_bgr, recon_dict)

        outdir = output_dir / name
        outdir.mkdir(parents=True, exist_ok=True)

        cv2.imwrite(str(outdir / "uv_analysis.png"), analysis)
        cv2.imwrite(str(outdir / "uv_synthetic.png"), beauty)
        cv2.imwrite(str(outdir / "uv_observed.png"), (observed.astype(np.uint8) * 255))
        cv2.imwrite(str(outdir / "uv_synthetic_mask.png"),
                    (aux['synthetic_mask'].astype(np.uint8) * 255))
        cv2.imwrite(str(outdir / "uv_confidence.png"),
                    (np.clip(confidence * 255, 0, 255).astype(np.uint8)))
        if 'analysis_view' in aux:
            cv2.imwrite(str(outdir / "uv_analysis_view.png"), aux['analysis_view'])

        print(f"  Saved to: {outdir}/")
        print(f"    - uv_analysis.png (analytic, real pixels only)")
        print(f"    - uv_synthetic.png (morph, with symmetric fill)")
        print(f"    - uv_observed.png (observed mask)")
        print(f"    - uv_synthetic_mask.png (synthetic region mask)")
        print(f"    - uv_confidence.png (per-pixel confidence)")
        if 'analysis_view' in aux:
            print(f"    - uv_analysis_view.png (enhanced view for human inspection)")

    print(f"\nAll done. Results in: {output_dir}")


if __name__ == '__main__':
    main()
