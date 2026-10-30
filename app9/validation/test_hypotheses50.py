from __future__ import annotations

import ast

import numpy as np
import pandas as pd
import pytest

from app9.validation import hypotheses50 as study


def test_frozen_catalogue_has_fifty_unique_high_priority_definitions():
    catalogue, expressions = study.load_catalogue(study.ROOT / "app9/validation/hypotheses50_catalog.json")
    assert len(catalogue["hypotheses"]) == len(expressions) == 50
    assert min(row["priority"] for row in catalogue["hypotheses"]) == 90
    assert "NOT probability" in catalogue["score_meaning"]


@pytest.mark.parametrize("formula", ["__import__('os')", "a.__class__", "a[0]", "2 ** 100", "[x for x in a]", "sqrt(a, b)"])
def test_formula_interpreter_rejects_code_and_unapproved_operations(formula):
    with pytest.raises(ValueError):
        study.evaluate_formula(ast.parse(formula, mode="eval"), {"a": 4.0, "b": 2.0})


def test_formula_interpreter_arithmetic_and_invalid_geometry():
    values = {"a": 4.0, "b": 2.0}
    assert study.evaluate_formula(ast.parse("sqrt(a) + a / b - abs(-b)", mode="eval"), values) == 2
    assert np.isnan(study.evaluate_formula(ast.parse("a / 0", mode="eval"), values))
    assert np.isnan(study.evaluate_formula(ast.parse("log(-a)", mode="eval"), values))


def test_planar_noncollinear_loop_is_valid_not_rejected():
    plane = np.array([[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]], dtype=float)
    assert study.plane_warp(plane, 2) == pytest.approx(0, abs=1e-12)
    line = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], dtype=float)
    assert np.isnan(study.plane_warp(line, 2))


def test_plane_warp_translation_rotation_and_scale():
    points = np.array([[-1, -1, 0], [1, -1, 0.2], [1, 1, 0], [-1, 1, -0.1], [0, 0, 0.3]], dtype=float)
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    baseline = study.plane_warp(points, 2)
    assert study.plane_warp((points @ rotation) * 7 + [3, 4, 5], 14) == pytest.approx(baseline)


def eye_fixture():
    points = np.zeros((18, 2))
    x = np.linspace(0, 1, 9)
    arc = np.sqrt(np.maximum(4 * x * (1 - x), 0))
    points[:9] = np.column_stack((x, -0.15 * arc))
    points[9:] = np.column_stack((x, 0.12 * arc))
    return points


def test_local_eye_shapes_are_translation_rotation_reflection_and_scale_invariant():
    points = eye_fixture()
    upper, lower = tuple(range(9)), tuple(range(9, 18))
    baseline = study.eye_profile(points, upper, lower)
    theta = 0.73
    rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    transformed = points @ rotation * 8 + [15, -10]
    for modified in (transformed, points * [-1, 1]):
        measured = study.eye_profile(modified, upper, lower)
        for key in ("mean", "q20", "skew", "kurt", "iqr", "shape_exponent", "peak_offset", "concentration"):
            assert measured[key] == pytest.approx(baseline[key], abs=1e-10)


def test_affine_area_ratios_survive_shear_anisotropic_scale_and_reflection():
    points = np.zeros((478, 2))
    for index, value in {33: [-3, 0], 263: [3, 0.2], 133: [-1, 0.1], 362: [1, -0.1],
                         168: [0.2, -1], 1: [-0.1, 2], 2: [0.1, 3]}.items():
        points[index] = value
    baseline = study.affine_ratios(points)
    transformed = points @ np.array([[-2, 0.7], [0.3, 3]]) + [7, -4]
    for key, value in study.affine_ratios(transformed).items():
        assert value == pytest.approx(baseline[key])


def test_vectorized_weighted_auc_matches_explicit_tied_resamples():
    a = np.array([0, 1, 1, 3, np.nan], dtype=float)
    b = np.array([1, 2, 3, np.nan], dtype=float)
    wa = np.array([[1, 2, 1, 0, 1], [0, 0, 1, 3, 0]], dtype=float)
    wb = np.array([[2, 1, 1, 1], [0, 1, 3, 0]], dtype=float)
    observed = study.weighted_auc_samples(a, b, wa, wb)
    for index in range(len(wa)):
        explicit = study.audit.raw_auc(np.repeat(a, wa[index].astype(int)), np.repeat(b, wb[index].astype(int)))
        assert observed[index] == pytest.approx(explicit)


def test_bootstrap_weights_preserve_date_rows_within_month_clusters():
    frame = pd.DataFrame([{"group": group, "month": month} for group in study.audit.GROUPS
                          for month in ("2020-01", "2020-01", "2020-02")])
    weights = study.bootstrap_weights(frame, 100, np.random.default_rng(7))
    for group in study.audit.GROUPS:
        assert np.array_equal(weights[group][:, 0], weights[group][:, 1])


def test_permutation_weights_preserve_all_group_counts_but_not_one_shared_shuffle():
    labels = np.array(["put"] * 8 + ["udmurt"] * 4 + ["vas"] * 5)
    weights = study.permutation_weights(labels, 50, np.random.default_rng(10))
    for group in study.audit.GROUPS:
        assert np.all(weights[group].sum(axis=1) == np.count_nonzero(labels == group))
    assert not np.array_equal(weights["put"][0], weights["put"][1])
    assert np.all(sum(weights.values()) == 1)


def test_paired_identical_feature_has_exactly_zero_increment_uncertainty():
    samples = np.array([[0.7, 0.8, 0.9], [0.8, 0.9, 0.7]] * 100)
    intervals = study.confidence_intervals(samples, samples.copy(), 50)
    assert intervals["delta_ci95"] == [0, 0]
    assert intervals["delta_ci_familywise_nominal95"] == [0, 0]


def test_diagnostic_uses_the_actual_multiplicity_family_label():
    row = {"cohorts": {key: {"worst_auc": 0.8} for key in ("test", "neutral", "strict", "pose_adjusted_test")},
           "bootstrap": {"auc_ci95": [0.6, 0.9], "delta_ci_familywise_nominal95": [0.04, 0.1]},
           "association": {"p_bonferroni50": 0.1}, "nearest_existing": {"rank_equivalent": False, "near_duplicate": False},
           "delta_test_auc": 0.05}
    row["cohorts"]["test"]["ref"] = {group: {"n_months": 8} for group in study.audit.GROUPS}
    outcome = study.hypothesis_status(row, family_size=68)
    assert any("Bonferroni68" in failure for failure in outcome["failures"])
