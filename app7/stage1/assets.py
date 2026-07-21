"""Save image assets, UV texture, mesh, face mask."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .geometry import to_original_image
from .masks import CHANNEL_NAMES

CROP_WIDTH = 424
CROP_HEIGHT = 500
CROP_MARGIN = 0.25


def _bbox(points: np.ndarray, shape: tuple[int, ...], margin: float = CROP_MARGIN) -> list[int]:
    h, w = shape[:2]
    p = np.asarray(points, np.float32)
    x1, y1 = np.floor(p.min(axis=0)).astype(int)
    x2, y2 = np.ceil(p.max(axis=0)).astype(int)
    bw, bh = max(x2 - x1, 1), max(y2 - y1, 1)
    dx, dy = int(round(bw * margin)), int(round(bh * margin))
    return [max(0, x1 - dx), max(0, y1 - dy), min(w, x2 + dx), min(h, y2 + dy)]


def _letterbox(image: np.ndarray, width: int = CROP_WIDTH, height: int = CROP_HEIGHT):
    h, w = image.shape[:2]
    scale = min(width / w, height / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized = cv2.resize(image, (nw, nh), interpolation=interp)
    canvas = np.zeros((height, width, image.shape[2]), image.dtype)
    ox, oy = (width - nw) // 2, (height - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return canvas, {"scale": float(scale), "offset_x": int(ox), "offset_y": int(oy)}


def save_image_assets(source: Path, bgr: np.ndarray, ldm106_original: np.ndarray,
                      out: Path) -> tuple[dict[str, str], dict[str, Any]]:
    """Save face crop + thumbnail. No original file copy (path is in info.json)."""
    files: dict[str, str] = {}
    bbox = _bbox(ldm106_original[:, :2], bgr.shape)
    x1, y1, x2, y2 = bbox
    crop = bgr[y1:y2, x1:x2]
    face, transform = _letterbox(crop)
    cv2.imwrite(str(out / "face_crop.jpg"), face, [cv2.IMWRITE_JPEG_QUALITY, 95])
    side = min(face.shape[:2])
    yy = (face.shape[0] - side) // 2
    xx = (face.shape[1] - side) // 2
    thumb = cv2.resize(face[yy:yy + side, xx:xx + side], (128, 128), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out / "thumb.jpg"), thumb, [cv2.IMWRITE_JPEG_QUALITY, 88])
    files.update({"face_crop": "face_crop.jpg", "thumbnail": "thumb.jpg"})
    return files, {"bbox": bbox, "letterbox": transform}


def technical_quality(bgr, face_bbox, mask, combined_visible):
    """Compute per-photo quality metrics for the index."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    x1, y1, x2, y2 = face_bbox
    face_gray = gray[y1:y2, x1:x2]
    lap = cv2.Laplacian(face_gray, cv2.CV_64F)
    gx = cv2.Sobel(face_gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(face_gray, cv2.CV_64F, 0, 1, ksize=3)
    vx, vy = max(float(np.var(gx)), 1e-8), max(float(np.var(gy)), 1e-8)
    return {
        "face_bbox_width": int(x2 - x1),
        "face_bbox_height": int(y2 - y1),
        "laplacian_variance": float(np.var(lap)),
        "tenengrad_mean": float(np.mean(gx * gx + gy * gy)),
        "gradient_anisotropy": float(max(vx / vy, vy / vx)),
        "combined_visible_fraction": float(np.mean(np.asarray(combined_visible, bool))),
        "skin_mask_coverage": float(np.mean(mask > 0)) if mask is not None else 0.0,
    }


def save_face_mask(bgr, hard_mask, bbox, out):
    """Save numeric mask bundle + visual preview."""
    if hard_mask is None or hard_mask.size == 0:
        return None
    if hard_mask.dtype == bool:
        hard_mask = hard_mask.astype(np.uint8) * 255
    elif hard_mask.dtype != np.uint8:
        hard_mask = np.clip(hard_mask, 0, 255).astype(np.uint8)
    x1, y1, x2, y2 = bbox
    mask_crop = hard_mask[y1:y2, x1:x2]
    face, transform = _letterbox(bgr[y1:y2, x1:x2])
    mh, mw = mask_crop.shape[:2]
    scale = transform["scale"]
    nw, nh = max(1, round(mw * scale)), max(1, round(mh * scale))
    ox, oy = transform["offset_x"], transform["offset_y"]
    mask_resized = cv2.resize(mask_crop, (nw, nh), interpolation=cv2.INTER_LINEAR)
    mask_canvas = np.zeros((500, 424), np.uint8)
    if oy + nh <= 500 and ox + nw <= 424:
        mask_canvas[oy:oy + nh, ox:ox + nw] = mask_resized
    rgba = cv2.cvtColor(face, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = mask_canvas
    cv2.imwrite(str(out / "face_mask.png"), rgba)
    mask_original_bool = hard_mask > 0
    np.savez_compressed(
        out / "face_mask.npz",
        mask_original=mask_original_bool,
        bbox_original=np.asarray([x1, y1, x2 - x1, y2 - y1], np.int32),
        original_shape=np.asarray(hard_mask.shape[:2], np.int32),
        skin_pixels_original=np.asarray([int(np.count_nonzero(mask_original_bool))], np.int64),
    )
    return {"face_mask": "face_mask.png", "face_mask_data": "face_mask.npz"}


def save_uv_and_mesh(bgr, bundle, out, uv_size, skin_mask=None):
    """Generate UV texture + OBJ mesh via uv_module."""
    from uv_module import HDUVConfig, HDUVTextureGenerator

    vertices_2d = to_original_image(bundle.vertices_image_224, bundle.trans_params)
    recon = {
        "vertices": bundle.vertices_camera,
        "vertices_3d": bundle.vertices_camera,
        "vertices_2d": vertices_2d,
        "triangles": bundle.triangles,
        "uv_coords": bundle.uv_coords,
        "normals_3d": bundle.normals_posed,
        "alpha_sh": bundle.alpha_sh if hasattr(bundle, "alpha_sh") else None,
        "skin_mask": skin_mask,
    }
    cfg = HDUVConfig(uv_size=int(uv_size), super_sample=3, enable_delighting=False,
                     force_all_triangles_visible=False, device="cpu")
    uv_render, uv_beauty, observed, confidence, aux = HDUVTextureGenerator(cfg).generate(bgr, recon)

    cv2.imwrite(str(out / "uv_texture.png"), uv_render)
    cv2.imwrite(str(out / "uv_texture_beauty.png"), uv_beauty)

    observed_bool = np.asarray(observed, bool)
    confidence_f32 = np.nan_to_num(np.asarray(confidence, np.float32), nan=0.0)
    if confidence_f32.size and float(np.max(confidence_f32)) > 1.5:
        confidence_01 = np.clip(confidence_f32 / 255.0, 0, 1)
    else:
        confidence_01 = np.clip(confidence_f32, 0, 1)
    valid_mask = observed_bool & (confidence_01 >= 0.50)
    filled_mask = np.asarray(aux.get("uv_synthetic_mask", np.zeros_like(observed_bool)), bool)

    np.savez_compressed(
        out / "uv.npz",
        texture_bgr=np.asarray(uv_render, np.uint8),
        confidence=confidence_01.astype(np.float16),
        observed_mask=observed_bool,
        filled_mask=filled_mask,
        valid_mask=valid_mask,
        uv_coords=np.asarray(bundle.uv_coords, np.float32),
        semantics=np.asarray("single visual UV render; skin evidence is on original pixels"),
    )
    _write_obj(out / "mesh.obj", out / "mesh.mtl",
               bundle.vertices_object_normalized, bundle.normals_object,
               bundle.uv_coords, bundle.triangles, "uv_texture.png")

    uv_meta = {
        "observed_coverage": float(np.mean(observed_bool)),
        "valid_coverage": float(np.mean(valid_mask)),
    }
    files = {"uv_texture": "uv_texture.png", "uv_data": "uv.npz", "mesh": "mesh.obj", "mesh_material": "mesh.mtl"}
    return files, uv_meta


def _write_obj(obj_path, mtl_path, vertices, normals, uv, triangles, texture_name="uv_texture.png"):
    mtl_path.write_text(
        f"newmtl face_material\nKa 0.2 0.2 0.2\nKd 0.8 0.8 0.8\nKs 0 0 0\nillum 2\nmap_Kd {texture_name}\n",
        encoding="utf-8")
    with obj_path.open("w", encoding="utf-8") as f:
        f.write("mtllib mesh.mtl\nusemtl face_material\n")
        for x, y, z in vertices:
            f.write(f"v {x:.8f} {y:.8f} {z:.8f}\n")
        for u, v in uv[:, :2]:
            f.write(f"vt {u:.8f} {v:.8f}\n")
        for x, y, z in normals:
            f.write(f"vn {x:.8f} {y:.8f} {z:.8f}\n")
        for tri in triangles:
            a, b, c = (int(x) + 1 for x in tri)
            f.write(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n")
