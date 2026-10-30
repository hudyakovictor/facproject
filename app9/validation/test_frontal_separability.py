from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app9.validation import frontal_separability as audit


def test_auc_ties_and_missing_values():
    a = np.array([1, 1, 2, np.nan])
    b = np.array([1, 2, 2])
    assert audit.raw_auc(a, b) == pytest.approx(1 / 3)
    assert audit.raw_auc(a, a) == pytest.approx(0.5)
    assert np.isnan(audit.raw_auc(np.array([1, 2]), b))


def test_balanced_noise_does_not_weight_larger_groups_more():
    groups = {group: np.array([-scale, 0, scale]) for group, scale in zip(audit.GROUPS, (1, 2, 3), strict=True)}
    baseline = audit.balanced_mad(groups)
    groups["put"] = np.tile(groups["put"], 100)
    assert audit.balanced_mad(groups) == baseline
    assert baseline == pytest.approx(1.4826 * 2)


def test_unknown_expression_is_not_neutral():
    assert audit.neutral_flags({}) == (False, False)
    scores = dict.fromkeys(audit.ms.EXPR_MAX, 0.0)
    assert audit.neutral_flags(scores) == (True, True)
    scores["jawOpen"] = np.nan
    assert audit.neutral_flags(scores) == (False, False)
    scores["jawOpen"] = 0.5
    assert audit.neutral_flags(scores) == (True, False)


def test_front_selection_and_strict_pose_are_explicit():
    frame = pd.DataFrame({"status": ["ok"] * 6 + ["bad"], "pose_bin": ["frontal"] * 7,
                          "yaw_deg": [0, 6, 11, 0, 0, np.nan, 0],
                          "pitch_deg": [10, 10, 10, 21, 10, 10, 10],
                          "roll_deg": [0, 0, 0, 0, 6, 0, 0]})
    assert audit.frontal_mask(frame).tolist() == [True, True, False, True, True, False, False]
    assert audit.frontal_mask(frame, strict=True).tolist() == [True, False, False, False, False, False, False]


def test_chronology_keeps_repeated_months_in_one_partition():
    rows = [{"group": group, "month": month} for group in audit.GROUPS
            for month in ("2020-01", "2020-01", "2020-02", "2020-03", "2020-04")]
    frame = pd.DataFrame(rows)
    frame["train"] = audit.chronological_split(frame, 0.5)
    for _, group in frame.groupby("group"):
        assert set(group.loc[group.train, "month"]) == {"2020-01", "2020-02"}
        assert set(group.loc[group.train, "month"]).isdisjoint(group.loc[~group.train, "month"])
    with pytest.raises(ValueError):
        audit.chronological_split(frame, 1)


def test_training_orientation_is_not_refitted_on_reversed_test():
    train = pd.DataFrame([{"group": group, "feature": offset + i, "month": "2020-01"}
                          for group, offset in zip(audit.GROUPS, (0, 10, 20), strict=True) for i in range(3)])
    signs = audit.training_signs(train, "feature")
    assert audit.summarize(train, "feature", signs)["worst_auc"] == 1
    test = train.copy()
    test["feature"] *= -1
    assert audit.summarize(test, "feature", signs)["worst_auc"] == 0


def test_shared_pose_fit_preserves_group_offsets_and_does_not_use_test_values():
    rows = []
    for group, offset in zip(audit.GROUPS, (0, 10, 20), strict=True):
        for yaw in range(8):
            rows.append({"group": group, "yaw_deg": float(yaw), "pitch_deg": 0.0, "roll_deg": 0.0,
                         "feature": offset + 2 * yaw})
    train = pd.DataFrame(rows)
    target = train.copy()
    adjusted, slopes = audit.pose_adjustment(train, target, "feature")
    assert slopes == pytest.approx([2, 0, 0])
    assert np.allclose(adjusted.groupby("group").feature.std(), 0)
    means = adjusted.groupby("group").feature.mean()
    assert means["udmurt"] - means["put"] == pytest.approx(10)
    target["feature"] += 1000
    _, new_slopes = audit.pose_adjustment(train, target, "feature")
    assert new_slopes == slopes


def test_bootstrap_resamples_whole_months():
    frame = pd.DataFrame([{"group": group, "month": month} for group in audit.GROUPS
                          for month in ("2020-01", "2020-01", "2020-02")])
    draws = audit.month_bootstrap_indices(frame, 100, np.random.default_rng(7))
    for group in audit.GROUPS:
        for draw in draws[group]:
            assert np.count_nonzero(draw == 0) == np.count_nonzero(draw == 1)


def test_absent_third_group_does_not_receive_a_worst_pair_score():
    frame = pd.DataFrame([{"group": group, "feature": float(i), "month": "2020-01"}
                          for group in ("put", "vas") for i in range(3)])
    summary = audit.summarize(frame, "feature", dict.fromkeys((f"{a}~{b}" for a, b in audit.PAIRS), 1))
    assert np.isnan(summary["worst_auc"])


def test_shortlist_uses_only_training_scores_and_training_correlations():
    train = pd.DataFrame({"a": range(10), "b": [4, 1, 7, 0, 8, 3, 6, 9, 2, 5]})
    metrics = {name: {"training_score": score, "meta": {"framework": "3ddfa"}, "test_auc": test}
               for name, score, test in (("a", 0.8, 0.1), ("b", 0.7, 1.0))}
    assert audit.training_shortlist(metrics, train, 1) == ["a"]
    metrics["a"]["test_auc"] = 1.0
    metrics["b"]["test_auc"] = 0.1
    assert audit.training_shortlist(metrics, train, 1) == ["a"]


def test_followup_diagnostics_rejects_reversal_and_missing_uncertainty():
    row = {"cohorts": {key: {"worst_auc": 0.8} for key in ("test", "neutral", "strict", "pose_adjusted_test")},
           "meta": {"framework": "mediapipe", "expression_sensitive": True, "uses_z": False},
           "test_bootstrap": {"worst_auc_ci95": [0.6, 0.9]}}
    row["cohorts"]["test"]["ref"] = {group: {"n_months": 8} for group in audit.GROUPS}
    status = audit.followup_diagnostics(row)
    assert status["passes_exploratory_checks"]
    assert "expression-sensitive" in status["risks"][0]
    row["cohorts"]["test"]["worst_auc"] = 0.4
    row["test_bootstrap"]["worst_auc_ci95"] = []
    assert not audit.followup_diagnostics(row)["passes_exploratory_checks"]


def test_nan_candidate_is_not_ranked_ahead_of_finite_training_score():
    train = pd.DataFrame({"missing": [np.nan] * 10, "valid": range(10)})
    metrics = {"missing": {"training_score": np.nan, "meta": {"framework": "3ddfa"}},
               "valid": {"training_score": 0.8, "meta": {"framework": "3ddfa"}}}
    assert audit.training_shortlist(metrics, train, 1) == ["valid"]
