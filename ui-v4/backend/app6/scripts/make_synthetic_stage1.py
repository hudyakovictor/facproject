#!/usr/bin/env python3
"""Synthetic Stage-1 fixture generator (CI / sandbox / offline development).

Builds a complete, loader-compatible Stage 1 tree plus a calibration Stage 1
tree so the full pipeline (timeline → selection → Stage 2 → Stage 3) and the
expert widgets (Landmark Compare, Morphing) can be exercised WITHOUT model
weights and WITHOUT the real dataset.

The geometry is deliberately simple (a parametric "face" ellipsoid with a nose
bump) — this is a *layout and contract* fixture, not an anthropometric one.
Every artifact name and JSON/CSV/NPZ contract matches the real Stage 1 output,
so the same code paths run against this fixture and against the real
/Volumes/SDCARD/storage dataset.

Usage:
    python app6/scripts/make_synthetic_stage1.py --root /tmp/sdcard \
        --main-photos 126 --cal-frames 504 [--seed 7]

Layout produced under <root>:
    storage/stage1/        main dataset (main_timeline.csv + photo dirs)
    storage/profiles/      (created lazily by the API)
    calibration/           calibration Stage 1 (main_timeline.csv +
                           all_calibration_index.csv + 7 persons × 9 bins)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from PIL import Image, ImageDraw
except ImportError:  # fixture textures are optional
    Image = None  # type: ignore

POSE_BINS = [
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
]
# canonical yaw (degrees) per bin — chronology target pose, mirrors real data
CANONICAL_YAW = {
    "left_profile": -70.0, "left_deep": -50.0, "left_mid": -30.0, "left_light": -15.0,
    "frontal": 0.0, "right_light": 15.0, "right_mid": 30.0, "right_deep": 50.0,
    "right_profile": 70.0,
}
CAL_PERSONS = 7
CAL_FRAMES_PER_PERSON_BIN = 4  # → 7 × 9 × 8 = 504 frames by default


# --------------------------------------------------------------------------
# parametric "face" geometry
# --------------------------------------------------------------------------
def _face_landmarks(count: int, yaw_deg: float, pitch_deg: float, roll_deg: float,
                    seed: int) -> np.ndarray:
    """Generate count 3D landmark points on a parametric face-like ellipsoid.

    Deterministic per (count, yaw, pitch, roll, seed). Points are positioned so
    the renderer shows a recognisable face: contour ellipse, brows, eyes, nose,
    mouth, cheeks.
    """
    rng = np.random.default_rng(seed)

    def ellipse_row(z: float, rx: float, ry: float, n: int, phase: float = 0.0) -> list[tuple[float, float, float]]:
        pts = []
        for i in range(n):
            t = phase + math.pi * i / max(1, n - 1)
            pts.append((rx * math.cos(t), ry * math.sin(t), z))
        return pts

    pts: list[tuple[float, float, float]] = []
    # outer contour (jaw/cheek line), 34 points
    pts += ellipse_row(0.0, 1.0, 1.25, 34, phase=-math.pi / 2)
    # brows (10) + eyes (16)
    for side, sign in ((-1, -1), (1, 1)):
        pts += [(sign * 0.28 + 0.10 * math.sin(math.pi * i / 4), 0.52 - 0.06 * i, 0.18) for i in range(5)]
        for i in range(8):
            t = math.pi * i / 7
            pts.append((side * (0.12 + 0.10 * math.sin(t)), 0.38 + 0.055 * math.cos(t), 0.30))
    # nose (9)
    pts += [(0.0, 0.10 - 0.045 * i, 0.42 + 0.05 * math.sin(i)) for i in range(9)]
    # mouth (20)
    for i in range(10):
        t = math.pi * i / 9
        pts.append((0.42 * math.sin(t), -0.28 + 0.05 * math.cos(t), 0.36))
    for i in range(10):
        t = math.pi * i / 9
        pts.append((0.34 * math.sin(t), -0.20 + 0.04 * math.cos(t), 0.34))
    # cheeks (18)
    for side in (-1, 1):
        for i in range(9):
            pts.append((side * (0.55 + 0.08 * math.sin(math.pi * i / 8)), 0.15 + 0.28 * math.cos(math.pi * i / 8), 0.10))
    # remaining padding along the contour (for 134)
    while len(pts) < count:
        t = 2 * math.pi * len(pts) / count
        pts.append((0.95 * math.cos(t), 0.8 * math.sin(t), 0.0))
    pts = pts[:count]

    arr = np.asarray(pts, np.float64)
    # scale face to object-normalized magnitude (~ unit size)
    arr /= 1.15
    # per-point deterministic jitter
    arr += rng.normal(0.0, 0.004, arr.shape)
    # apply pose rotation (pitch around x, yaw around y, roll around z)
    def rot_x(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], np.float64)
    def rot_y(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], np.float64)
    def rot_z(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float64)
    arr = arr @ rot_y(math.radians(yaw_deg)) @ rot_x(math.radians(pitch_deg)) @ rot_z(math.radians(roll_deg))
    return arr.astype(np.float32)


def _face_mesh(seed: int, yaw_deg: float, pitch_deg: float, roll_deg: float,
               lat: int = 32, lon: int = 32) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parametric ellipsoid "face" mesh with nose bump; returns (V, F, UV)."""
    rng = np.random.default_rng(seed)
    vertices: list[list[float]] = []
    for i in range(lat + 1):
        theta = math.pi * i / lat  # 0..pi (top→bottom)
        for j in range(lon + 1):
            phi = 2 * math.pi * j / lon
            x = math.sin(theta) * math.cos(phi)
            y = math.cos(theta)
            z = math.sin(theta) * math.sin(phi)
            # face-ish ellipsoid
            v = [x * 0.95, y * 1.18, z * 0.62]
            # nose bump near front (theta ~ pi/2, phi ~ pi/2)
            d = math.hypot(x - 0.0, y - 0.15)
            if d < 0.45 and z > 0.15:
                v[2] += 0.28 * math.sin(math.pi * d / 0.9) * min(1.0, (z - 0.15) / 0.35)
            v[0] += rng.normal(0, 0.004)
            v[1] += rng.normal(0, 0.004)
            v[2] += rng.normal(0, 0.004)
            vertices.append(v)
    V = np.asarray(vertices, np.float64)
    # UV: spherical mapping
    uv = []
    for i in range(lat + 1):
        theta = math.pi * i / lat
        for j in range(lon + 1):
            phi = 2 * math.pi * j / lon
            uv.append([j / lon, i / lat])
    UV = np.asarray(uv, np.float32)
    triangles: list[list[int]] = []
    for i in range(lat):
        for j in range(lon):
            a = i * (lon + 1) + j
            b = a + 1
            c = (i + 1) * (lon + 1) + j
            d = c + 1
            triangles.append([a, b, c])
            triangles.append([b, d, c])
    F = np.asarray(triangles, np.int64)
    # pose rotation, same convention as landmarks
    def rot_y(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], np.float64)
    def rot_x(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], np.float64)
    def rot_z(a: float) -> np.ndarray:
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float64)
    V = V @ rot_y(math.radians(yaw_deg)) @ rot_x(math.radians(pitch_deg)) @ rot_z(math.radians(roll_deg))
    return V.astype(np.float32), F, UV


def _make_texture(photo_id: str, seed: int) -> Path:
    """Small UV texture PNG (128×128) with a deterministic gradient + face hint."""
    if Image is None:
        raise RuntimeError("PIL is required for fixture textures")
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (96, 96))
    px = img.load()
    for y in range(96):
        for x in range(96):
            base = (int(0.75 * 255 * (1 - y / 256)), int(0.62 * 255 * (1 - x / 400)), int(0.58 * 255))
            noise = int(rng.normal(0, 6))
            px[x, y] = tuple(max(0, min(255, c + noise)) for c in base)
    d = ImageDraw.Draw(img)
    d.ellipse((28, 24, 68, 74), outline=(180, 140, 110), width=2)  # face outline hint
    d.ellipse((36, 38, 44, 48), fill=(40, 40, 50))  # left eye
    d.ellipse((52, 38, 60, 48), fill=(40, 40, 50))  # right eye
    d.ellipse((44, 56, 54, 66), fill=(120, 80, 80))  # mouth
    path = Path(photo_id) / "uv_texture.png"
    img.save(path)
    return path


def _make_photo_jpegs(photo_dir: Path, seed: int) -> None:
    if Image is None:
        return
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (160, 160))
    px = img.load()
    for y in range(160):
        for x in range(160):
            base = (int(120 + 40 * math.sin(x / 24)), int(110 + 30 * math.cos(y / 20)), int(100))
            px[x, y] = tuple(max(0, min(255, c + int(rng.normal(0, 5)))) for c in base)
    d = ImageDraw.Draw(img)
    d.ellipse((40, 36, 120, 140), outline=(160, 130, 105), width=2)
    d.ellipse((62, 62, 74, 74), fill=(30, 30, 40))
    d.ellipse((88, 62, 100, 74), fill=(30, 30, 40))
    img.save(photo_dir / "original.jpg", quality=88)
    img.resize((40, 40)).save(photo_dir / "thumb.jpg", quality=80)
    img.crop((30, 20, 130, 150)).resize((64, 64)).save(photo_dir / "face_crop.jpg", quality=85)


def _write_landmark_csv(path: Path, points: np.ndarray, visible: np.ndarray,
                        indices: np.ndarray, confidence: np.ndarray | None = None) -> None:
    import csv
    rows = []
    for i in range(len(points)):
        row = {
            "landmark_id": i, "x": float(points[i, 0]), "y": float(points[i, 1]),
            "z": float(points[i, 2]), "visible": int(visible[i]),
            "vertex_index": int(indices[i]),
        }
        if confidence is not None:
            row["confidence"] = float(confidence[i])
        rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _info_json(photo_id: str, date_iso: str, pose_bin: str, yaw: float, pitch: float,
               roll: float, quality: float, confidence: float, source_relative_path: str,
               quality_status: str = "pass") -> dict:
    return {
        "schema_version": "deeputin-stage1-info-v1.4",
        "photo_id": photo_id,
        "source_relative_path": source_relative_path,
        "source_digest": f"sha256:{photo_id}_synthetic_digest",
        "date_provenance": {
            "status": "confirmed", "filename_date": date_iso,
            "exif_date": None, "source_claimed_date": date_iso,
            "delta_days": 0, "conflict_sources": [],
        },
        "source_provenance": {"status": "provided", "chain": ["synthetic_fixture"]},
        "quality_inputs": {
            "combined_visible_fraction": quality, "skin_mask_coverage": quality * 0.9,
            "uv_observed_coverage": quality * 0.85, "laplacian_variance": 40.0 + quality * 30,
            "face_bbox_area_ratio": 0.18 + quality * 0.12, "face_bbox_width": 120,
            "noise_residual_mean": 0.02, "detection_confidence": confidence,
        },
        "quality_summary": {"supported_forehead_wrinkle_pose_v1": True},
        "skin_quality_score": quality, "skin_quality_status": quality_status,
        "skin_authenticity_score": 0.5 + quality * 0.4, "skin_authenticity_status": "authentic",
        "chronology": {
            "alignment_method": "full_pose_correction_v1",
            "alignment_quality": 0.55 + quality * 0.4,
            "actual_pose": [pitch, yaw, roll],
            "canonical_yaw": CANONICAL_YAW[pose_bin],
            "pose_confidence": confidence,
            "detection_confidence": confidence,
            "reprojection_p95": 2.5 - quality, "reprojection_rmse": 1.2 - quality * 0.5,
            "residual_yaw_deg": 1.0, "residual_pitch_deg": 0.6, "residual_roll_deg": 0.4,
            "correction_magnitude_deg": 8.0,
            "corner_lift_ioc": -0.01, "jaw_open_ratio": 0.05,
            "smile_detected": False, "jaw_open_detected": False,
            "visible_landmarks_106": 106, "visible_landmarks_134": 134,
            "coordinate_noise_sigma": 0.012,
            "alignment_csv_106": "ldm106_chronology.csv",
            "alignment_csv_134": "ldm134_chronology.csv",
        },
        "uv": {"observed_coverage": quality * 0.85, "original_coverage": quality * 0.7, "valid_coverage": quality * 0.9},
        "files": {
            "original": "original.jpg", "thumbnail": "thumb.jpg", "face_crop": "face_crop.jpg",
            "reconstruction": "reconstruction.npz", "uv_texture": "uv_texture.png",
            "face_mask": "face_mask.png", "mesh": "mesh.obj",
            "ldm106_raw": "ldm106_raw.csv", "ldm106_chronology": "ldm106_chronology.csv",
            "ldm134_raw": "ldm134_raw.csv", "ldm134_chronology": "ldm134_chronology.csv",
        },
        "pose_bin": pose_bin,
    }


def _write_photo_dir(photo_dir: Path, photo_id: str, date_iso: str, pose_bin: str,
                     yaw: float, pitch: float, roll: float, quality: float,
                     confidence: float, seed: int, source_relative_path: str) -> None:
    """Write a complete Stage-1 photo directory (every artifact the API reads)."""
    photo_dir.mkdir(parents=True, exist_ok=True)
    canonical_yaw = CANONICAL_YAW[pose_bin]

    raw106 = _face_landmarks(106, yaw, pitch, roll, seed)
    raw134 = _face_landmarks(134, yaw, pitch, roll, seed + 1)
    # chronology-aligned = canonical pose + tiny per-frame noise (same person baseline)
    chr106 = _face_landmarks(106, canonical_yaw, 0.0, 0.0, seed + 2)
    chr134 = _face_landmarks(134, canonical_yaw, 0.0, 0.0, seed + 3)
    visible106 = np.ones(106, bool)
    visible134 = np.ones(134, bool)
    idx106 = np.arange(106, dtype=np.int64) * 3 + 7
    idx134 = np.arange(134, dtype=np.int64) * 2 + 5

    _write_landmark_csv(photo_dir / "ldm106_raw.csv", raw106, visible106, idx106, np.full(106, confidence, np.float32))
    _write_landmark_csv(photo_dir / "ldm106_chronology.csv", chr106, visible106, idx106, np.full(106, confidence, np.float32))
    _write_landmark_csv(photo_dir / "ldm134_raw.csv", raw134, visible134, idx134, np.full(134, confidence, np.float32))
    _write_landmark_csv(photo_dir / "ldm134_chronology.csv", chr134, visible134, idx134, np.full(134, confidence, np.float32))

    # Mesh: object-space mesh (posed) + chronology-aligned mesh (canonical)
    V_obj, F, UV = _face_mesh(seed, yaw, pitch, roll)
    V_chr, _, _ = _face_mesh(seed, canonical_yaw, 0.0, 0.0)
    identity = V_chr * 1.0
    alpha_id = np.full(128, 0.001, np.float32)
    alpha_exp = np.zeros(64, np.float32)
    np.savez_compressed(
        photo_dir / "reconstruction.npz",
        vertices_object=V_obj.astype(np.float32),
        vertices_identity_only=identity.astype(np.float32),
        vertices_object_normalized=V_obj.astype(np.float32),
        vertices_bin_canonical=V_chr.astype(np.float32),
        vertices_chronology_aligned=V_chr.astype(np.float32),
        vertices_camera=V_obj.astype(np.float32),
        vertices_image_224=V_obj.astype(np.float32),
        triangles=F,
        uv_coords=UV,
        ldm106_vertex_indices=idx106,
        ldm134_vertex_indices=idx134,
        ldm106_object_normalized=raw106,
        ldm134_object_normalized=raw134,
        ldm106_identity_only=raw106,
        ldm134_identity_only=raw134,
        ldm106_visible=visible106,
        ldm134_visible=visible134,
        alpha_id=alpha_id,
        alpha_exp=alpha_exp,
        angle_deg_pitch_yaw_roll=np.asarray([pitch, yaw, roll], np.float32),
        angle_rad=np.asarray([math.radians(pitch), math.radians(yaw), math.radians(roll)], np.float32),
        canonical_rotation_row_matrix=np.eye(3, dtype=np.float32),
        chronology_correction_matrix=np.eye(3, dtype=np.float32),
        chronology_target_pose=np.asarray([0.0, canonical_yaw, 0.0], np.float32),
        canonical_yaw=np.asarray([canonical_yaw], np.float32),
    )

    _make_photo_jpegs(photo_dir, seed)
    _make_texture(photo_dir, seed + 5)

    # small PNG masks
    if Image is not None:
        mask = Image.new("L", (96, 96), 200)
        mask.save(photo_dir / "face_mask.png")
    else:
        (photo_dir / "face_mask.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    # minimal mesh.obj / mtl (inventory only checks existence)
    with (photo_dir / "mesh.obj").open("w", encoding="utf-8") as handle:
        handle.write("# synthetic fixture mesh\n")
        for v in V_chr[:64]:
            handle.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
        handle.write("usemtl synthetic\n")
        for f in F[:32]:
            handle.write(f"f {f[0]+1} {f[1]+1} {f[2]+1}\n")
    (photo_dir / "mesh.mtl").write_text("newmtl synthetic\nKd 0.8 0.7 0.6\n", encoding="utf-8")

    (photo_dir / "texture.json").write_text(json.dumps({
        "schema": "deeputin-texture-quality-v1", "photo_id": photo_id,
        "quality": {"status": "pass", "score": quality},
        "uv": {"observed_coverage": quality * 0.85},
    }), encoding="utf-8")
    (photo_dir / "validation.json").write_text(json.dumps({
        "schema": "deeputin-stage1-validation-v1", "photo_id": photo_id,
        "status": "complete", "errors": [],
    }), encoding="utf-8")
    (photo_dir / "info.json").write_text(json.dumps(
        _info_json(photo_id, date_iso, pose_bin, yaw, pitch, roll, quality, confidence, source_relative_path),
        ensure_ascii=False, indent=1), encoding="utf-8")
    (photo_dir / "skin_zone_quality.json").write_text(json.dumps({
        "photo_id": photo_id, "active_zone_count": 8, "zones": [],
    }), encoding="utf-8")


def _timeline_row(photo_id: str, date_iso: str, pose_bin: str, yaw: float, pitch: float,
                  roll: float, quality: float, confidence: float, sequence: int) -> dict:
    return {
        "photo_id": photo_id, "date": date_iso, "same_date_sequence": sequence,
        "pose_bin": pose_bin, "yaw": f"{yaw:.3f}", "pitch": f"{pitch:.3f}", "roll": f"{roll:.3f}",
        "combined_visible_fraction": f"{quality:.4f}", "skin_mask_coverage": f"{quality*0.9:.4f}",
        "uv_observed_coverage": f"{quality*0.85:.4f}",
        "date_provenance_status": "confirmed", "near_duplicate_of": "",
        "source_provenance_status": "provided",
        "source_relative_path": f"fixture/{photo_id}.jpg",
    }


def _build_stage1(stage1_root: Path, photos: list[tuple[str, str, str, float, float, float, float, float, int]],
                  manifest_label: str, seed_base: int) -> None:
    rows = []
    for i, (photo_id, date_iso, pose_bin, yaw, pitch, roll, quality, confidence, seq) in enumerate(photos):
        _write_photo_dir(
            stage1_root / photo_id, photo_id, date_iso, pose_bin, yaw, pitch, roll,
            quality, confidence, seed_base + i * 7, f"fixture/{photo_id}.jpg",
        )
        rows.append(_timeline_row(photo_id, date_iso, pose_bin, yaw, pitch, roll, quality, confidence, seq))
    rows.sort(key=lambda r: (r["date"], r["same_date_sequence"]))
    import csv
    with (stage1_root / "main_timeline.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (stage1_root / "stage1_manifest.json").write_text(json.dumps({
        "schema": "deeputin-stage1-manifest-v1.4", "label": manifest_label,
        "status": "complete", "record_count": len(rows),
        "date_range": {"start": rows[0]["date"], "end": rows[-1]["date"]},
        "created_at_utc": "2026-08-04T00:00:00Z",
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def _build_calibration(cal_root: Path, frames_per_person_bin: int, seed_base: int) -> None:
    photos: list[tuple[str, str, str, float, float, float, float, float, int]] = []
    index_rows: list[dict] = []
    seq = 0
    for person in range(1, CAL_PERSONS + 1):
        for bin_index, pose_bin in enumerate(POSE_BINS):
            yaw_base = CANONICAL_YAW[pose_bin]
            for frame in range(frames_per_person_bin):
                photo_id = f"cal_p{person:02d}_b{bin_index+1:02d}_f{frame+1:03d}"
                yaw = yaw_base + (frame - frames_per_person_bin / 2) * 0.6
                pitch = 2.0 * math.sin(frame * 1.7)
                roll = 1.2 * math.cos(frame)
                quality = min(1.0, 0.62 + 0.3 * abs(math.sin(frame * 0.9)))
                confidence = 0.7 + 0.25 * abs(math.cos(frame * 1.3))
                photos.append((photo_id, "2000-01-01", pose_bin, yaw, pitch, roll, quality, confidence, seq))
                index_rows.append({
                    "photo_id": photo_id, "dataset_id": f"person_{person:02d}",
                    "person": f"person_{person:02d}", "pose_bin": pose_bin,
                    "frame_index": frame, "date": "",
                })
                seq += 1
    _build_stage1(cal_root, photos, "synthetic calibration stage1", seed_base)
    import csv
    with (cal_root / "all_calibration_index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(index_rows[0].keys()))
        writer.writeheader()
        writer.writerows(index_rows)


def _build_main(stage1_root: Path, main_photos: int, seed_base: int) -> None:
    photos: list[tuple[str, str, str, float, float, float, float, float, int]] = []
    start = date(1999, 1, 4)
    end = date(2026, 8, 1)
    span_days = (end - start).days
    # deterministic pseudo-random spread so every bin covers the whole range
    rng = np.random.default_rng(seed_base + 1000)
    per_bin = max(1, main_photos // len(POSE_BINS))
    seq = 0
    for bin_index, pose_bin in enumerate(POSE_BINS):
        yaw_base = CANONICAL_YAW[pose_bin]
        offsets = np.sort(rng.uniform(0, span_days, per_bin).astype(int))
        for k, offset in enumerate(offsets):
            d = start + timedelta(days=int(offset))
            photo_id = f"m_{d.strftime('%Y%m%d')}_{pose_bin}_{k+1:03d}"
            yaw = yaw_base + rng.normal(0, 1.5)
            pitch = rng.normal(0, 1.2)
            roll = rng.normal(0, 1.0)
            quality = min(1.0, max(0.3, rng.normal(0.82, 0.09)))
            confidence = min(1.0, max(0.5, rng.normal(0.88, 0.06)))
            photos.append((photo_id, d.isoformat(), pose_bin, yaw, pitch, roll, quality, confidence, seq))
            seq += 1
    _build_stage1(stage1_root, photos, "synthetic main stage1", seed_base)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="destination root (storage + calibration will be created inside)")
    parser.add_argument("--main-photos", type=int, default=126, help="main dataset photo count (spread over 9 bins)")
    parser.add_argument("--cal-frames", type=int, default=504, help="calibration frame count (7 persons × 9 bins × N)")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    root = args.root.resolve()
    storage = root / "storage"
    cal = root / "calibration"
    frames_per_person_bin = max(1, args.cal_frames // (CAL_PERSONS * len(POSE_BINS)))
    _build_main(storage / "stage1", args.main_photos, args.seed)
    _build_calibration(cal, frames_per_person_bin, args.seed + 50)
    print(json.dumps({
        "root": str(root),
        "storage": str(storage),
        "calibration": str(cal),
        "main_photos": args.main_photos,
        "cal_frames": CAL_PERSONS * len(POSE_BINS) * frames_per_person_bin,
        "note": "Set DEEPUTIN_STORAGE_ROOT and DEEPUTIN_CALIBRATION_ROOT to these paths.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
