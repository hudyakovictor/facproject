from __future__ import annotations
from .masks import CHANNEL_NAMES
import shutil
from pathlib import Path
from typing import Any
from .status_logger import log_status, log_blocker, log_warning

import cv2
import numpy as np

from .geometry import to_original_image

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
    x1, y1 = max(0, x1 - dx), max(0, y1 - dy)
    x2, y2 = min(w, x2 + dx), min(h, y2 + dy)
    if x2 <= x1 or y2 <= y1:
        raise ValueError("invalid landmark crop")
    return [x1, y1, x2 - x1, y2 - y1]


def _letterbox(image: np.ndarray, width: int = CROP_WIDTH, height: int = CROP_HEIGHT) -> tuple[np.ndarray, dict[str, float]]:
    h, w = image.shape[:2]
    scale = min(width / w, height / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized = cv2.resize(image, (nw, nh), interpolation=interpolation)
    canvas = np.zeros((height, width, image.shape[2]), image.dtype)
    ox, oy = (width - nw) // 2, (height - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return canvas, {"scale": float(scale), "offset_x": int(ox), "offset_y": int(oy), "content_width": int(nw), "content_height": int(nh)}


def save_image_assets(source: Path, bgr: np.ndarray, ldm106_original: np.ndarray, out: Path, save_original: bool = True) -> tuple[dict[str, str], dict[str, Any]]:
    log_status("save_image_assets", "complete")
    files: dict[str, str] = {}
    if save_original:
        original_name = "original" + source.suffix.lower()
        shutil.copy2(source, out / original_name)
        files["original"] = original_name
    bbox = _bbox(ldm106_original[:, :2], bgr.shape)
    x, y, w, h = bbox
    crop = bgr[y:y + h, x:x + w]
    face, transform = _letterbox(crop)
    if not cv2.imwrite(str(out / "face_crop.jpg"), face, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise OSError("failed to write face_crop.jpg")
    side = min(face.shape[:2]); yy = (face.shape[0] - side) // 2; xx = (face.shape[1] - side) // 2
    thumb = cv2.resize(face[yy:yy + side, xx:xx + side], (128, 128), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out / "thumb.jpg"), thumb, [cv2.IMWRITE_JPEG_QUALITY, 88])
    files.update({"face_crop": "face_crop.jpg", "thumbnail": "thumb.jpg"})
    return files, {"bbox_original": bbox, "letterbox": transform, "crop_source": "ldm106_projection"}


def technical_quality(bgr: np.ndarray, face_bbox: list[int], mask: np.ndarray | None, combined_visible: np.ndarray) -> dict[str, float | int]:
    log_status("technical_quality", "complete")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    x, y, w, h = face_bbox
    face_gray = gray[y:y + h, x:x + w]
    lap = cv2.Laplacian(face_gray, cv2.CV_64F)
    gx = cv2.Sobel(face_gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(face_gray, cv2.CV_64F, 0, 1, ksize=3)
    med = cv2.medianBlur(face_gray, 3)
    diff = np.abs(face_gray.astype(np.float32) - med.astype(np.float32))
    vx, vy = max(float(np.var(gx)), 1e-8), max(float(np.var(gy)), 1e-8)
    out: dict[str, float | int] = {
        "face_bbox_width": int(w), "face_bbox_height": int(h),
        "face_bbox_area_ratio": float(w * h / max(bgr.shape[0] * bgr.shape[1], 1)),
        "laplacian_variance": float(np.var(lap)),
        "tenengrad_mean": float(np.mean(gx * gx + gy * gy)),
        "noise_residual_mean": float(np.mean(diff)),
        "gradient_anisotropy": float(max(vx / vy, vy / vx)),
        "combined_visible_fraction": float(np.mean(np.asarray(combined_visible, bool))),
    }
    out["skin_mask_coverage"] = float(np.mean(mask > 0)) if mask is not None else 0.0
    return out


def save_uv_and_mesh(bgr: np.ndarray, bundle: Any, out: Path, uv_size: int, skin_mask: np.ndarray | None = None, super_sample: int = 3, save_mesh: bool = True) -> tuple[dict[str, str], dict[str, np.ndarray], dict[str, float]]:
    log_status("save_uv_and_mesh", "complete")
    from uv_module import HDUVConfig, HDUVTextureGenerator

    vertices_2d = to_original_image(bundle.vertices_image_224, bundle.trans_params)
    recon = {
        "vertices": bundle.vertices_camera,
        "vertices_3d": bundle.vertices_camera,
        "vertices_2d": vertices_2d,
        "triangles": bundle.triangles,
        "uv_coords": bundle.uv_coords,
        "normals_3d": bundle.normals_posed,
        "alpha_sh": bundle.alpha_sh,
        "skin_mask": skin_mask,  # Pass skin_mask INSIDE recon dict (generator reads from here)
    }
    cfg = HDUVConfig(uv_size=int(uv_size), super_sample=super_sample, enable_delighting=False, force_all_triangles_visible=False, device="cpu")
    uv_render, uv_beauty, observed, confidence, aux = HDUVTextureGenerator(cfg).generate(bgr, recon)
    out.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(out / "uv_texture.png"), uv_render):
        raise OSError(f"failed to write uv_texture.png to {out / 'uv_texture.png'}")
    # UV is visualization/correspondence only. Anatomical zones, wrinkles and
    # forensic evidence are produced by app6.stage1.skin.pipeline in native
    # photo space; no disabled placeholder and no silent legacy-atlas fallback.

    # Confidence is stored in uv.npz with exact arrays for future analysis.
    # (uv_confidence.png visual preview is no longer generated.)
    observed_bool = np.asarray(observed, bool)
    is_original_bool = np.asarray(aux.get("uv_is_original", observed), bool)
    confidence_f32 = np.asarray(confidence, np.float32)
    confidence_f32 = np.nan_to_num(confidence_f32, nan=0.0, posinf=1.0, neginf=0.0)
    # Some generators may return 0..255, others 0..1. Normalize defensively.
    if confidence_f32.size and float(np.max(confidence_f32)) > 1.5:
        confidence_01 = np.clip(confidence_f32 / 255.0, 0.0, 1.0)
    else:
        confidence_01 = np.clip(confidence_f32, 0.0, 1.0)
    confidence_u8 = np.round(confidence_01 * 255.0).astype(np.uint8)
    valid_threshold = 0.50
    valid_mask = observed_bool & is_original_bool & (confidence_01 >= valid_threshold)

    tri_visibility = np.asarray(aux.get("tri_visibility", []), np.float16)
    # Exactly one UV texture is serialized. Provenance masks identify observed
    # and visually filled texels, but neither is used by skin analyzers.
    filled_mask = np.asarray(aux.get("uv_synthetic_mask", np.zeros_like(observed_bool)), bool)
    np.savez_compressed(
        out / "uv.npz",
        texture_bgr=np.asarray(uv_render, np.uint8),
        confidence=confidence_01.astype(np.float16),
        observed_mask=observed_bool,
        filled_mask=filled_mask,
        is_original_mask=is_original_bool,
        valid_mask=valid_mask,
        tri_visibility=tri_visibility,
        uv_shape=np.asarray(observed_bool.shape, np.int32),
        valid_threshold=np.asarray([valid_threshold], np.float32),
        uv_coords=np.asarray(bundle.uv_coords, np.float32),
        semantics=np.asarray(
            "single visual UV render for 3D/morphing only; skin evidence is measured "
            "on original photo pixels through face_mask and native surface projection"
        ),
    )

    uv_arrays = {
        "uv_observed_mask_packbits": np.packbits(observed_bool.astype(np.uint8).reshape(-1), bitorder="little"),
        "uv_is_original_packbits": np.packbits(is_original_bool.astype(np.uint8).reshape(-1), bitorder="little"),
        "uv_valid_mask_packbits": np.packbits(valid_mask.astype(np.uint8).reshape(-1), bitorder="little"),
        "uv_confidence": confidence_01.astype(np.float16),
        "tri_visibility": tri_visibility,
        "uv_shape": np.asarray(observed_bool.shape, np.int32),
    }
    uv_meta = {
        "observed_coverage": float(np.mean(observed_bool)),
        "original_coverage": float(np.mean(is_original_bool)),
        "valid_coverage": float(np.mean(valid_mask)),
        "valid_threshold": float(valid_threshold),
        "mean_confidence_observed": float(np.mean(confidence_01[observed_bool])) if np.any(observed_bool) else 0.0,
        "confidence_semantics": "uv_confidence.png is a binary visual valid mask; uv.npz stores UV texture pixels, continuous 0..1 confidence, component masks, UV coords and triangle visibility; valid_mask = observed AND original AND confidence >= threshold",
        "render_fill_policy": "contralateral mirror plus tiny-hole inpaint inside the single visualization render; never evidence",
        "uv_product_count": 1,
        "native_skin_contract": "all skin evidence uses original photo pixels through face_mask in app6.stage1.skin.pipeline",
    }

    files = {
        "uv_texture": "uv_texture.png",
        "uv_data": "uv.npz",
    }
    # Only save mesh files if requested (for morphing/visualization)
    if save_mesh:
        _write_obj(out / "mesh.obj", out / "mesh.mtl", bundle.vertices_object_normalized, bundle.normals_object, bundle.uv_coords, bundle.triangles, "uv_texture.png")
        files["mesh"] = "mesh.obj"
        files["mesh_material"] = "mesh.mtl"
    return files, uv_arrays, uv_meta


def _write_obj(obj_path: Path, mtl_path: Path, vertices: np.ndarray, normals: np.ndarray, uv: np.ndarray, triangles: np.ndarray, texture_name: str = "uv_texture.png") -> None:
    if len(vertices) != len(normals) or len(vertices) != len(uv):
        raise ValueError("OBJ vertex/normal/UV counts differ")
    mtl_path.write_text(f"newmtl face_material\nKa 0.2 0.2 0.2\nKd 0.8 0.8 0.8\nKs 0 0 0\nillum 2\nmap_Kd {texture_name}\n", encoding="utf-8")
    with obj_path.open("w", encoding="utf-8") as f:
        f.write("mtllib mesh.mtl\nusemtl face_material\n")
        for x, y, z in vertices: f.write(f"v {x:.8f} {y:.8f} {z:.8f}\n")
        for u, v in uv[:, :2]: f.write(f"vt {u:.8f} {v:.8f}\n")
        for x, y, z in normals: f.write(f"vn {x:.8f} {y:.8f} {z:.8f}\n")
        for tri in triangles:
            a, b, c = (int(x) + 1 for x in tri)
            f.write(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n")


def save_face_mask(bgr: np.ndarray, hard_mask: np.ndarray | None, bbox: list[int], out: Path) -> dict[str, str] | None:
    log_status("save_face_mask", "complete")
    """🎯 CRITICAL → Создание face_mask.png и face_mask.npz.

    face_mask — это ОСНОВНАЯ маска для skin analysis. Все текстурные анализы
    используют именно эту маску (НЕ UV текстуру!).

    🔗 DEPENDS ON:
      - engine._one() — вызывается после build_mask_bundle
      - mask.hard_original — binary mask в original resolution

    ⚠️ IN PROGRESS:
      - Нет проверки что маска покрывает достаточно кожи
      - Нет проверки что bbox корректный (не выходит за изображение)

    💡 NOTE:
      - face_mask.png — RGBA визуальный превью (424x500 letterboxed)
      - face_mask.npz — числовые маски (original, crop, face, alpha)
      - mask_original — в original resolution (может быть большим!)

    🚨 WARNING:
      - При hard_mask = None — возвращает None (mask unavailable)
      - При ошибке записи — engine пишет face_mask_failure.json
    """
    if hard_mask is None or hard_mask.size == 0:
        return None
    
    # Convert to uint8 if boolean
    if hard_mask.dtype == bool:
        hard_mask = hard_mask.astype(np.uint8) * 255
    elif hard_mask.dtype != np.uint8:
        hard_mask = np.clip(hard_mask, 0, 255).astype(np.uint8)
    
    x, y, w, h = bbox
    H, W = hard_mask.shape[:2]
    
    # Clamp bbox to image bounds
    x1 = max(0, min(x, W - 1))
    y1 = max(0, min(y, H - 1))
    x2 = max(0, min(x + w, W))
    y2 = max(0, min(y + h, H))
    w = x2 - x1
    h = y2 - y1
    
    if w <= 0 or h <= 0:
        return None
    
    # Extract face crop and mask
    crop = bgr[y1:y2, x1:x2]
    mask_crop = hard_mask[y1:y2, x1:x2]
    
    # Letterbox to 424x500 (same as face_crop)
    face, transform = _letterbox(crop)
    mh, mw = mask_crop.shape[:2]
    scale = transform["scale"]
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    ox, oy = transform["offset_x"], transform["offset_y"]
    
    # Resize mask with same letterbox transform
    mask_resized = cv2.resize(mask_crop, (nw, nh), interpolation=cv2.INTER_LINEAR)
    mask_canvas = np.zeros((500, 424), np.uint8)
    if oy + nh <= 500 and ox + nw <= 424:
        mask_canvas[oy:oy + nh, ox:ox + nw] = mask_resized
    
    # Create RGBA visual preview.
    rgba = cv2.cvtColor(face, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = mask_canvas
    if not cv2.imwrite(str(out / "face_mask.png"), rgba):
        raise OSError(f"failed to write face_mask.png to {out / 'face_mask.png'}")

    mask_original_bool = hard_mask > 0
    mask_crop_bool = mask_crop > 0
    mask_face_bool = mask_canvas > 0
    np.savez_compressed(
        out / "face_mask.npz",
        mask_original=mask_original_bool,
        mask_crop=mask_crop_bool,
        mask_face=mask_face_bool,
        mask_alpha_u8=mask_canvas,
        bbox_original=np.asarray([x1, y1, w, h], np.int32),
        original_shape=np.asarray(hard_mask.shape[:2], np.int32),
        crop_shape=np.asarray(mask_crop.shape[:2], np.int32),
        face_shape=np.asarray(mask_canvas.shape[:2], np.int32),
        letterbox_scale=np.asarray([float(scale)], np.float32),
        letterbox_offset=np.asarray([int(ox), int(oy)], np.int32),
        letterbox_content_size=np.asarray([int(nw), int(nh)], np.int32),
        skin_pixels_original=np.asarray([int(np.count_nonzero(mask_original_bool))], np.int64),
        skin_pixels_crop=np.asarray([int(np.count_nonzero(mask_crop_bool))], np.int64),
        skin_pixels_face=np.asarray([int(np.count_nonzero(mask_face_bool))], np.int64),
        skin_coverage_original=np.asarray([float(np.mean(mask_original_bool))], np.float32),
        skin_coverage_crop=np.asarray([float(np.mean(mask_crop_bool))], np.float32),
        skin_coverage_face=np.asarray([float(np.mean(mask_face_bool))], np.float32),
        semantics=np.asarray(
            "face_mask.npz: numeric skin/face mask bundle; mask_original is in original image space; "
            "mask_crop is the original-resolution bbox crop; mask_face is the 424x500 letterboxed preview alpha"
        ),
    )
    return {"face_mask": "face_mask.png", "face_mask_data": "face_mask.npz"}


def save_semantic_channels(bundle: Any, out: Path) -> str:
    log_status("save_semantic_channels", "complete")
    """
    Save semantic_channels.npz from mask bundle.
    """
    np.savez_compressed(
        out / "semantic_channels.npz",
        channels_224=bundle.channels_224,
        channel_names=np.asarray(CHANNEL_NAMES),
        skin_soft_224=bundle.soft_224.astype(np.float16),
        skin_hard_224=bundle.hard_224.astype(np.uint8),
    )
    return "semantic_channels.npz"
