from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .config import PHOTO_SCHEMA_VERSION, VALIDATION_SCHEMA_VERSION
from .geometry import unpack_mask
from .utils import atomic_json

# Default topology constants for BFM-based 3DDFA model.
# Ideally read from reconstruction.npz at runtime; these are fallbacks.
MESH_COUNT = 35709
TRIANGLE_COUNT = 70789


def _resolve_topology(directory: Path) -> tuple[int, int]:
    """Resolve MESH_COUNT and TRIANGLE_COUNT from reconstruction.npz if available.

    Returns (mesh_count, triangle_count) — either from the NPZ or from
    the BFM defaults above.
    """
    try:
        p = directory / "reconstruction.npz"
        if p.is_file():
            with np.load(p, allow_pickle=False) as z:
                mc = int(z["vertices_object"].shape[0]) if "vertices_object" in z else MESH_COUNT
                tc = int(z["triangles"].shape[0]) if "triangles" in z else TRIANGLE_COUNT
                return mc, tc
    except Exception:
        pass
    return MESH_COUNT, TRIANGLE_COUNT


NPZ_REQUIRED = {
    "vertices_object": (MESH_COUNT, 3),
    "vertices_identity_only": (MESH_COUNT, 3),
    "vertices_object_normalized": (MESH_COUNT, 3),
    "vertices_bin_canonical": (MESH_COUNT, 3),
    "vertices_chronology_aligned": (MESH_COUNT, 3),
    "vertices_camera": (MESH_COUNT, 3),
    "vertices_image_224": (MESH_COUNT, 2),
    "normals_object": (MESH_COUNT, 3),
    "normals_posed": (MESH_COUNT, 3),
    "triangles": (TRIANGLE_COUNT, 3),
    "uv_coords": (MESH_COUNT, 2),
    "ldm106_vertex_indices": (106,),
    "ldm134_vertex_indices": (134,),
    "alpha_full": (257,), "alpha_id": (80,), "alpha_exp": (64,), "alpha_alb": (80,), "alpha_sh": (27,),
    "angle_rad": (3,), "angle_deg_pitch_yaw_roll": (3,), "rotation_matrix": (3, 3),
    "translation": (3,), "trans_params": (5,), "normalization_center": (3,),
    "normalization_scale": (1,), "canonical_rotation_row_matrix": (3, 3),
    "chronology_correction_matrix": (3, 3), "chronology_target_pose": (3,),
    "canonical_yaw": (1,),
    "ldm106_object": (106, 3), "ldm106_object_normalized": (106, 3),
    "ldm106_bin_canonical": (106, 3), "ldm106_chronology_aligned": (106, 3),
    "ldm106_camera": (106, 3), "ldm106_image_224": (106, 2),
    "ldm106_identity_only": (106, 3),
    "ldm106_front_facing": (106,), "ldm106_renderer_visible": (106,), "ldm106_visible": (106,),
    "ldm134_object": (134, 3), "ldm134_object_normalized": (134, 3),
    "ldm134_bin_canonical": (134, 3), "ldm134_chronology_aligned": (134, 3),
    "ldm134_camera": (134, 3), "ldm134_image_224": (134, 2),
    "ldm134_identity_only": (134, 3),
    "ldm134_front_facing": (134,), "ldm134_renderer_visible": (134,), "ldm134_visible": (134,),
    "full_mesh_front_facing_packbits": (4464,),
    "full_mesh_renderer_visible_packbits": (4464,),
    "full_mesh_visible_packbits": (4464,),
}


class ValidationError(RuntimeError):
    pass


def _csv_check(path: Path, expected: int) -> tuple[np.ndarray, np.ndarray]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != expected:
        raise ValidationError(f"{path.name}: expected {expected} rows, got {len(rows)}")
    ids = [int(row["landmark_id"]) for row in rows]
    if ids != list(range(expected)):
        raise ValidationError(f"{path.name}: landmark_id sequence invalid")
    points = np.asarray([[float(r["x"]), float(r["y"]), float(r["z"])] for r in rows], np.float32)
    indices = np.asarray([int(r["vertex_index"]) for r in rows], np.int64)
    return points, indices


def validate_photo(directory: Path, write_result: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    info: dict[str, Any] = {}
    try:
        info = json.loads((directory / "info.json").read_text(encoding="utf-8"))
        if info.get("schema_version") != PHOTO_SCHEMA_VERSION:
            raise ValidationError(f"photo schema mismatch: {info.get('schema_version')}")
        files = info.get("files") or {}
        optional_files = {"face_mask", "face_mask_data"}

        # Resolve topology from reconstruction.npz rather than hardcoding
        mesh_count, tri_count = _resolve_topology(directory)
        for name, relative in files.items():
            if relative is None:
                if name in optional_files:
                    warnings.append(f"optional file absent: {name}")
                    continue
                raise ValidationError(f"required file is None: {name}")
            path = directory / str(relative)
            if not path.is_file() or path.stat().st_size <= 0:
                raise ValidationError(f"missing/empty file {name}: {relative}")
        csv_data = {
            "ldm106_raw": _csv_check(directory / "ldm106_raw.csv", 106),
            "ldm106_aligned": _csv_check(directory / "ldm106_aligned.csv", 106),
            "ldm106_chronology": _csv_check(directory / "ldm106_chronology.csv", 106),
            "ldm134_raw": _csv_check(directory / "ldm134_raw.csv", 134),
            "ldm134_aligned": _csv_check(directory / "ldm134_aligned.csv", 134),
            "ldm134_chronology": _csv_check(directory / "ldm134_chronology.csv", 134),
        }
        with np.load(directory / "reconstruction.npz", allow_pickle=False) as z:
            # Build shape requirements using dynamic topology
            dynamic_npz_required = dict(NPZ_REQUIRED)
            for key in ("vertices_object", "vertices_identity_only", "vertices_object_normalized",
                        "vertices_bin_canonical", "vertices_chronology_aligned",
                        "vertices_camera", "vertices_image_224",
                        "normals_object", "normals_posed", "uv_coords"):
                if key in dynamic_npz_required:
                    dynamic_npz_required[key] = (mesh_count, *dynamic_npz_required[key][1:])
            dynamic_npz_required["triangles"] = (tri_count, 3)
            # Update landmark array shapes
            for prefix in ("ldm106", "ldm134"):
                for suffix in ("object", "object_normalized", "bin_canonical", "chronology_aligned",
                               "camera", "image_224", "identity_only"):
                    key = f"{prefix}_{suffix}"
                    if key in dynamic_npz_required:
                        count = 106 if prefix == "ldm106" else 134
                        if suffix == "image_224":
                            dynamic_npz_required[key] = (count, 2)
                        else:
                            dynamic_npz_required[key] = (count, 3)
            # Update landmark index shapes if needed
            for key in ("ldm106_vertex_indices",):
                pass  # (106,) stays
            for key, shape in dynamic_npz_required.items():
                if key not in z:
                    raise ValidationError(f"NPZ missing {key}")
                if z[key].shape != shape:
                    raise ValidationError(f"NPZ {key} shape {z[key].shape}, expected {shape}")
                if np.issubdtype(z[key].dtype, np.number) and not np.isfinite(z[key]).all():
                    raise ValidationError(f"NPZ {key} contains NaN/Inf")
            triangles = z["triangles"]
            if triangles.min() < 0 or triangles.max() >= mesh_count:
                raise ValidationError("triangle index out of bounds")
            for key in ("ldm106_vertex_indices", "ldm134_vertex_indices"):
                if z[key].min() < 0 or z[key].max() >= mesh_count:
                    raise ValidationError(f"{key} out of bounds")
            front = unpack_mask(z["full_mesh_front_facing_packbits"], mesh_count).astype(bool)
            renderer = unpack_mask(z["full_mesh_renderer_visible_packbits"], mesh_count).astype(bool)
            combined = unpack_mask(z["full_mesh_visible_packbits"], mesh_count).astype(bool)
            if not np.array_equal(combined, front & renderer):
                raise ValidationError("combined visibility differs from front & renderer")
            if z["alpha_alb"].size == 0 or z["alpha_sh"].size == 0:
                raise ValidationError("albedo/SH coefficients are empty")
            uv_shape = tuple(int(x) for x in z["uv_shape"])
            if len(uv_shape) != 2 or min(uv_shape) <= 0:
                raise ValidationError(f"invalid uv_shape: {uv_shape}")
            if z["uv_confidence"].shape != uv_shape:
                raise ValidationError("uv_confidence shape differs from uv_shape")
            required_uv_bytes = (uv_shape[0] * uv_shape[1] + 7) // 8
            for key in ("uv_observed_mask_packbits", "uv_is_original_packbits"):
                if z[key].shape != (required_uv_bytes,):
                    raise ValidationError(f"{key} has invalid packed length")
            if z["tri_visibility"].shape != (tri_count,):
                raise ValidationError("tri_visibility shape invalid")
            if float(z["normalization_scale"][0]) <= 0:
                raise ValidationError("normalization scale must be positive")
            rotation = z["rotation_matrix"].astype(np.float64)
            if not np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-4) or not np.isclose(np.linalg.det(rotation), 1.0, atol=2e-4):
                raise ValidationError("rotation_matrix is not a proper rotation")
            mapping = {
                "ldm106_raw": ("ldm106_object", "ldm106_vertex_indices"),
                "ldm106_aligned": ("ldm106_bin_canonical", "ldm106_vertex_indices"),
                "ldm106_chronology": ("ldm106_chronology_aligned", "ldm106_vertex_indices"),
                "ldm134_raw": ("ldm134_object", "ldm134_vertex_indices"),
                "ldm134_aligned": ("ldm134_bin_canonical", "ldm134_vertex_indices"),
                "ldm134_chronology": ("ldm134_chronology_aligned", "ldm134_vertex_indices"),
            }
            for name, (array_key, index_key) in mapping.items():
                points, indices = csv_data[name]
                if not np.allclose(points, z[array_key], atol=1e-6):
                    raise ValidationError(f"{name}.csv coordinates differ from NPZ")
                if not np.array_equal(indices, z[index_key]):
                    raise ValidationError(f"{name}.csv vertex indices differ from NPZ")
        semantic = np.load(directory / "semantic_channels.npz", allow_pickle=False)
        if semantic["channels_224"].shape != (224, 224, 8):
            raise ValidationError("semantic channels shape invalid")

        if files.get("uv_data"):
            with np.load(directory / str(files["uv_data"]), allow_pickle=False) as uvz:
                for key in ("texture_bgr", "confidence", "observed_mask", "filled_mask", "is_original_mask", "valid_mask", "uv_shape", "uv_coords"):
                    if key not in uvz:
                        raise ValidationError(f"uv.npz missing {key}")
                forbidden = {"analysis_bgr", "synthetic_bgr", "beauty_bgr"} & set(uvz.files)
                if forbidden:
                    raise ValidationError(f"multiple UV texture versions forbidden: {sorted(forbidden)}")
                uv_shape2 = tuple(int(x) for x in uvz["uv_shape"])
                for key in ("confidence", "observed_mask", "is_original_mask", "valid_mask"):
                    if uvz[key].shape != uv_shape2:
                        raise ValidationError(f"uv.npz {key} shape differs from uv_shape")
                if uvz["texture_bgr"].shape[:2] != uv_shape2:
                    raise ValidationError("uv.npz texture_bgr shape differs from uv_shape")
                if uvz["uv_coords"].shape != (mesh_count, 2):
                    raise ValidationError("uv.npz uv_coords shape invalid")

        if files.get("face_mask_data"):
            with np.load(directory / str(files["face_mask_data"]), allow_pickle=False) as fmz:
                for key in ("mask_original", "mask_crop", "mask_face", "mask_alpha_u8", "bbox_original"):
                    if key not in fmz:
                        raise ValidationError(f"face_mask.npz missing {key}")
                if fmz["mask_face"].shape != (500, 424) or fmz["mask_alpha_u8"].shape != (500, 424):
                    raise ValidationError("face_mask.npz face mask shape invalid")

        if files.get("quality"):
            q = json.loads((directory / str(files["quality"])).read_text(encoding="utf-8"))
            if q.get("status") not in {"complete", "no_face_mask"}:
                raise ValidationError(f"quality.json bad status: {q.get('status')}")
        if files.get("quality_zones"):
            with np.load(directory / str(files["quality_zones"]), allow_pickle=False) as qz:
                for key in ("zone_names", "zone_texture_roi_original_packbits", "zone_texture_pixels", "zone_visible_fraction"):
                    if key not in qz:
                        raise ValidationError(f"quality_zones.npz missing {key}")
                if qz["zone_texture_pixels"].shape[0] != qz["zone_names"].shape[0]:
                    raise ValidationError("quality_zones zone count mismatch")

        if files.get("skin_manifest"):
            skin_root = directory / "skin"
            sm = json.loads((skin_root / "manifest.json").read_text(encoding="utf-8"))
            if sm.get("schema") != "skin-manifest-v1" or sm.get("state") != "success":
                raise ValidationError("skin manifest is not successful skin-manifest-v1")
            if not (skin_root / "SUCCESS").is_file():
                raise ValidationError("skin SUCCESS marker absent")
            from .skin.serialization import sha256_file
            source_mask = sm.get("source_mask") or {}
            if source_mask.get("sha256") != sha256_file(directory / "face_mask.npz") or source_mask.get("array") != "mask_original":
                raise ValidationError("skin source-mask provenance mismatch")
            for relative, meta in sm.get("products", {}).items():
                product = skin_root / relative
                if not product.is_file() or sha256_file(product) != meta.get("sha256"):
                    raise ValidationError(f"skin product checksum mismatch: {relative}")
            with np.load(skin_root / "surface_observations.npz", allow_pickle=False) as sz:
                original_shape = tuple(map(int, sz["original_shape"]))
                if original_shape != tuple(info["image"][k] for k in ("height", "width")):
                    raise ValidationError("skin original_shape differs from source photo")
                if sz["triangle_id"].shape != sz["source_xy"].shape[:2]:
                    raise ValidationError("skin cropped map shapes differ")
                if sz["surface_vertices"].shape != (mesh_count,3) or sz["triangles"].shape != (tri_count,3) or sz["triangle_surface_area"].shape != (tri_count,):
                    raise ValidationError("skin surface geometry contract invalid")
                surface_map_shape = sz["triangle_id"].shape
                surface_origin = tuple(map(int, sz["map_origin_xy"]))
                valid = sz["triangle_id"] >= 0
                if np.any(valid):
                    xy = sz["source_xy"][valid]
                    if xy[:, 0].min() < 0 or xy[:, 0].max() >= original_shape[1] or xy[:, 1].min() < 0 or xy[:, 1].max() >= original_shape[0]:
                        raise ValidationError("skin source_xy outside original photo")
                if np.any(valid) and not np.allclose(sz["barycentric"][valid].sum(1), 1, atol=2e-3):
                    raise ValidationError("skin barycentric sum invariant failed")
            with np.load(directory / "face_mask.npz", allow_pickle=False) as fm:
                mask_original = fm["mask_original"].astype(bool)
            x0,y0=surface_origin;hmap,wmap=surface_map_shape;face_mask_native=mask_original[y0:y0+hmap,x0:x0+wmap]
            if face_mask_native.shape != surface_map_shape:
                raise ValidationError("face_mask crop/surface map shape mismatch")
            with np.load(skin_root / "atlas_projection.npz", allow_pickle=False) as az:
                if np.any(az["zone_id_a20"] < -1) or np.any(az["zone_id_s40"] < -1):
                    raise ValidationError("invalid skin zone sentinel")
                if az["zone_id_a20"].shape != face_mask_native.shape or az["wrinkle_bits_w14"].shape != (2, *face_mask_native.shape):
                    raise ValidationError("skin atlas/mask shape mismatch")
                if np.any((az["zone_id_a20"] >= 0) & ~face_mask_native):
                    raise ValidationError("skin evidence leaves canonical face_mask")
            with np.load(skin_root / "features/texture.npz", allow_pickle=False) as ft:
                if ft["values"].shape[0] != 60 or ft["values"].shape[1] != ft["columns"].shape[0]:
                    raise ValidationError("texture feature contract invalid")
            with np.load(skin_root / "wrinkles/classical.npz", allow_pickle=False) as wz:
                if wz["ridge_probability"].shape != face_mask_native.shape:
                    raise ValidationError("wrinkle map shape invalid")

        for key in ("face_crop", "uv_texture"):
            p = directory / str(files[key])
            if cv2.imread(str(p), cv2.IMREAD_UNCHANGED) is None:
                raise ValidationError(f"cannot decode {key}")
    except Exception as exc:
        errors.append(str(exc))
    status = "complete" if not errors else "invalid"
    result = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "photo_id": info.get("photo_id"),
    }
    if write_result:
        atomic_json(directory / "validation.json", result)
    return result


def is_resumable(directory: Path, source_sha256: str, code_hash: str, config_hash: str, model_hash: str) -> tuple[bool, dict[str, Any] | None]:
    if not directory.is_dir():
        return False, None
    try:
        info = json.loads((directory / "info.json").read_text(encoding="utf-8"))
        expected = {
            "source_sha256": source_sha256, "code_hash": code_hash,
            "config_hash": config_hash, "model_hash": model_hash,
        }
        if any(info.get(k) != v for k, v in expected.items()):
            return False, None
        result = validate_photo(directory, write_result=False)
        return result["status"] == "complete", info
    except Exception:
        return False, None
