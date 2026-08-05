"""Calibration Workspace API (Iteration 10).

Dashboard over the calibration dataset (7 persons × 9 pose bins) and the
calibration-derived thresholds of the active Stage 2 run:

- per-person × per-bin frame counts and same-person pair counts,
- LOPO / leave-one-dataset-out sensitivity summary of the active run,
- per-(pose bin, landmark count) same-person noise references (median/MAD/p95)
  from the active run's `point_noise_model.npz`,
- the *distinction* between diagnostic thresholds (manual sliders) and
  calibrated thresholds (derived from calibration data). The UI must never
  label a manual slider as "calibrated".

Everything here is read-only.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from .calibration import POSE_BINS
from .runtime_config import load_runtime_paths

CALIBRATION_WORKSPACE_SCHEMA = "deeputin-calibration-workspace-v1.0"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


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


def workspace_dashboard() -> dict[str, Any]:
    """Per-person × per-bin coverage and pair counts from calibration index."""
    paths = load_runtime_paths()
    root = paths.calibration_root
    index_path = root / "all_calibration_index.csv"
    if not index_path.is_file():
        return {
            "schema": CALIBRATION_WORKSPACE_SCHEMA,
            "status": "unavailable",
            "detail": f"all_calibration_index.csv not found under {root}",
        }

    rows = _read_csv(index_path)
    persons = sorted({str(r.get("dataset_id") or r.get("person") or "?").strip() for r in rows})
    bins: dict[str, dict[str, int]] = {}
    for pose in POSE_BINS:
        bins[pose] = {person: 0 for person in persons}
    for row in rows:
        person = str(row.get("dataset_id") or row.get("person") or "?").strip()
        pose = str(row.get("pose_bin") or "unknown")
        if pose in bins and person in bins[pose]:
            bins[pose][person] += 1

    person_rows = []
    for person in persons:
        counts = [bins[pose][person] for pose in POSE_BINS]
        person_rows.append({
            "person": person,
            "total": sum(counts),
            "per_bin": {pose: bins[pose][person] for pose in POSE_BINS},
            "covered_bins": sum(1 for count in counts if count > 0),
        })

    per_bin_rows = []
    for pose in POSE_BINS:
        counts = [bins[pose][person] for person in persons]
        total = sum(counts)
        # same-person adjacent pair estimate (chronology-free calibration frames)
        adjacent_pairs = sum(max(0, count - 1) for count in counts)
        per_bin_rows.append({
            "pose": pose,
            "total": total,
            "persons_with_frames": sum(1 for count in counts if count > 0),
            "adjacent_pair_estimate": adjacent_pairs,
        })

    # completeness: a bin is "complete" when all 7 persons have ≥2 frames
    complete_bins = [row["pose"] for row in per_bin_rows if row["persons_with_frames"] == len(persons) and row["total"] >= 2 * len(persons)]

    return {
        "schema": CALIBRATION_WORKSPACE_SCHEMA,
        "status": "ready",
        "root": str(root),
        "person_count": len(persons),
        "persons": person_rows,
        "pose_bins": per_bin_rows,
        "complete_bins": complete_bins,
        "covered_bin_count": len(complete_bins),
        "total_frames": sum(row["total"] for row in per_bin_rows),
        "total_pair_estimate": sum(row["adjacent_pair_estimate"] for row in per_bin_rows),
        "not_a_verdict": True,
    }


def calibrated_thresholds() -> dict[str, Any]:
    """Calibrated same-person noise references from the active Stage 2 run.

    Returns per (pose bin, count) scalar summary (median of per-point medians,
    MAD, p95) plus the per-point arrays, and LOPO sensitivity if available.
    """
    run = _active_stage2_run()
    if run is None:
        return {
            "schema": CALIBRATION_WORKSPACE_SCHEMA,
            "status": "unavailable",
            "detail": "no completed Stage 2 run — run Stage 2 first to obtain calibrated references",
            "calibrated": False,
        }

    references: list[dict[str, Any]] = []
    npz_path = run / "point_noise_model.npz"
    if npz_path.is_file():
        try:
            with np.load(npz_path, allow_pickle=False) as z:
                for pose in POSE_BINS:
                    for count in (106, 134):
                        prefix = f"{pose}__ldm{count}"
                        if f"{prefix}__median" not in z.files:
                            continue
                        median = np.asarray(z[f"{prefix}__median"], np.float32)
                        mad = np.asarray(z[f"{prefix}__mad"], np.float32) if f"{prefix}__mad" in z.files else None
                        p95 = np.asarray(z[f"{prefix}__p95"], np.float32) if f"{prefix}__p95" in z.files else None
                        n = np.asarray(z[f"{prefix}__count"], np.int32) if f"{prefix}__count" in z.files else None
                        references.append({
                            "pose_bin": pose,
                            "count": count,
                            "supported_points": int(n.sum()) if n is not None and n.size else None,
                            "scalar": {
                                "median": float(np.nanmedian(median)) if median.size else None,
                                "mad": float(np.nanmedian(mad)) if mad is not None and mad.size else None,
                                "p95": float(np.nanmedian(p95)) if p95 is not None and p95.size else None,
                            },
                            "per_point": {
                                "median": median.reshape(-1).tolist(),
                                "mad": mad.reshape(-1).tolist() if mad is not None else None,
                                "p95": p95.reshape(-1).tolist() if p95 is not None else None,
                            },
                        })
        except (OSError, ValueError):
            pass

    sensitivity = _read_json(run / "calibration_sensitivity.json")
    mesh_noise = _read_json(run / "mesh_noise_model.json")
    manifest = _read_json(run / "analysis_manifest.json")
    return {
        "schema": CALIBRATION_WORKSPACE_SCHEMA,
        "status": "ready",
        "calibrated": bool(references),
        "run_id": run.name,
        "run_directory": str(run),
        "references": references,
        "sensitivity": sensitivity,
        "mesh_noise_model": mesh_noise,
        "manifest": {
            "record_count": (manifest or {}).get("main_record_count"),
            "pair_count": (manifest or {}).get("pair_count"),
        },
        "distinction": {
            "diagnostic_threshold": "manual slider — expert reference only, never called calibrated",
            "calibrated_threshold": "derived from 7-person same-person calibration noise (LOPO-validated)",
        },
        "not_a_verdict": True,
    }
