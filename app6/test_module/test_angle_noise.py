"""ТЗ п.1: вычитание углового шума калибровки."""
from __future__ import annotations

import numpy as np
import pytest

from app6.stage2.angle_noise import (
    DEFAULT_TOLERANCE,
    angle_delta,
    build_calibration_pair_index,
    find_matching_calibration_pair,
    subtract_angle_noise,
)


def test_angle_delta_is_absolute_and_ordered() -> None:
    delta = angle_delta([1.0, -70.0, 3.0], [2.0, -60.0, 1.0])
    assert delta == {"pitch": 1.0, "yaw": 10.0, "roll": 2.0}


def test_angle_delta_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        angle_delta([1.0, 2.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        angle_delta([1.0, float("nan"), 3.0], [1.0, 2.0, 3.0])


def test_zero_delta_pair_is_matched() -> None:
    """Граничный случай ТЗ: Δyaw = 0, Δpitch = 0."""
    pairs = [{"pose_bin": "frontal", "delta": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
              "metrics": {"ldm134_rmse": 0.004}, "dataset_id": "person_01",
              "record_a": "a", "record_b": "b"}]
    match = find_matching_calibration_pair({"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
                                           pairs, pose_bin="frontal")
    assert match is not None
    assert match["match_distance"] == 0.0


def test_compensation_reduces_observed_divergence() -> None:
    pairs = [{"pose_bin": "frontal", "delta": {"yaw": 1.0, "pitch": 0.2, "roll": 0.1},
              "metrics": {"ldm134_rmse": 0.003}, "dataset_id": "person_01",
              "record_a": "a", "record_b": "b"}]
    metrics = {"angles_a": [0.0, 0.0, 0.0], "angles_b": [0.2, 1.0, 0.1],
               "pose_bin": "frontal", "ldm134_rmse": 0.010}
    out = subtract_angle_noise(metrics, pairs)
    assert out["angle_noise_uncompensated"] is False
    assert out["ldm134_rmse_angle_compensated"] == pytest.approx(0.007)
    assert out["ldm134_rmse_angle_compensated"] < out["ldm134_rmse"]


def test_flag_set_when_no_pair_within_tolerance() -> None:
    """Допуски ТЗ: ±2° yaw, ±1° pitch/roll."""
    pairs = [{"pose_bin": "frontal", "delta": {"yaw": 30.0, "pitch": 0.0, "roll": 0.0},
              "metrics": {"ldm134_rmse": 0.003}, "dataset_id": "person_01",
              "record_a": "a", "record_b": "b"}]
    metrics = {"angles_a": [0.0, 0.0, 0.0], "angles_b": [0.0, 1.0, 0.0],
               "pose_bin": "frontal", "ldm134_rmse": 0.010}
    out = subtract_angle_noise(metrics, pairs)
    assert out["angle_noise_uncompensated"] is True
    assert "ldm134_rmse_angle_compensated" not in out


def test_compensated_value_never_negative() -> None:
    pairs = [{"pose_bin": "frontal", "delta": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
              "metrics": {"ldm134_rmse": 0.050}, "dataset_id": "person_01",
              "record_a": "a", "record_b": "b"}]
    out = subtract_angle_noise({"angles_a": [0, 0, 0], "angles_b": [0, 0, 0],
                                "pose_bin": "frontal", "ldm134_rmse": 0.004}, pairs)
    assert out["ldm134_rmse_angle_compensated"] == 0.0


def test_missing_angles_fail_closed() -> None:
    with pytest.raises(KeyError):
        subtract_angle_noise({"ldm134_rmse": 0.01}, [])


def test_index_built_from_real_calibration(calibration_records, zone_maps) -> None:
    from app6.stage2.core import compare_landmarks

    zone106, zone134 = zone_maps
    subset = [r for r in calibration_records if r.pose_bin == "frontal"][:60]
    index = build_calibration_pair_index(subset, compare_landmarks, zone106, zone134,
                                         max_pairs_per_group=10)
    assert index, "индекс калибровочных пар пуст"
    assert all("delta" in pair and "metrics" in pair for pair in index)
    assert all(pair["pose_bin"] == "frontal" for pair in index)
