"""Synthetic Stage 1 output generator.

The real pipeline needs ~421 MB of model weights, a mounted photo archive and a
CUDA-capable machine. That made Stage 2 effectively untestable, which is a large
part of why so many bugs survived: nothing could be exercised without the whole
world present.

This module writes a Stage 1 output tree that satisfies contract.py exactly -
the same index, the same per-photo files, the same NPZ keys and shapes - built
from a deterministic synthetic face. That makes it possible to:

  * run the admin panel and its dry-run planner with no weights,
  * unit-test loaders, gates and pair planning,
  * inject a known change at a known date in a known zone and assert that
    Stage 2 finds it (a real golden fixture, not a smoke test).

Nothing here is used in production runs.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import contract

FIXTURE_VERSION = "stage2v2-fixture-v1"


@dataclass(frozen=True)
class FixtureSpec:
    """Description of a synthetic dataset."""

    dates: tuple[str, ...] = (
        "1999-01-11",
        "2003-06-02",
        "2008-09-14",
        "2012-03-05",
        "2017-11-21",
        "2022-04-08",
    )
    #: Pose bins to emit a photo in, for every date.
    pose_bins: tuple[str, ...] = ("frontal", "left_quarter", "right_quarter")
    #: Photos per (date, bin). >1 exercises the same-day noise ceiling.
    per_day: int = 1
    #: Landmark noise, in normalized object units.
    noise_sigma: float = 0.0015
    #: Inject a permanent change of this magnitude from `change_after`.
    change_magnitude: float = 0.0
    change_after: str = "2012-03-05"
    #: Landmark indices (in the 134 scheme) that the injected change moves.
    change_indices: tuple[int, ...] = tuple(range(60, 76))
    detection_confidence: float = 0.93
    texture_quality: float = 0.82
    skin_quality: float = 0.78
    alignment_quality: float = 0.71
    seed: int = 20260101


def _base_face(rng: np.random.Generator) -> np.ndarray:
    """A crude but stable synthetic face: an ellipsoid shell of vertices."""
    n = contract.MESH_COUNT
    idx = np.arange(n, dtype=np.float64)
    # Deterministic quasi-uniform points on a sphere, then squashed into a
    # face-like ellipsoid. Not anatomical - only shape stability matters.
    golden = math.pi * (3.0 - math.sqrt(5.0))
    z = 1.0 - 2.0 * idx / max(n - 1, 1)
    radius = np.sqrt(np.clip(1.0 - z * z, 0.0, None))
    theta = golden * idx
    verts = np.stack(
        [radius * np.cos(theta) * 0.75, radius * np.sin(theta) * 1.0, z * 0.6],
        axis=1,
    )
    verts[:, 2] += 0.25 * np.exp(-(verts[:, 0] ** 2 + verts[:, 1] ** 2) / 0.2)
    return verts.astype(np.float32)


def _rotation(pitch: float, yaw: float, roll: float) -> np.ndarray:
    p, y, r = (math.radians(v) for v in (pitch, yaw, roll))
    rx = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    rz = np.array([[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]])
    return (rz @ ry @ rx).astype(np.float32)


def _yaw_for_bin(bin_name: str) -> float:
    return float(contract.BIN_CANONICAL_YAW.get(bin_name, 0.0))


def _landmark_indices(count: int) -> np.ndarray:
    """Deterministic, evenly spread vertex indices standing in for landmarks."""
    return np.linspace(0, contract.MESH_COUNT - 1, count).astype(np.int32)


def build(root: Path, spec: FixtureSpec | None = None) -> dict:
    """Write a complete synthetic Stage 1 tree at `root`. Returns a manifest."""
    spec = spec or FixtureSpec()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(spec.seed)

    base = _base_face(rng)
    idx106 = _landmark_indices(contract.LDM106)
    idx134 = _landmark_indices(contract.LDM134)
    triangles = np.zeros((contract.TRIANGLE_COUNT, 3), dtype=np.int32)
    step = max(contract.MESH_COUNT // contract.TRIANGLE_COUNT, 1)
    for t in range(contract.TRIANGLE_COUNT):
        a = (t * step) % contract.MESH_COUNT
        triangles[t] = (a, (a + 1) % contract.MESH_COUNT, (a + 2) % contract.MESH_COUNT)

    index_rows: list[dict] = []
    manifest = {
        "fixture_version": FIXTURE_VERSION,
        "root": str(root),
        "photos": [],
        "injected_change": {
            "magnitude": spec.change_magnitude,
            "after": spec.change_after,
            "landmark_indices": list(spec.change_indices),
        },
    }

    for date in spec.dates:
        changed = spec.change_magnitude > 0 and date >= spec.change_after
        for bin_name in spec.pose_bins:
            for seq in range(1, spec.per_day + 1):
                suffix = "" if seq == 1 else f"_{seq}"
                photo_id = f"{date.replace('-', '_')}{suffix}__{bin_name}"
                yaw = _yaw_for_bin(bin_name) + float(rng.normal(0, 1.2))
                pitch = float(rng.normal(0, 1.0))
                roll = float(rng.normal(0, 0.8))

                verts = base.copy()
                if changed:
                    moved = idx134[list(spec.change_indices)]
                    verts[moved, 1] += spec.change_magnitude
                    verts[moved, 2] += spec.change_magnitude * 0.5

                identity_only = verts.copy()
                verts = verts + rng.normal(0, spec.noise_sigma, verts.shape).astype(np.float32)

                rotation = _rotation(pitch, yaw, roll)
                # Visibility: a vertex is front-facing if its outward normal
                # (approximated by the vertex direction) points at the camera.
                direction = verts / (np.linalg.norm(verts, axis=1, keepdims=True) + 1e-9)
                camera = np.array([0, 0, 1], dtype=np.float32)
                facing = (direction @ (rotation.T @ camera)) > 0.15
                renderer_visible = facing.copy()
                combined = facing & renderer_visible

                photo_dir = root / photo_id
                photo_dir.mkdir(parents=True, exist_ok=True)

                npz = {
                    "alpha_id": rng.normal(0, 1, 80).astype(np.float32),
                    "alpha_exp": rng.normal(0, 0.2, 64).astype(np.float32),
                    "angle_deg_pitch_yaw_roll": np.array(
                        [pitch, yaw, roll], dtype=np.float32
                    ),
                    "rotation_matrix": rotation,
                    "normalization_center": verts.mean(axis=0).astype(np.float32),
                    "normalization_scale": np.float32(
                        float(np.linalg.norm(verts - verts.mean(axis=0), axis=1).mean())
                    ),
                    "ldm106_vertex_indices": idx106,
                    "ldm134_vertex_indices": idx134,
                    "ldm106_object_normalized": verts[idx106],
                    "ldm134_object_normalized": verts[idx134],
                    "ldm106_identity_only": identity_only[idx106],
                    "ldm134_identity_only": identity_only[idx134],
                    "ldm106_visible": combined[idx106],
                    "ldm134_visible": combined[idx134],
                    # optional but written by real Stage 1
                    "front_facing": facing,
                    "renderer_visible": renderer_visible,
                    "vertices_object_normalized": verts,
                    "vertices_identity_only": identity_only,
                    "triangles": triangles,
                    "full_mesh_visible_packbits": np.packbits(combined),
                    "bin_canonical": np.array(
                        [_yaw_for_bin(bin_name)], dtype=np.float32
                    ),
                }
                np.savez_compressed(photo_dir / "reconstruction.npz", **npz)

                info = {
                    "schema_version": "deeputin-photo-v2.4-chronology-alignment",
                    "photo_id": photo_id,
                    "source_relative_path": f"synthetic/{photo_id}.jpg",
                    "date": date,
                    "same_date_sequence": seq,
                    "pose_bin": bin_name,
                    "image": {"pixels": 4000000, "width": 2000, "height": 2000},
                    "skin_quality_score": spec.skin_quality,
                    "skin_quality_status": "ok",
                    "quality_summary": {
                        "supported_forehead_wrinkle_pose_v1": bin_name == "frontal"
                    },
                    "chronology": {
                        "alignment_quality": spec.alignment_quality,
                        "corner_lift_ioc": -0.008,
                        "jaw_open_ratio": 0.14,
                        "smile_detected": False,
                        "jaw_open_detected": False,
                        "jaw_open_degree": 2.1,
                        "detection_confidence": spec.detection_confidence,
                        "face_area_ratio": 0.22,
                        "coordinate_noise_sigma": spec.noise_sigma,
                        "reprojection_rmse": 1.4,
                    },
                    "date_provenance": {
                        "exif_date": None,
                        "source_claimed_date": date,
                        "source_claimed_delta_days": 0,
                        "delta_days": 0,
                        "conflict_sources": [],
                    },
                    "source_provenance": "synthetic-fixture",
                    "source_digest": f"sha256:{photo_id}",
                    "perceptual_dhash": f"{abs(hash(photo_id)) % (1 << 60):015x}",
                    "near_duplicate_of": None,
                }
                (photo_dir / "info.json").write_text(
                    json.dumps(info, indent=2), encoding="utf-8"
                )
                (photo_dir / "texture.json").write_text(
                    json.dumps(
                        {
                            "quality": {
                                "status": "ok",
                                "score": spec.texture_quality,
                            }
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                (photo_dir / "validation.json").write_text(
                    json.dumps(
                        {
                            "schema_version": (
                                "deeputin-validation-v2.4-chronology-alignment"
                            ),
                            "photo_id": photo_id,
                            "status": "complete",
                            "errors": [],
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                index_rows.append(
                    {
                        "photo_id": photo_id,
                        "date": date,
                        "same_date_sequence": seq,
                        "pose_bin": bin_name,
                    }
                )
                manifest["photos"].append(
                    {"photo_id": photo_id, "date": date, "pose_bin": bin_name}
                )

    with (root / contract.MAIN_INDEX).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(contract.MAIN_INDEX_COLUMNS))
        writer.writeheader()
        writer.writerows(index_rows)

    (root / "fixture_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Write a synthetic Stage 1 tree")
    parser.add_argument("output")
    parser.add_argument("--per-day", type=int, default=1)
    parser.add_argument("--change", type=float, default=0.0)
    parser.add_argument("--change-after", default="2012-03-05")
    args = parser.parse_args(argv)

    manifest = build(
        Path(args.output),
        FixtureSpec(
            per_day=args.per_day,
            change_magnitude=args.change,
            change_after=args.change_after,
        ),
    )
    print(f"wrote {len(manifest['photos'])} synthetic photos to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
