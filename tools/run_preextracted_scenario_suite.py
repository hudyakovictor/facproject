#!/usr/bin/env python3
"""Execute pose-matched chronology fixtures on the pre-extracted landmark corpus.

This is a validation harness, not an identity classifier.  It intentionally
uses synthetic chronology dates and writes expected-vs-observed measurement
states.  Its purpose is to test that the geometry/pose/return logic behaves
predictably before real evidence enters Stage 1/2/3.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app6.archive_adapter import POSE_BINS
from app6.scenarios import SCENARIOS, SCENARIO_SCHEMA
from app6.stage2.analysis_policy import pose_gap
from app6.stage2.core import robust_rigid_align


@dataclass(frozen=True)
class Frame:
    person: str
    frame_id: str
    directory: Path
    pose_bin: str
    angles: np.ndarray
    points: np.ndarray
    visible: np.ndarray
    expressive: bool


def _read_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    points = np.full((134, 3), np.nan, dtype=np.float32)
    visible = np.zeros(134, dtype=bool)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            i = int(row["landmark_id"])
            points[i] = [float(row["x"]), float(row["y"]), float(row["z"])]
            visible[i] = bool(int(float(row.get("visible", "1"))))
    if not np.isfinite(points).all():
        raise ValueError(f"incomplete landmarks: {path}")
    return points, visible


def load_frames(root: Path) -> list[Frame]:
    result: list[Frame] = []
    for info_path in sorted(root.glob("person_*/frame_*/info.json")):
        info = json.loads(info_path.read_text(encoding="utf-8"))
        pose = info.get("pose") or {}
        pose_bin = str(pose.get("pose_bin") or "")
        if pose_bin not in POSE_BINS:
            continue
        directory = info_path.parent
        raw, visible = _read_csv(directory / "ldm134_raw.csv")
        norm = info.get("normalization") or {}
        center = np.asarray(norm.get("center"), dtype=np.float32)
        scale = float(norm.get("scale", 0.0))
        if center.shape != (3,) or not np.isfinite(scale) or scale <= 0:
            continue
        chronology = info.get("chronology") or {}
        result.append(Frame(
            person=directory.parent.name,
            frame_id=str(info.get("photo_id") or directory.name), directory=directory,
            pose_bin=pose_bin,
            angles=np.asarray([pose.get("pitch"), pose.get("yaw"), pose.get("roll")], dtype=np.float32),
            points=(raw - center) / scale, visible=visible,
            expressive=bool(chronology.get("smile_detected") or chronology.get("jaw_open_detected")),
        ))
    return result


def distance(a: Frame, b: Frame) -> float | None:
    common = a.visible & b.visible
    if int(common.sum()) < 30:
        return None
    aligned, _, _, _ = robust_rigid_align(b.points[common], a.points[common])
    return float(np.sqrt(np.mean(np.sum((aligned - a.points[common]) ** 2, axis=1))))


def angular_cost(a: Frame, b: Frame) -> float:
    # Lower is better but only after the production pose gate has admitted it.
    return float(np.linalg.norm((a.angles - b.angles) / np.asarray([3.0, 6.0, 5.0])))


def choose_sequence(pattern: str, pose_bin: str, grouped: dict[tuple[str, str], list[Frame]]) -> tuple[list[Frame] | None, str]:
    roles = sorted(set(pattern))
    # A role repeated four times needs four distinct neutral frames.  Select
    # people by usable coverage, not lexicographic person ID, otherwise a
    # single all-expressive person would block every fixture in that bin.
    candidates_by_role: dict[str, list[str]] = {}
    for role in roles:
        required = pattern.count(role)
        candidates_by_role[role] = sorted(
            (person for person, bin_name in grouped
             if bin_name == pose_bin and sum(not f.expressive for f in grouped[(person, pose_bin)]) >= required),
            key=lambda person: (-sum(not f.expressive for f in grouped[(person, pose_bin)]), person),
        )
    role_people: dict[str, str] = {}
    used: set[str] = set()
    for role in roles:
        person = next((candidate for candidate in candidates_by_role[role] if candidate not in used), None)
        if person is None:
            return None, "insufficient_distinct_people_with_neutral_coverage"
        role_people[role] = person
        used.add(person)
    pools = {role: [f for f in grouped[(person, pose_bin)] if not f.expressive][:30]
             for role, person in role_people.items()}
    selected: list[Frame] = []
    # Greedy constrained selection: each next frame is closest in 3-axis pose
    # to the preceding frame, but it must be distinct for repeated roles.
    for role in pattern:
        candidates = [frame for frame in pools[role] if frame.frame_id not in {x.frame_id for x in selected}]
        if not candidates:
            return None, "not_enough_distinct_frames"
        if not selected:
            frame = min(candidates, key=lambda x: float(np.linalg.norm(x.angles)))
        else:
            valid = [x for x in candidates if pose_gap(selected[-1].angles, x.angles, pose_bin=pose_bin).accepted]
            if not valid:
                return None, "no_cross_step_pose_matched_frame"
            frame = min(valid, key=lambda x: angular_cost(selected[-1], x))
        selected.append(frame)
    return selected, ""


def thresholds(frames: list[Frame]) -> dict[str, float]:
    groups: dict[tuple[str, str], list[Frame]] = defaultdict(list)
    for frame in frames:
        if not frame.expressive:
            groups[(frame.person, frame.pose_bin)].append(frame)
    out: dict[str, float] = {}
    for pose_bin in POSE_BINS:
        values: list[float] = []
        for (person, pose), rows in groups.items():
            if pose != pose_bin:
                continue
            rows = sorted(rows, key=lambda x: x.frame_id)
            for a, b in zip(rows, rows[1:]):
                if pose_gap(a.angles, b.angles, pose_bin=pose_bin).accepted:
                    d = distance(a, b)
                    if d is not None:
                        values.append(d)
        if len(values) >= 5:
            out[pose_bin] = float(np.percentile(values, 95))
    return out


def evaluate(pattern: str, frames: list[Frame], threshold: float) -> dict[str, Any]:
    pairs = []
    observed_changes: list[int] = []
    expected_changes = [index for index in range(1, len(pattern)) if pattern[index] != pattern[index - 1]]
    for index, (a, b) in enumerate(zip(frames, frames[1:]), 1):
        gap = pose_gap(a.angles, b.angles, pose_bin=a.pose_bin)
        d = distance(a, b) if gap.accepted else None
        transition = d is not None and d > threshold
        if transition:
            observed_changes.append(index)
        pairs.append({"boundary_after_step": index, "from": a.frame_id, "to": b.frame_id,
                      "same_role": pattern[index - 1] == pattern[index], "rmse": d,
                      "threshold_p95": threshold, "transition": transition,
                      "pose_gate": {"accepted": gap.accepted, "reason": gap.reason,
                                    "pitch": gap.pitch, "yaw": gap.yaw, "roll": gap.roll}})
    # A return is a pattern-level observation, not a person claim. It requires
    # two detected boundaries and a terminal role equal to the initial role.
    return_expected = pattern[0] == pattern[-1] and len(set(pattern)) > 1
    return_observed = return_expected and len(observed_changes) >= 2
    return {"expected_boundaries": expected_changes, "observed_boundaries": observed_changes,
            "boundary_recall": (sum(x in observed_changes for x in expected_changes) / len(expected_changes)
                                if expected_changes else 1.0),
            "false_boundaries": [x for x in observed_changes if x not in expected_changes],
            "return_expected": return_expected, "return_observed": return_observed, "pairs": pairs}


def render_html(result: dict[str, Any]) -> str:
    rows = []
    for run in result["runs"]:
        actual = run.get("evaluation", {})
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in (
            run["scenario"], run["pose_bin"], run["status"], run.get("reason", ""),
            actual.get("expected_boundaries", ""), actual.get("observed_boundaries", ""),
            actual.get("boundary_recall", ""), actual.get("return_observed", ""),
        )) + "</tr>")
    return """<!doctype html><meta charset='utf-8'><title>Scenario validation suite</title>
<style>body{font:14px system-ui;margin:32px;color:#17212b}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd5df;padding:7px;text-align:left}th{background:#edf2f7}.blocked{color:#a13b28}</style>
<h1>Pre-extracted chronology scenario suite</h1><p>This report validates controlled landmark fixtures, not identity claims. Synthetic dates establish order only.</p>
<table><thead><tr><th>Scenario</th><th>Pose</th><th>Status</th><th>Reason</th><th>Expected boundaries</th><th>Observed boundaries</th><th>Recall</th><th>Return observed</th></tr></thead><tbody>""" + "\n".join(rows) + "</tbody></table>"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "calibration_dataset")
    parser.add_argument("--output", type=Path, required=True, help="output JSON path")
    parser.add_argument("--scenarios", nargs="*", default=sorted(SCENARIOS), choices=sorted(SCENARIOS))
    parser.add_argument("--poses", nargs="*", default=list(POSE_BINS), choices=list(POSE_BINS))
    args = parser.parse_args()
    frames = load_frames(args.input)
    grouped: dict[tuple[str, str], list[Frame]] = defaultdict(list)
    for frame in frames:
        grouped[(frame.person, frame.pose_bin)].append(frame)
    for values in grouped.values():
        values.sort(key=lambda x: x.frame_id)
    threshold_by_pose = thresholds(frames)
    runs: list[dict[str, Any]] = []
    for scenario in args.scenarios:
        pattern = str(SCENARIOS[scenario]["pattern"])
        for pose_bin in args.poses:
            threshold = threshold_by_pose.get(pose_bin)
            selected, reason = choose_sequence(pattern, pose_bin, grouped)
            if threshold is None:
                reason = "insufficient_same_person_null" if not reason else reason
            if selected is None or threshold is None:
                runs.append({"scenario": scenario, "pose_bin": pose_bin, "status": "blocked", "reason": reason,
                             "expected": SCENARIOS[scenario]["expect"]})
                continue
            evaluation = evaluate(pattern, selected, threshold)
            runs.append({"scenario": scenario, "pose_bin": pose_bin, "status": "measured", "reason": "",
                         "expected": SCENARIOS[scenario]["expect"], "pattern": pattern,
                         "synthetic_dates": [(date(2000, 1, 1) + timedelta(days=i)).isoformat() for i in range(len(selected))],
                         "frames": [{"role": role, "person": frame.person, "frame_id": frame.frame_id,
                                     "angles": frame.angles.tolist(), "directory": str(frame.directory)}
                                    for role, frame in zip(pattern, selected)], "evaluation": evaluation})
    result = {"schema": "deeputin-preextracted-scenario-suite-v1.0", "scenario_registry": SCENARIO_SCHEMA,
              "input": str(args.input), "source_record_count": len(frames), "threshold_by_pose": threshold_by_pose,
              "runs": runs,
              "limitations": ["Synthetic dates establish order and are not capture dates.",
                              "This harness tests pre-extracted geometry only; it does not test image ingestion, texture/UV, or production provenance.",
                              "A transition candidate is a measurement state, not a conclusion about identity or cause."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".html").write_text(render_html(result), encoding="utf-8")
    measured = sum(x["status"] == "measured" for x in runs)
    print(json.dumps({"json": str(args.output), "html": str(args.output.with_suffix('.html')),
                      "runs": len(runs), "measured": measured, "blocked": len(runs) - measured}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
