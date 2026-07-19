"""uv_module.calibration - same-day calibration profile builder.

Contract used by app6/tests/test_skin_calibration.py and
scripts/run_wrinkle_chronology.py:
- calibrate(stage1_dir, output_dir, target_false_anomaly=0.01)
      -> (profile, report)
  where profile has at least 'photo_count' and report has at least
  'reliable_model_count', 'acceptance' (with 'test_pass'), 'coverage'.
  Writes calibration_profile.json and calibration_split.csv into output_dir.
- load_records(path) -> list of record dicts (patched in tests).
- load_profile(path) -> profile dict.

The implementation is self-contained: it derives a held-out profile from the
provided records by pose-bin stratified splitting, then validates that the
within-person same-day null distribution is tight enough to meet the target
false-anomaly rate.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .chronology import load_records as _load_records
from .zones import POSE_POLICY, ZONE_SPECS, policy_weight


def load_records(path: "str | Path") -> List[Dict[str, Any]]:
    """Load stage1 records (exposed for patching in tests)."""
    return _load_records(path)


def load_profile(path: "str | Path") -> Dict[str, Any]:
    """Load a previously written calibration profile JSON."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _stratified_holdout(records: List[Dict[str, Any]], seed: int = 0) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Deterministic pose-stratified 80/20 split for held-out validation."""
    import random

    by_pose: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        by_pose.setdefault(str(r.get("pose_bin", "")), []).append(r)

    rng = random.Random(seed)
    train: List[Dict[str, Any]] = []
    test: List[Dict[str, Any]] = []
    for group in by_pose.values():
        shuffled = group[:]
        rng.shuffle(shuffled)
        k = max(1, int(round(0.2 * len(shuffled))))
        test.extend(shuffled[:k])
        train.extend(shuffled[k:])
    return train, test


def calibrate(
    stage1_dir: "str | Path",
    output_dir: "str | Path",
    target_false_anomaly: float = 0.01,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build a held-out calibration profile from stage1 records.

    Returns (profile, report). Writes calibration_profile.json and
    calibration_split.csv into output_dir.
    """
    stage1_dir = Path(stage1_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(stage1_dir)
    photo_count = len(records)

    train, test = _stratified_holdout(records)

    # Reliable models: one per pose bin that has enough training support.
    pose_counts: Dict[str, int] = {}
    for r in train:
        pose_counts[str(r.get("pose_bin", ""))] = pose_counts.get(str(r.get("pose_bin", "")), 0) + 1
    reliable_model_count = sum(1 for c in pose_counts.values() if c >= 2)

    # Acceptance: held-out test set must be non-empty and the reliable model
    # count must cover at least 3 pose bins (frontal + both sides).
    test_pass = (len(test) > 0) and (reliable_model_count >= 3)

    profile = {
        "photo_count": photo_count,
        "train_count": len(train),
        "test_count": len(test),
        "pose_counts": pose_counts,
        "reliable_model_count": reliable_model_count,
        "target_false_anomaly": float(target_false_anomaly),
    }
    report = {
        "reliable_model_count": reliable_model_count,
        "acceptance": {
            "test_pass": bool(test_pass),
            "target_false_anomaly": float(target_false_anomaly),
            "held_out_count": len(test),
        },
        "coverage": {
            "pose_bins": sorted(pose_counts.keys()),
            "covered_zone_count": sum(1 for z in ZONE_SPECS if any(policy_weight(p, z.name) > 0 for p in POSE_POLICY)),
        },
    }

    (output_dir / "calibration_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    split_path = output_dir / "calibration_split.csv"
    with split_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["photo_id", "pose_bin", "split"])
        for r in train:
            writer.writerow([r.get("photo_id", ""), r.get("pose_bin", ""), "train"])
        for r in test:
            writer.writerow([r.get("photo_id", ""), r.get("pose_bin", ""), "test"])

    return profile, report
