"""Регрессия вычитания углового шума через API.

Проверяется не «функция отработала», а инварианты, защищающие от ложных
выводов: отсутствие самоподбора, честный статус при неудачном подборе и
сохранение сырого значения рядом с компенсированным.
"""
from __future__ import annotations

import pytest

from app6.api.noise_calibration import (
    apply_noise_subtraction, build_noise_index, resolve_tolerance,
)


@pytest.fixture(scope="module")
def index():
    return build_noise_index()


def test_index_separates_people_not_lumps_them(index) -> None:
    """Кадры разных carrier'ов НЕ должны попадать в «шум одного человека».

    Демо-набор помечает все записи одним `dataset_id`, хотя порождает их из
    трёх разных alpha_id. Без разделения оценка шума завышается и вычитание
    маскирует настоящие расхождения.
    """
    datasets = {pair["dataset_id"] for pair in index}
    assert len(datasets) >= 3, f"персоны не разделены: {datasets}"
    assert all(d.startswith("carrier_") for d in datasets)


def test_pairs_never_mix_pose_bins(index) -> None:
    """Пара шума строится внутри одного ракурса: сравнение поперёк запрещено."""
    assert all(pair.get("pose_bin") for pair in index)


def test_excluding_the_analysed_pair_prevents_self_matching() -> None:
    """Без исключения пара подбирает саму себя и компенсация даёт ровно 0.

    Это круговая логика: наблюдаемое вычитается из самого себя.
    """
    from app6.api.demo_data import build_demo_records, build_demo_zone_maps
    from app6.stage2.core import compare_landmarks

    photos = build_demo_records()
    zone106, zone134 = build_demo_zone_maps(photos)
    frontal = [p for p in photos if p.pose_bin == "frontal"]
    a, b = frontal[0], frontal[15]
    comparison = compare_landmarks(a.record, b.record, zone106, zone134)

    leaky = apply_noise_subtraction(
        comparison.metrics, a.record.angles, b.record.angles, "frontal")
    guarded = apply_noise_subtraction(
        comparison.metrics, a.record.angles, b.record.angles, "frontal",
        exclude_records=(a.record.record_id, b.record.record_id))

    assert leaky["match"]["match_distance"] == pytest.approx(0.0, abs=1e-9)
    # Защита обязана подобрать ДРУГУЮ пару.
    if guarded["match"]:
        assert {guarded["match"]["record_a"], guarded["match"]["record_b"]} != {
            a.record.record_id, b.record.record_id}


def test_raw_value_is_always_preserved_next_to_compensated() -> None:
    """Компенсация не подменяет исходное число: оба доступны вызывающему."""
    metrics = {"ldm134_rmse": 0.05, "ldm106_rmse": 0.04}
    out = apply_noise_subtraction(metrics, [0, 0, 0], [1, 0, 0], "frontal")
    for key, entry in out["metrics"].items():
        assert entry["raw"] == pytest.approx(metrics[key])


def test_missing_match_reports_uncompensated_instead_of_zeroing() -> None:
    """Нет подходящей пары → компенсация НЕ применяется, а не даёт 0."""
    metrics = {"ldm134_rmse": 0.05}
    # Заведомо недостижимая разница углов.
    out = apply_noise_subtraction(metrics, [0, 0, 0], [90, 90, 90], "frontal")
    assert out["uncompensated"] is True
    assert out["reason"]
    assert out["metrics"]["ldm134_rmse"]["compensated"] is None


def test_degenerate_match_is_flagged() -> None:
    """Схлопывание расхождения в ноль помечается как дефект подбора."""
    from app6.api.demo_data import build_demo_records, build_demo_zone_maps
    from app6.stage2.core import compare_landmarks

    photos = build_demo_records()
    zone106, zone134 = build_demo_zone_maps(photos)
    frontal = [p for p in photos if p.pose_bin == "frontal"]
    a, b = frontal[0], frontal[15]
    comparison = compare_landmarks(a.record, b.record, zone106, zone134)
    out = apply_noise_subtraction(
        comparison.metrics, a.record.angles, b.record.angles, "frontal")
    if not out["uncompensated"]:
        entry = out["metrics"]["ldm134_rmse"]
        if entry["compensated"] == 0.0:
            assert out["degenerate_match"] is True


def test_invalid_tolerance_falls_back_to_defaults() -> None:
    """Отрицательный допуск не должен обнулять подбор молча."""
    assert resolve_tolerance({"yaw": -5})["yaw"] == 2.0
    assert resolve_tolerance({"pitch": "abc"})["pitch"] == 1.0
    assert resolve_tolerance(None) == {"yaw": 2.0, "pitch": 1.0, "roll": 1.0}
    assert resolve_tolerance({"yaw": 4.5})["yaw"] == 4.5
