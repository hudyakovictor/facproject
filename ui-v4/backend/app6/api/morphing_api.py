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

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from .calibration import POSE_BINS
from .landmark_regions import regions_for
from .runtime_config import load_runtime_paths

MORPHING_SCHEMA = "deeputin-morphing-api-v1.0"
MORPH_DIFF_SCHEMA = "deeputin-morphing-diff-v1.0"
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


# ---------------------------------------------------------------------------
# 3D heatmap support: per-vertex mesh displacement between two photos
# ---------------------------------------------------------------------------
def _read_landmark_csv_points(path: Path, count: int) -> np.ndarray:
    """(N,3) chronology-aligned landmark points from a Stage-1 CSV."""
    points: list[list[float]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            points.append([float(row["x"]), float(row["y"]), float(row.get("z") or 0.0)])
    arr = np.asarray(points, np.float32)
    if arr.shape != (count, 3):
        raise ValueError(f"expected {count} landmark rows, got {arr.shape[0]}")
    return arr


def _kabsch(p: np.ndarray, q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Optimal rigid transform R,t mapping p → q (||R p + t − q|| min)."""
    p = np.asarray(p, np.float64)
    q = np.asarray(q, np.float64)
    pc = p - p.mean(axis=0)
    qc = q - q.mean(axis=0)
    h = pc.T @ qc
    u, _, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    diag = np.diag([1.0, 1.0, float(d)])
    r = vt.T @ diag @ u.T
    t = q.mean(axis=0) - r @ p.mean(axis=0)
    return r, t


def _active_stage2_run() -> Path | None:
    paths = load_runtime_paths()
    root = paths.stage2_root
    candidates: list[Path] = []
    if (root / "analysis_manifest.json").is_file():
        candidates.append(root)
    runs = root / "runs"
    if runs.is_dir():
        candidates.extend(
            item for item in runs.iterdir()
            if item.is_dir() and (item / "analysis_manifest.json").is_file()
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def mesh_displacement(photo_a: str, photo_b: str) -> dict[str, Any]:
    """Per-vertex displacement between two canonical meshes.

    Both meshes are read from immutable Stage 1 `reconstruction.npz`
    (`vertices_chronology_aligned`). A global Kabsch alignment on the 106
    chronology landmarks removes the residual rigid difference between the
    two canonical frames, so the heatmap shows *shape* change, not pose
    offset. The B mesh is returned already aligned to A.

    When a completed Stage 2 run exists, each vertex is also mapped to its
    nearest landmark and gets that landmark's calibrated same-person p95 —
    the color scale can then be anchored to "within noise → exceeds p95".
    """
    dir_a = _photo_dir(photo_a)
    dir_b = _photo_dir(photo_b)

    def _load(directory: Path, photo_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        npz_path = directory / "reconstruction.npz"
        if not npz_path.is_file():
            raise FileNotFoundError(f"reconstruction.npz not found for {photo_id}")
        with np.load(npz_path, allow_pickle=False) as z:
            vertices = _first_array(z, "vertices_chronology_aligned", "vertices_bin_canonical", "vertices_object_normalized")
            triangles = _first_array(z, "triangles")
            idx106 = _first_array(z, "ldm106_vertex_indices")
            if vertices is None or triangles is None:
                raise ValueError(f"reconstruction.npz for {photo_id} lacks vertices/triangles")
            if vertices.shape[0] > MAX_VERTICES or triangles.shape[0] > MAX_TRIANGLES:
                raise ValueError(f"mesh too large for {photo_id}")
        ldm_path = directory / "ldm106_chronology.csv"
        if not ldm_path.is_file():
            ldm_path = directory / "ldm106_raw.csv"
        landmarks = _read_landmark_csv_points(ldm_path, 106)
        return vertices.astype(np.float32), triangles, landmarks, np.asarray(idx106, np.int64)

    va, ta, la, idx_a = _load(dir_a, photo_a)
    vb, tb, lb, idx_b = _load(dir_b, photo_b)
    if ta.shape != tb.shape or (idx_a.shape != idx_b.shape or not np.array_equal(idx_a, idx_b)):
        raise ValueError(f"topology mismatch between {photo_a} and {photo_b} — morphing not defined")

    # residual rigid alignment A←B (both meshes already share the canonical frame)
    r_mat, t_vec = _kabsch(lb, la)
    vb_aligned = (vb.astype(np.float64) @ r_mat.T + t_vec).astype(np.float32)
    magnitudes = np.linalg.norm(vb_aligned - va, axis=1).astype(np.float32)

    stats = {
        "min": float(np.min(magnitudes)),
        "median": float(np.median(magnitudes)),
        "p95": float(np.percentile(magnitudes, 95)),
        "max": float(np.max(magnitudes)),
    }

    pose_bin = "unknown"
    info_path = dir_a / "info.json"
    if info_path.is_file():
        try:
            payload = json.loads(info_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("pose_bin"):
                pose_bin = str(payload["pose_bin"])
        except (OSError, json.JSONDecodeError):
            pass

    # per-vertex calibrated reference via nearest landmark (active run)
    calibration: dict[str, Any] = {"available": False, "mean_p95": None, "per_vertex_p95": None, "pose_bin": pose_bin}
    run = _active_stage2_run()
    if run is not None:
        npz_path = run / "point_noise_model.npz"
        if npz_path.is_file():
            try:
                with np.load(npz_path, allow_pickle=False) as z:
                    template_key = f"{pose_bin}__ldm106__template"
                    p95_key = f"{pose_bin}__ldm106__p95"
                    if template_key in z.files and p95_key in z.files:
                        template = np.asarray(z[template_key], np.float32)
                        p95 = np.asarray(z[p95_key], np.float32)
                        if template.shape == (106, 3) and p95.shape == (106,):
                            # nearest landmark per vertex (chunked to bound memory)
                            nearest = np.empty(va.shape[0], np.int64)
                            for start in range(0, va.shape[0], 8192):
                                chunk = va[start:start + 8192].astype(np.float64)
                                d2 = ((chunk[:, None, :] - template[None, :, :].astype(np.float64)) ** 2).sum(-1)
                                nearest[start:start + chunk.shape[0]] = d2.argmin(1)
                            per_vertex = p95[nearest].astype(np.float32)
                            calibration = {
                                "available": True,
                                "mean_p95": float(np.nanmean(per_vertex)),
                                "per_vertex_p95": per_vertex.tolist(),
                                "pose_bin": pose_bin,
                            }
            except (OSError, ValueError):
                calibration = {"available": False, "mean_p95": None, "per_vertex_p95": None, "pose_bin": pose_bin}

    return {
        "schema": MORPH_DIFF_SCHEMA,
        "not_a_verdict": True,
        "photo_a": photo_a,
        "photo_b": photo_b,
        "pose_bin": pose_bin,
        "vertex_count": int(va.shape[0]),
        "triangle_count": int(ta.shape[0]),
        "vertices_a": va.reshape(-1).tolist(),
        "vertices_b": vb_aligned.reshape(-1).tolist(),
        "magnitudes": magnitudes.reshape(-1).tolist(),
        "stats": stats,
        "calibration": calibration,
    }
