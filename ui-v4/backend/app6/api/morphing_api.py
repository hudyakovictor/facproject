"""Morphing workspace API (Iteration 09).

Serves everything the Morphing widget needs:

- per-pose-bin photo lists (chronology order),
- per-photo canonical (chronology-aligned) mesh + triangles + UV coordinates
  straight from the immutable Stage 1 `reconstruction.npz` — the same arrays
  the Stage 2 pipeline reads,
- texture URLs (existing `/api/v1/photos/{id}/image?kind=uv_texture`).

All models in one pose bin share the same canonical orientation
(`vertices_chronology_aligned`), so the widget can interpolate geometry and
texture between any two photos without re-posing them.

🚨 WARNING: morphing is a *visualization-only* comparison. Interpolated frames
are never fed into Stage 2 measurements.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .calibration import POSE_BINS
from .landmark_regions import regions_for
from .runtime_config import load_runtime_paths

MORPHING_SCHEMA = "deeputin-morphing-api-v1.0"
# Canonical viewer direction per pose bin (degrees). The models themselves are
# already in canonical chronology pose; this is the *camera* azimuth so that a
# left-profile photo is looked at from the left, etc.
BIN_CAMERA_YAW: dict[str, float] = {
    "left_profile": -70.0, "left_deep": -50.0, "left_mid": -30.0, "left_light": -15.0,
    "frontal": 0.0, "right_light": 15.0, "right_mid": 30.0, "right_deep": 50.0,
    "right_profile": 70.0,
}
BIN_CAMERA_ELEVATION: dict[str, float] = {
    "left_profile": 0.0, "left_deep": 0.0, "left_mid": 0.0, "left_light": 0.0,
    "frontal": -4.0, "right_light": 0.0, "right_mid": 0.0, "right_deep": 0.0,
    "right_profile": 0.0,
}
# mesh size cap: full BFM meshes are ~35k vertices; the fixture uses smaller
# meshes. We never downsample real data — the JSON is gzip-compressed by the
# server middleware and the frontend converts it straight into Float32Arrays.
MAX_VERTICES = 60_000
MAX_TRIANGLES = 140_000


def _stage1_root() -> Path | None:
    paths = load_runtime_paths()
    root = paths.stage1_root
    return root if (root / "main_timeline.csv").is_file() else None


def _photo_dir(photo_id: str) -> Path:
    root = _stage1_root()
    if root is None:
        raise FileNotFoundError("Stage 1 is not configured (no main_timeline.csv)")
    resolved = (root / photo_id).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"invalid photo_id: {photo_id}") from exc
    if not resolved.is_dir():
        raise FileNotFoundError(f"no Stage 1 output for {photo_id}")
    return resolved


def _first_array(z: np.lib.npyio.NpzFile, *names: str) -> np.ndarray | None:
    for name in names:
        if name in z.files:
            return np.asarray(z[name])
    return None


def morphing_bins(timeline_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group timeline rows into the nine pose bins (chronology order)."""
    bins: dict[str, list[dict[str, Any]]] = {}
    for pose in POSE_BINS:
        bins[pose] = []
    for row in timeline_rows:
        pose = str(row.get("bucket") or row.get("pose_bin") or "unknown")
        bins.setdefault(pose, []).append(row)
    for pose in bins:
        bins[pose].sort(key=lambda r: (r.get("t") if isinstance(r.get("t"), (int, float)) else 0,
                                       str(r.get("date") or ""), str(r.get("id") or "")))
    return {
        "schema": MORPHING_SCHEMA,
        "pose_bins": [
            {
                "pose": pose,
                "label": pose,
                "camera": {
                    "yaw_deg": BIN_CAMERA_YAW.get(pose, 0.0),
                    "elevation_deg": BIN_CAMERA_ELEVATION.get(pose, 0.0),
                },
                "photos": [
                    {
                        "id": str(row["id"]),
                        "date": str(row.get("date") or ""),
                        "t": row.get("t"),
                        "quality": row.get("quality"),
                        "yaw": row.get("yaw"),
                        "pitch": row.get("pitch"),
                        "roll": row.get("roll"),
                    }
                    for row in rows
                ],
            }
            for pose, rows in bins.items()
        ],
    }


def photo_morph_payload(photo_id: str, include_landmarks: bool = True) -> dict[str, Any]:
    """Mesh + UV + landmarks for one photo, in canonical chronology pose."""
    directory = _photo_dir(photo_id)
    npz_path = directory / "reconstruction.npz"
    if not npz_path.is_file():
        raise FileNotFoundError(f"reconstruction.npz not found for {photo_id}")

    with np.load(npz_path, allow_pickle=False) as z:
        vertices = _first_array(z, "vertices_chronology_aligned", "vertices_bin_canonical", "vertices_object_normalized")
        triangles = _first_array(z, "triangles")
        uv_coords = _first_array(z, "uv_coords")
        if vertices is None or triangles is None:
            raise ValueError(f"reconstruction.npz for {photo_id} lacks vertices/triangles")
        if vertices.shape[0] > MAX_VERTICES or triangles.shape[0] > MAX_TRIANGLES:
            raise ValueError(f"mesh too large for {photo_id}: {vertices.shape}, {triangles.shape}")
        angles = _first_array(z, "angle_deg_pitch_yaw_roll")
        canonical_yaw = _first_array(z, "canonical_yaw")
        target_pose = _first_array(z, "chronology_target_pose")

    info: dict[str, Any] = {}
    info_path = directory / "info.json"
    if info_path.is_file():
        try:
            payload = json.loads(info_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                info = payload
        except (OSError, json.JSONDecodeError):
            pass

    texture_available = (directory / "uv_texture.png").is_file()
    if uv_coords is None:
        uv_npz = directory / "uv.npz"
        if uv_npz.is_file():
            with np.load(uv_npz, allow_pickle=False) as z:
                uv_coords = _first_array(z, "uv_coords")

    provenance = info.get("date_provenance") if isinstance(info.get("date_provenance"), dict) else {}
    out: dict[str, Any] = {
        "schema": MORPHING_SCHEMA,
        "photo_id": photo_id,
        "pose_bin": info.get("pose_bin") or "unknown",
        "date": provenance.get("filename_date") or provenance.get("source_claimed_date"),
        "vertices": np.asarray(vertices, np.float32).reshape(-1).tolist(),
        "triangles": np.asarray(triangles, np.int64).reshape(-1).tolist(),
        "uv_coords": (np.asarray(uv_coords, np.float32).reshape(-1).tolist() if uv_coords is not None else []),
        "vertex_count": int(vertices.shape[0]),
        "triangle_count": int(triangles.shape[0]),
        "has_uv": bool(uv_coords is not None and len(uv_coords)),
        "texture_url": f"/api/v1/photos/{photo_id}/image?kind=uv_texture" if texture_available else None,
        "texture_size": [96, 96],  # informational; the real size is read from the PNG by the browser
        "actual_pose_deg": angles.reshape(-1).tolist() if angles is not None else None,
        "canonical_pose_deg": {
            "yaw": float(target_pose.reshape(-1)[1]) if target_pose is not None and target_pose.size > 1 else (
                float(canonical_yaw.reshape(-1)[0]) if canonical_yaw is not None and canonical_yaw.size else 0.0),
            "pitch": float(target_pose.reshape(-1)[0]) if target_pose is not None and target_pose.size else 0.0,
            "roll": float(target_pose.reshape(-1)[2]) if target_pose is not None and target_pose.size > 2 else 0.0,
        },
    }
    if include_landmarks:
        out["regions"] = {count: regions_for(count) for count in (106, 134)}
    return out
