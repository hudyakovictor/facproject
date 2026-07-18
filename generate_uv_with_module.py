#!/usr/bin/env python
"""
Integration script for using uv_module_v1/v2 with 3DDFA-V3 reconstruction.

This script takes 3DDFA-V3 reconstruction results and generates high-quality
UV textures using the standalone UV texture generation modules.

Usage:
    python generate_uv_with_module.py --input /path/to/image.jpg --uv_module v1 --output /path/to/output
"""
import argparse
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

# Add 3DDFA-V3 package root to path for imports
sys.path.insert(0, str(Path(__file__).parent / "3ddfav3"))

from face_box import face_box
from model.recon import face_model
from util.preprocess import get_data_path

def convert_3ddfa_to_uv_module_format(recon_results, trans_params, original_img):
    """
    Convert 3DDFA-V3 reconstruction results to uv_module format.
    
    Args:
        recon_results: dict from 3DDFA-V3 forward pass
        trans_params: transformation parameters from face detection
        original_img: original PIL image
        
    Returns:
        recon_dict: dict in uv_module expected format
    """
    h, w = original_img.size[1], original_img.size[0]
    
    # Convert vertices_2d back to original image coordinates
    v2d_224 = recon_results['v2d'][0]  # (N, 2) in 224x224 space
    v2d_original = v2d_224.copy()
    
    # Inverse transformation
    w0, h0, s, t, target_size = trans_params[0], trans_params[1], trans_params[2], [trans_params[3], trans_params[4]], 224
    
    img_w = int(w0 * s)
    img_h = int(h0 * s)
    left = int(img_w / 2 - target_size / 2 + float((t[0] - w0 / 2) * s))
    up = int(img_h / 2 - target_size / 2 + float((h0 / 2 - t[1]) * s))
    
    v2d_original[:, 0] = (v2d_224[:, 0] + left) / img_w * w0
    v2d_original[:, 1] = (v2d_224[:, 1] + up) / img_h * h0
    
    # Get 3D vertices (already in camera space)
    v3d = recon_results['v3d'][0]
    
    # Get triangles
    triangles = recon_results['tri']
    
    # Get UV coordinates
    uv_coords = recon_results['uv_coords']
    
    # Compute normals from 3D vertices
    def compute_normals(vertices, triangles):
        v1 = vertices[triangles[:, 0]]
        v2 = vertices[triangles[:, 1]]
        v3 = vertices[triangles[:, 2]]
        e1 = v2 - v1
        e2 = v3 - v1
        face_normals = np.cross(e1, e2)
        face_normals = face_normals / (np.linalg.norm(face_normals, axis=1, keepdims=True) + 1e-9)
        
        # Accumulate to vertices
        vertex_normals = np.zeros_like(vertices)
        for i in range(triangles.shape[0]):
            for j in range(3):
                vertex_normals[triangles[i, j]] += face_normals[i]
        
        # Normalize
        vertex_normals = vertex_normals / (np.linalg.norm(vertex_normals, axis=1, keepdims=True) + 1e-9)
        return vertex_normals
    
    normals_3d = compute_normals(v3d, triangles)
    
    recon_dict = {
        'vertices_2d': v2d_original,
        'vertices_3d': v3d,
        'vertices': v3d,
        'triangles': triangles,
        'uv_coords': uv_coords,
        'normals_3d': normals_3d,
        'alpha_sh': None,  # SH coefficients not available in basic reconstruction
    }
    
    return recon_dict

def main(args):
    print(f"Using UV module: {args.uv_module}")
    
    # Import the appropriate UV module
    if args.uv_module == 'v1':
        sys.path.insert(0, str(Path(__file__).parent / "uv_module_v1"))
        from config import HDUVConfig
        from generator import HDUVTextureGenerator
    elif args.uv_module == 'v2':
        sys.path.insert(0, str(Path(__file__).parent / "uv_module_v2"))
        from config import HDUVConfig
        from generator import HDUVTextureGenerator
    else:
        raise ValueError(f"Unknown UV module: {args.uv_module}")
    
    # Initialize 3DDFA-V3 reconstruction
    print("Initializing 3DDFA-V3 reconstruction...")
    recon_model = face_model(args)
    facebox_detector = face_box(args).detector
    
    # Load image
    print(f"Loading image: {args.input}")
    im = Image.open(args.input).convert('RGB')
    trans_params, im_tensor = facebox_detector(im)
    
    # Run reconstruction
    print("Running 3DDFA-V3 reconstruction...")
    recon_model.input_img = im_tensor.to(args.device)
    results = recon_model.forward()
    
    # Convert to UV module format
    print("Converting to UV module format...")
    recon_dict = convert_3ddfa_to_uv_module_format(results, trans_params, im)
    
    # Convert image to BGR for OpenCV
    img_bgr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    
    # Configure UV texture generator
    cfg = HDUVConfig(
        uv_size=args.uv_size,
        super_sample=args.super_sample,
        enable_delighting=False,
        mirror_fill=True,
        cache_dir=args.cache_dir
    )
    
    print(f"Generating UV textures (size={cfg.uv_size}, super_sample={cfg.super_sample})...")
    gen = HDUVTextureGenerator(cfg)
    
    # Generate textures
    analysis, beauty, observed, confidence, aux = gen.generate(img_bgr, recon_dict)
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save results
    output_name = Path(args.input).stem
    
    # Save analytical texture (real pixels only)
    analysis_path = output_dir / f"{output_name}_uv_analysis.png"
    cv2.imwrite(str(analysis_path), analysis)
    print(f"Saved analytical texture: {analysis_path}")
    
    # Save synthetic texture (symmetric completion)
    beauty_path = output_dir / f"{output_name}_uv_synthetic.png"
    cv2.imwrite(str(beauty_path), beauty)
    print(f"Saved synthetic texture: {beauty_path}")
    
    # Save masks
    observed_path = output_dir / f"{output_name}_uv_observed.png"
    cv2.imwrite(str(observed_path), (observed.astype(np.uint8) * 255))
    print(f"Saved observed mask: {observed_path}")
    
    synthetic_mask_path = output_dir / f"{output_name}_uv_synthetic_mask.png"
    cv2.imwrite(str(synthetic_mask_path), (aux['synthetic_mask'].astype(np.uint8) * 255))
    print(f"Saved synthetic mask: {synthetic_mask_path}")
    
    # Save confidence as visualization
    confidence_path = output_dir / f"{output_name}_uv_confidence.png"
    cv2.imwrite(str(confidence_path), (confidence * 255).astype(np.uint8))
    print(f"Saved confidence: {confidence_path}")
    
    print("\nUV texture generation complete!")
    print(f"Output directory: {output_dir}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate UV textures using uv_module with 3DDFA-V3')
    parser.add_argument('--input', type=str, required=True, help='Input image path')
    parser.add_argument('--output', type=str, default='/Users/victorkhudyakov/work/tests', help='Output directory')
    parser.add_argument('--uv_module', type=str, default='v1', choices=['v1', 'v2'], help='UV module version')
    parser.add_argument('--uv_size', type=int, default=1000, help='UV texture size (max 1000)')
    parser.add_argument('--super_sample', type=int, default=3, help='Super-sampling factor')
    parser.add_argument('--cache_dir', type=str, default=None, help='Cache directory for UV raster')
    parser.add_argument('--device', type=str, default='cpu', help='Device (cpu/cuda)')
    parser.add_argument('--detector', type=str, default='retinaface', help='Face detector')
    parser.add_argument('--iscrop', type=lambda x: x.lower() in ['true', '1'], default=True)
    parser.add_argument('--backbone', type=str, default='resnet50', help='Backbone network')
    # Additional arguments required by face_model
    parser.add_argument('--ldm68', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--ldm106', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--ldm106_2d', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--ldm134', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--seg', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--seg_visible', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--useTex', type=lambda x: x.lower() in ['true', '1'], default=False)
    parser.add_argument('--extractTex', type=lambda x: x.lower() in ['true', '1'], default=False)
    
    args = parser.parse_args()
    main(args)
