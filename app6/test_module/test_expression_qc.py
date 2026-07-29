"""ТЗ п.2: динамическое исключение мимических зон."""
from __future__ import annotations

import numpy as np
import pytest

from app6.stage2.expression_qc import (
    BONE_ZONES,
    MIMIC_ZONES,
    detect_expression,
    exclude_mimic_zones,
    expression_magnitude,
)


@pytest.fixture()
def neutral_landmarks(calibration_records):
    return [r for r in calibration_records if r.pose_bin == "frontal"][0].ldm106


@pytest.fixture()
def zone_weights():
    return {zone: 1.0 for zone in (MIMIC_ZONES | BONE_ZONES)}


def test_magnitude_is_scale_invariant(neutral_landmarks) -> None:
    """Метрики нормированы на межзрачковое расстояние.

    Ландмарки хранятся во float32, поэтому масштабирование вносит ошибку
    порядка 1e-7 — допуск задан с запасом относительно неё, но на семь
    порядков строже самих порогов детекции.
    """
    base = expression_magnitude(neutral_landmarks)
    scaled = expression_magnitude(np.asarray(neutral_landmarks) * 3.7)
    assert base["smile"] == pytest.approx(scaled["smile"], rel=1e-6)
    assert base["jaw_open"] == pytest.approx(scaled["jaw_open"], rel=1e-6)


def test_open_mouth_is_detected(neutral_landmarks) -> None:
    points = np.asarray(neutral_landmarks, dtype=np.float64).copy()
    points[93] += (points[93] - points[87]) * 3.0
    assert detect_expression(points)["jaw_open_detected"] is True


def test_mimic_zones_zeroed_when_expression_active(neutral_landmarks, zone_weights) -> None:
    points = np.asarray(neutral_landmarks, dtype=np.float64).copy()
    points[93] += (points[93] - points[87]) * 3.0
    result = exclude_mimic_zones(points, zone_weights)
    assert result["expression"]["expression_active"] is True
    for zone in MIMIC_ZONES:
        assert result["zone_weights"][zone] == 0.0


def test_bone_zones_never_touched(neutral_landmarks, zone_weights) -> None:
    """Костные структуры не зависят от выражения — вес обязан сохраниться."""
    points = np.asarray(neutral_landmarks, dtype=np.float64).copy()
    points[93] += (points[93] - points[87]) * 5.0
    result = exclude_mimic_zones(points, zone_weights)
    for zone in BONE_ZONES:
        assert result["zone_weights"][zone] == 1.0


def test_weights_unchanged_below_threshold(zone_weights) -> None:
    """Синтетически нейтральное лицо: рот узкий и закрытый."""
    points = np.zeros((106, 3), dtype=np.float64)
    points[74] = [-1.0, 0.0, 0.0]
    points[77] = [1.0, 0.0, 0.0]
    points[84] = [-0.2, -1.0, 0.0]
    points[90] = [0.2, -1.0, 0.0]
    points[87] = [0.0, -1.0, 0.0]
    points[93] = [0.0, -1.05, 0.0]
    result = exclude_mimic_zones(points, zone_weights)
    assert result["expression"]["expression_active"] is False
    assert result["zone_weights"] == zone_weights
    assert result["excluded_zones"] == []


def test_degenerate_scale_fails_closed() -> None:
    points = np.zeros((106, 3), dtype=np.float64)
    with pytest.raises(ValueError):
        expression_magnitude(points)


def test_negative_weights_rejected(neutral_landmarks) -> None:
    with pytest.raises(ValueError):
        exclude_mimic_zones(neutral_landmarks, {"orbit_L": -1.0})
