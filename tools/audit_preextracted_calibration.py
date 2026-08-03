#!/usr/bin/env python3
"""Audit the checked-out 7-person landmark calibration corpus without inference.

This is an exploratory geometry-validation tool.  It is deliberately separate
from ``load_calibration()``: production Stage 2 still requires a provenance-
complete Stage 1 run.  The output must therefore never be used as a production
threshold or identity conclusion.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app6.archive_adapter import POSE_BINS
from app6.stage2.analysis_policy import pose_gap
from app6.stage2.core import Record, robust_rigid_align
from app6.stage2.pose_policy import BIN_NAME_TO_YAW

SPACES = ("raw", "aligned", "chronology")


def read_landmarks(path: Path, count: int = 134) -> tuple[np.ndarray, np.ndarray]:
    points = np.full((count, 3), np.nan, np.float32)
    visible = np.zeros(count, dtype=bool)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            index = int(row["landmark_id"])
            points[index] = (float(row["x"]), float(row["y"]), float(row["z"]))
            visible[index] = bool(int(float(row.get("visible", "1"))))
    if not np.isfinite(points).all():
        raise ValueError(f"non-finite or incomplete landmarks: {path}")
    return points, visible


def load(root: Path) -> tuple[list[Record], dict[str, dict[str, np.ndarray]]]:
    records: list[Record] = []
    spaces: dict[str, dict[str, np.ndarray]] = {name: {} for name in SPACES}
    for info_path in sorted(root.glob("person_*/frame_*/info.json")):
        info = json.loads(info_path.read_text(encoding="utf-8"))
        directory = info_path.parent
        pose = info.get("pose") or {}
        pose_bin = str(pose.get("pose_bin") or "")
        if pose_bin not in POSE_BINS:
            continue
        raw, visible = read_landmarks(directory / "ldm134_raw.csv")
        center = np.asarray((info.get("normalization") or {}).get("center"), dtype=np.float32)
        scale = float((info.get("normalization") or {}).get("scale", 0.0))
        if center.shape != (3,) or not np.isfinite(scale) or scale <= 0:
            raise ValueError(f"invalid object normalization: {directory}")
        record_id = f"{directory.parent.name}/{directory.name}"
        # The raw object landmarks are normalized exactly once to place them in
        # the coordinate system consumed by the production geometry comparator.
        raw_normalized = (raw - center) / scale
        records.append(Record(
            record_id=record_id, dataset_id=directory.parent.name, date=None,
            sequence=int(directory.name.removeprefix("frame_") or 0), pose_bin=pose_bin,
            angles=np.asarray([pose["pitch"], pose["yaw"], pose["roll"]], dtype=np.float32),
            ldm106=np.zeros((106, 3), dtype=np.float32), ldm134=raw_normalized,
            visible106=np.ones(106, dtype=bool), visible134=visible,
            alpha_id=np.full(80, np.nan, dtype=np.float32), alpha_exp=np.full(64, np.nan, dtype=np.float32),
            dataset_role="calibration", record_dir=str(directory),
            analysis_space="raw_object_normalized",
        ))
        spaces["raw"][record_id] = raw_normalized
        for name, filename in (("aligned", "ldm134_aligned.csv"), ("chronology", "ldm134_chronology.csv")):
            spaces[name][record_id] = read_landmarks(directory / filename)[0]
    return records, spaces


def rmse(a: Record, b: Record, points: dict[str, np.ndarray]) -> float | None:
    common = a.visible134 & b.visible134
    if int(common.sum()) < 30:
        return None
    aligned, _, _, _ = robust_rigid_align(points[b.record_id][common], points[a.record_id][common])
    return float(np.sqrt(np.mean(np.sum((aligned - points[a.record_id][common]) ** 2, axis=1))))


def auc(same: list[float], different: list[float]) -> float | None:
    if not same or not different:
        return None
    # Probability that a random different-person distance exceeds a random
    # same-person distance; tie correction makes this deterministic.
    total = len(same) * len(different)
    wins = sum((d > s) + 0.5 * (d == s) for s in same for d in different)
    return float(wins / total)


def q(values: list[float], percentile: float) -> float | None:
    return float(np.percentile(values, percentile)) if values else None


def analyze(records: list[Record], spaces: dict[str, dict[str, np.ndarray]], max_pairs: int) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[Record]] = defaultdict(list)
    by_bin: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        grouped[(record.dataset_id, record.pose_bin)].append(record)
        by_bin[record.pose_bin].append(record)
    for values in grouped.values():
        values.sort(key=lambda r: (r.angles[1], r.angles[0], r.angles[2], r.record_id))

    report: dict[str, Any] = {"record_count": len(records), "people": sorted({r.dataset_id for r in records}),
        "coverage": {person: {pose: len(grouped[(person, pose)]) for pose in POSE_BINS}
                     for person in sorted({r.dataset_id for r in records})}, "bins": {}}
    for pose in POSE_BINS:
        same: dict[str, list[float]] = {space: [] for space in SPACES}
        diff: dict[str, list[float]] = {space: [] for space in SPACES}
        accepted_same = accepted_diff = attempted_same = attempted_diff = 0
        people = sorted({r.dataset_id for r in by_bin[pose]})
        # Deterministic near-neighbour samples: avoids falsely treating all
        # video frames as independent while covering each source/person.
        for person in people:
            group = grouped[(person, pose)]
            for index, first in enumerate(group[:-1]):
                if attempted_same >= max_pairs:
                    break
                second = group[index + 1]
                attempted_same += 1
                if not pose_gap(first.angles, second.angles, pose_bin=pose).accepted:
                    continue
                accepted_same += 1
                for space in SPACES:
                    value = rmse(first, second, spaces[space])
                    if value is not None:
                        same[space].append(value)
        # Balanced adjacent-person controls, one fixed pairing per source row.
        for person_index, person in enumerate(people):
            others = [p for p in people if p != person]
            if not others:
                continue
            other = others[person_index % len(others)]
            left, right = grouped[(person, pose)], grouped[(other, pose)]
            for index, first in enumerate(left[:max_pairs]):
                second = min(right, key=lambda r: float(np.linalg.norm(first.angles - r.angles)))
                attempted_diff += 1
                if not pose_gap(first.angles, second.angles, pose_bin=pose).accepted:
                    continue
                accepted_diff += 1
                for space in SPACES:
                    value = rmse(first, second, spaces[space])
                    if value is not None:
                        diff[space].append(value)
        # Edge-to-canonical test: same person and bin; assesses whether pose
        # correction creates a less stable result at the edge of its bin.
        edge: dict[str, list[float]] = {space: [] for space in SPACES}
        canonical: dict[str, list[float]] = {space: [] for space in SPACES}
        centre = BIN_NAME_TO_YAW[pose]
        for person in people:
            group = grouped[(person, pose)]
            near = [r for r in group if abs(float(r.angles[1]) - centre) <= 3.0]
            far = [r for r in group if abs(float(r.angles[1]) - centre) >= 8.0]
            if not near or not far:
                continue
            anchor = min(near, key=lambda r: abs(float(r.angles[0])) + abs(float(r.angles[2])))
            for candidate in far[:10]:
                if not pose_gap(anchor.angles, candidate.angles, pose_bin=pose).accepted:
                    continue
                for space in SPACES:
                    value = rmse(anchor, candidate, spaces[space])
                    if value is not None:
                        edge[space].append(value)
            for candidate in near:
                if candidate.record_id == anchor.record_id or not pose_gap(anchor.angles, candidate.angles, pose_bin=pose).accepted:
                    continue
                for space in SPACES:
                    value = rmse(anchor, candidate, spaces[space])
                    if value is not None:
                        canonical[space].append(value)
        report["bins"][pose] = {
            "records": len(by_bin[pose]), "people": len(people),
            "same_pairs": {space: len(same[space]) for space in SPACES},
            "different_pairs": {space: len(diff[space]) for space in SPACES},
            "pose_gate": {"same_accepted": accepted_same, "same_attempted": attempted_same,
                           "different_accepted": accepted_diff, "different_attempted": attempted_diff},
            "discrimination": {space: {"auc_same_vs_different": auc(same[space], diff[space]),
                "same_median": q(same[space], 50), "different_median": q(diff[space], 50),
                "same_p95": q(same[space], 95), "different_p05": q(diff[space], 5)} for space in SPACES},
            "edge_to_canonical": {space: {"edge_pair_count": len(edge[space]), "near_pair_count": len(canonical[space]),
                "edge_median": q(edge[space], 50), "near_median": q(canonical[space], 50),
                "median_ratio_edge_over_near": (q(edge[space], 50) / q(canonical[space], 50)
                    if q(edge[space], 50) is not None and q(canonical[space], 50) not in (None, 0.0) else None)} for space in SPACES},
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("calibration_dataset"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-pairs-per-person-bin", type=int, default=30)
    args = parser.parse_args()
    records, spaces = load(args.input)
    report = analyze(records, spaces, args.max_pairs_per_person_bin)
    report.update({"schema": "deeputin-preextracted-calibration-audit-v1.0", "input": str(args.input),
        "coordinate_spaces": {"raw": "ldm134_raw normalized with info.normalization", "aligned": "ldm134_aligned.csv", "chronology": "ldm134_chronology.csv"},
        "limitations": ["Exploratory audit of pre-extracted artifacts; not a production threshold release.",
            "Pairs are dependent frames, not independent people; AUC is descriptive only.",
            "No texture, source-provenance, image-quality or neural-inference validation is possible from landmark CSVs alone."]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "records": len(records), "bins": len(report["bins"])}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
