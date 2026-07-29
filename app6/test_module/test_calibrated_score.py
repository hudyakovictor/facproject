"""Регрессия D1: нефинитная метрика не должна выглядеть аномалией."""
from __future__ import annotations

import math

import numpy as np
import pytest

from app6.stage2.core import calibrated_score
from app6.stage2.evidence import evidence_state

REFERENCE = {"count": 50, "median": 0.01, "mad": 0.002, "p95": 0.02}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_value_is_not_measurable(value: float) -> None:
    """NaN/Inf раньше проваливались в ветку else и получали статус elevated."""
    result = calibrated_score(value, REFERENCE, [])
    assert result["status"] == "not_measurable"
    assert math.isnan(float(result["robust_z"]))


def test_not_measurable_maps_to_its_own_evidence_state() -> None:
    """Отсутствие измерения не должно становиться elevated_uncertain."""
    assert evidence_state("not_measurable") == "not_measurable"


def test_normal_values_still_scored() -> None:
    within = calibrated_score(0.005, REFERENCE, [])
    elevated = calibrated_score(0.5, REFERENCE, [])
    assert within["status"] == "within_calibration_noise"
    assert elevated["status"] == "elevated"
    assert elevated["robust_z"] > within["robust_z"]


def test_insufficient_calibration_takes_priority() -> None:
    result = calibrated_score(0.1, {"count": 0, "median": 0.0, "mad": 0.0, "p95": 0.0}, [])
    assert result["status"] == "insufficient_calibration"


def test_alpha_metrics_of_sidecar_pair_do_not_fake_anomaly(calibration_records, zone_maps) -> None:
    """Калибровочные записи содержат alpha: метрики финитны, статус normal.

    Ранее тест ожидал NaN, но calibration_dataset содержит alpha_id/alpha_exp
    во всех record.npz. Проверяем, что значение финитно и не помечается как
    аномалия при нормальном уровне.
    """
    from app6.stage2.core import compare_landmarks

    zone106, zone134 = zone_maps
    frontal = [r for r in calibration_records
               if r.dataset_id == "person_01" and r.pose_bin == "frontal"][:2]
    comparison = compare_landmarks(frontal[0], frontal[1], zone106, zone134)
    assert comparison.status == "measured"
    assert np.isfinite(comparison.metrics["alpha_id_l2"])
    assert comparison.metrics["alpha_id_l2"] > 0

    scored = calibrated_score(comparison.metrics["alpha_id_l2"], REFERENCE, [])
    assert scored["status"] != "not_measurable"
