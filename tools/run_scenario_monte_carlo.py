#!/usr/bin/env python3
"""Run 100 deterministic perturbation simulations over chronology fixtures.

The harness seeks failure modes (false steps, missed returns, pose/visibility
leakage), not a claim about identity.  Every simulation records its seed and
injection so it can be reproduced exactly.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app6.archive_adapter import POSE_BINS
from app6.scenarios import SCENARIOS
from tools.run_preextracted_scenario_suite import (
    Frame, choose_sequence, evaluate, load_frames, thresholds,
)


def perturb(frames: list[Frame], mode: str, rng: np.random.Generator) -> list[Frame]:
    """Return a non-mutating pathological fixture with known expected guard."""
    out = list(frames)
    target = len(out) // 2
    frame = out[target]
    if mode == "none":
        return out
    if mode == "coordinate_noise_low":
        return [replace(x, points=x.points + rng.normal(0.0, 0.001, x.points.shape).astype(np.float32)) for x in out]
    if mode == "coordinate_noise_high":
        return [replace(x, points=x.points + rng.normal(0.0, 0.004, x.points.shape).astype(np.float32)) for x in out]
    if mode == "visibility_dropout_15":
        mask = frame.visible.copy(); mask[rng.choice(134, size=20, replace=False)] = False
        out[target] = replace(frame, visible=mask)
        return out
    if mode == "visibility_dropout_85":
        mask = frame.visible.copy(); mask[rng.choice(134, size=114, replace=False)] = False
        out[target] = replace(frame, visible=mask)
        return out
    if mode == "pose_shock":
        angles = frame.angles.copy(); angles[0] += 10.0
        out[target] = replace(frame, angles=angles)
        return out
    if mode == "duplicate":
        # Exact reuse must remain quiet; a duplicate is never independent
        # corroboration, but it must not fabricate a geometric step.
        out[target] = out[target - 1]
        return out
    raise ValueError(mode)


def expected_guard(mode: str) -> str:
    return {
        "visibility_dropout_85": "insufficient_visibility",
        "pose_shock": "pose_gate_reject",
        "duplicate": "no_geometric_transition_at_duplicate",
    }.get(mode, "metric_stability")


def verify(mode: str, result: dict[str, Any], target: int) -> tuple[bool, str]:
    pairs = result["pairs"]
    affected = [p for p in pairs if p["boundary_after_step"] in {target, target + 1}]
    if mode == "pose_shock":
        return any(not p["pose_gate"]["accepted"] for p in affected), "pose_gate_not_rejecting" 
    if mode == "visibility_dropout_85":
        return any(p["rmse"] is None for p in affected), "visibility_not_fail_closed"
    if mode == "duplicate":
        duplicate_boundary = next((p for p in affected if p["boundary_after_step"] == target), None)
        return bool(duplicate_boundary and not duplicate_boundary["transition"]), "duplicate_created_transition"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "calibration_dataset")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260803)
    args = parser.parse_args()
    if args.runs < 100:
        raise ValueError("minimum is 100 simulations")
    frames = load_frames(args.input)
    grouped: dict[tuple[str, str], list[Frame]] = {}
    for frame in frames:
        grouped.setdefault((frame.person, frame.pose_bin), []).append(frame)
    for values in grouped.values():
        values.sort(key=lambda x: x.frame_id)
    cutoffs = thresholds(frames)
    rng = np.random.default_rng(args.seed)
    modes = ("none", "coordinate_noise_low", "coordinate_noise_high", "visibility_dropout_15",
             "visibility_dropout_85", "pose_shock", "duplicate")
    scenarios = sorted(SCENARIOS)
    results: list[dict[str, Any]] = []
    for index in range(args.runs):
        scenario = scenarios[index % len(scenarios)]
        pose = POSE_BINS[(index // len(scenarios)) % len(POSE_BINS)]
        mode = modes[index % len(modes)]
        selected, reason = choose_sequence(str(SCENARIOS[scenario]["pattern"]), pose, grouped)
        if selected is None or pose not in cutoffs:
            results.append({"run": index + 1, "scenario": scenario, "pose_bin": pose, "mode": mode,
                            "status": "blocked", "reason": reason or "insufficient_same_person_null"})
            continue
        changed = perturb(selected, mode, rng)
        evaluation = evaluate(str(SCENARIOS[scenario]["pattern"]), changed, cutoffs[pose])
        ok, failure = verify(mode, evaluation, len(changed) // 2)
        # For NULL fixtures, all detected boundaries are a false-positive.
        if scenario == "S01" and evaluation["observed_boundaries"]:
            ok, failure = False, "null_false_transition"
        # AABBAA must retain its two specified boundaries absent a deliberate
        # guard injection; its omission is useful robustness evidence.
        if scenario == "S03" and mode in {"none", "coordinate_noise_low", "visibility_dropout_15"} and evaluation["boundary_recall"] < 1:
            ok, failure = False, "return_boundary_missed"
        results.append({"run": index + 1, "scenario": scenario, "pose_bin": pose, "mode": mode,
                        "status": "pass" if ok else "failure", "failure": failure,
                        "expected_guard": expected_guard(mode), "evaluation": evaluation})
    executed = [r for r in results if r["status"] != "blocked"]
    failures = [r for r in executed if r["status"] == "failure"]
    by_failure: dict[str, int] = {}
    for row in failures:
        by_failure[row["failure"]] = by_failure.get(row["failure"], 0) + 1
    improvements = []
    if any(r["status"] == "blocked" for r in results):
        improvements.append("Добрать pose-matched neutral frames, прежде всего profile/deep bins; blocked fixture не должен обходиться ослаблением gate.")
    if by_failure.get("null_false_transition"):
        improvements.append("Усилить NULL-control: раздельные thresholds по quality/visibility strata и persistent-event minimum length.")
    if by_failure.get("return_boundary_missed"):
        improvements.append("Для return добавить matched-null coverage и anchor comparison; не снижать порог глобально.")
    if by_failure.get("visibility_not_fail_closed"):
        improvements.append("Проверить common-visibility gate: отсутствие точек не может порождать distance/score.")
    if by_failure.get("pose_gate_not_rejecting"):
        improvements.append("Проверить передачу pose_bin и axis-specific limits во все entry points.")
    if by_failure.get("duplicate_created_transition"):
        improvements.append("Подключить perceptual duplicate gate до chronology и исключить duplicate из corroboration count.")
    if not improvements:
        improvements.append("В данной области perturbations guard-поведение устойчиво; следующий прирост покрытия требует image/texture/provenance fixtures, отсутствующих в landmark-only corpus.")
    output = {"schema": "deeputin-scenario-monte-carlo-v1.0", "runs_requested": args.runs,
              "seed": args.seed, "source_record_count": len(frames), "runs": results,
              "summary": {"executed": len(executed), "blocked": args.runs - len(executed),
                          "passed": len(executed) - len(failures), "failures": len(failures),
                          "failure_types": by_failure, "improvements": improvements},
              "limitations": ["Fixtures use pre-extracted landmarks and synthetic chronology dates.",
                              "This is not an assessment of real identity, source authenticity, texture, or a biological timeline."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **output["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
