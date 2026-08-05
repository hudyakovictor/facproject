"""Landmark Comparison widget API (Iteration 08).

Computes per-point 3D displacement between two Stage-1 photos in the selected
coordinate space (chronology-aligned by default — the space used for
chronological analysis), plus the same-person calibrated noise reference from
the active Stage 2 run (if any) so the widget can separate "within noise" from
"exceeds calibration" visually and numerically.

Nothing here writes to Stage 1 or Stage 2 — it is a read-only projection of
already extracted evidence.

🚨 WARNING: a displacement value is a measurement, not a verdict. Thresholds
are reference lines; exceedance is a *review trigger*, never an identity claim.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import numpy as np

from .landmark_regions import region_of
from .morphing_api import _photo_dir, _stage1_root
from .runtime_config import load_runtime_paths

LANDMARK_COMPARE_SCHEMA = "deeputin-landmark-compare-v1.0"

_LANDMARK_CSV = {
    (106, "chronology"): "ldm106_chronology.csv",
    (106, "raw"): "ldm106_raw.csv",
    (134, "chronology"): "ldm134_chronology.csv",
    (134, "raw"): "ldm134_raw.csv",
}
# spaces the widget can request; 'aligned' is an alias for chronology
SPACE_ALIASES = {"aligned": "chronology"}


def _read_landmarks(path: Path, count: int) -> tuple[np.ndarray, np.ndarray]:
    """Read (N,3) points and (N,) visibility from a Stage-1 landmark CSV."""
    points: list[list[float]] = []
    visible: list[int] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            points.append([float(row["x"]), float(row["y"]), float(row.get("z") or 0.0)])
            raw_vis = row.get("visible")
            visible.append(1 if raw_vis is not None and str(raw_vis).strip() not in ("", "0", "False", "false") else 0)
    arr = np.asarray(points, np.float32)
    if arr.shape != (count, 3):
        raise ValueError(f"expected {count} landmark rows, got {arr.shape[0]}")
    return arr, np.asarray(visible, bool)


def _active_stage2_run() -> Path | None:
    """Path of the most recent completed Stage 2 run (or None)."""
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


def _calibration_reference(stage2_run: Path | None, pose_bin: str, count: int) -> dict[str, Any] | None:
    """Per-point same-person noise reference (median/MAD/p95) for a pose bin."""
    if stage2_run is None:
        return None
    npz_path = stage2_run / "point_noise_model.npz"
    if not npz_path.is_file():
        return None
    try:
        with np.load(npz_path, allow_pickle=False) as z:
            prefix = f"{pose_bin}__ldm{count}"
            median_key = f"{prefix}__median"
            mad_key = f"{prefix}__mad"
            p95_key = f"{prefix}__p95"
            if median_key not in z.files:
                return None
            median = np.asarray(z[median_key], np.float32)
            mad = np.asarray(z[mad_key], np.float32) if mad_key in z.files else None
            p95 = np.asarray(z[p95_key], np.float32) if p95_key in z.files else None
    except (OSError, ValueError):
        return None
    return {
        "pose_bin": pose_bin,
        "count": count,
        "median": median.reshape(-1).tolist() if median.size else None,
        "mad": mad.reshape(-1).tolist() if mad is not None and mad.size else None,
        "p95": p95.reshape(-1).tolist() if p95 is not None and p95.size else None,
        "calibrated": bool(mad is not None and mad.size),
    }


def compare_landmarks(photo_a: str, photo_b: str, count: int = 134, space: str = "chronology") -> dict[str, Any]:
    """Per-point displacement between two photos in the requested space."""
    space = SPACE_ALIASES.get(space, space)
    spec = _LANDMARK_CSV.get((count, space))
    if spec is None:
        raise ValueError("supported counts: 106/134; spaces: chronology/raw")

    dir_a = _photo_dir(photo_a)
    dir_b = _photo_dir(photo_b)
    points_a, vis_a = _read_landmarks(dir_a / spec, count)
    points_b, vis_b = _read_landmarks(dir_b / spec, count)

    delta = points_b.astype(np.float64) - points_a.astype(np.float64)
    magnitude = np.linalg.norm(delta, axis=1).astype(np.float32)
    common_visible = vis_a & vis_b

    finite = np.isfinite(magnitude)
    measured = finite & common_visible
    rms = float(np.sqrt(np.mean(np.square(magnitude[measured])))) if measured.any() else None
    p95 = float(np.percentile(magnitude[measured], 95)) if measured.any() else None
    max_val = float(np.max(magnitude[measured])) if measured.any() else None

    # pose bins of both photos (from info.json)
    def _pose(photo_id: str) -> str:
        info_path = _photo_dir(photo_id) / "info.json"
        if info_path.is_file():
            try:
                import json
                payload = json.loads(info_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("pose_bin"):
                    return str(payload["pose_bin"])
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        return "unknown"

    pose_a, pose_b = _pose(photo_a), _pose(photo_b)
    pose_bin = pose_a if pose_a == pose_b else "cross_bin"

    stage2_run = _active_stage2_run()
    calibration = _calibration_reference(stage2_run, pose_bin, count)

    points: list[dict[str, Any]] = []
    for i in range(count):
        mag = float(magnitude[i]) if finite[i] else None
        cal_median = calibration["median"][i] if calibration and calibration.get("median") and i < len(calibration["median"]) else None
        cal_p95 = calibration["p95"][i] if calibration and calibration.get("p95") and i < len(calibration["p95"]) else None
        exceeds_p95 = bool(cal_p95 is not None and mag is not None and mag > cal_p95)
        points.append({
            "i": i,
            "region": region_of(count, i),
            "x_a": float(points_a[i, 0]), "y_a": float(points_a[i, 1]), "z_a": float(points_a[i, 2]),
            "x_b": float(points_b[i, 0]), "y_b": float(points_b[i, 1]), "z_b": float(points_b[i, 2]),
            "dx": float(delta[i, 0]), "dy": float(delta[i, 1]), "dz": float(delta[i, 2]),
            "magnitude": mag,
            "visible_a": bool(vis_a[i]), "visible_b": bool(vis_b[i]),
            "common_visible": bool(common_visible[i]),
            "calibration_median": cal_median,
            "calibration_p95": cal_p95,
            "exceeds_calibration_p95": exceeds_p95,
        })

    return {
        "schema": LANDMARK_COMPARE_SCHEMA,
        "not_a_verdict": True,
        "photo_a": photo_a,
        "photo_b": photo_b,
        "count": count,
        "space": space,
        "pose_bin": pose_bin,
        "summary": {
            "rms": rms,
            "p95": p95,
            "max": max_val,
            "common_visible": int(common_visible.sum()),
            "exceeds_calibration_p95": int(sum(1 for p in points if p["exceeds_calibration_p95"])),
            "calibrated": bool(calibration and calibration.get("calibrated")),
        },
        "calibration": calibration,
        "points": points,
    }


def pair_rms_from_csv(photo_a: str, photo_b: str, count: int = 106) -> dict[str, Any] | None:
    """Lightweight RMS displacement for the timeline tracks (no calibration).

    Used when Stage 2 has not been run yet — same CSV source, so values stay
    consistent with the full Stage 2 measurements.
    """
    try:
        payload = compare_landmarks(photo_a, photo_b, count=count, space="chronology")
    except (ValueError, FileNotFoundError):
        return None
    summary = payload["summary"]
    return {
        "photo_a": photo_a,
        "photo_b": photo_b,
        "count": count,
        "rms": summary["rms"],
        "p95": summary["p95"],
        "max": summary["max"],
        "common_visible": summary["common_visible"],
        "calibrated": summary["calibrated"],
        "exceeds_calibration_p95": summary["exceeds_calibration_p95"],
        "source": "stage1_chronology_csv",
    }


def batch_displacement(pairs: list[list[str]], count: int = 106) -> dict[str, Any]:
    """Batch displacement for timeline tracks (Iteration 07).

    Pairs are [photo_a, photo_b] string pairs. A cap protects the API from
    unbounded requests; the timeline widget pages its requests.
    """
    MAX_PAIRS = 400
    if len(pairs) > MAX_PAIRS:
        raise ValueError(f"batch too large: {len(pairs)} > {MAX_PAIRS}")
    results = []
    errors = []
    for a, b in pairs:
        result = pair_rms_from_csv(a, b, count=count)
        if result is None:
            errors.append({"photo_a": a, "photo_b": b, "error": "unavailable"})
        else:
            results.append(result)
    return {
        "schema": "deeputin-batch-displacement-v1.0",
        "count": count,
        "results": results,
        "errors": errors,
        "result_count": len(results),
        "error_count": len(errors),
    }
