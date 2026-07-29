"""Регрессия D4/D5: нормативная политика ракурсов должна читаться и быть однозначной."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app6.stage2.pose_policy import (
    BIN_NAME_TO_YAW,
    applicable_zones,
    load_pose_policy,
    policy_summary,
    yaw_for_bin,
    zone_applicability,
)

ATLAS_DIR = Path(__file__).resolve().parents[1] / "atlas"


def test_normative_policy_is_loadable() -> None:
    """AGENTS.md объявляет файл нормативным, но код его не читал (D4)."""
    table = load_pose_policy()
    assert len(table) == 180, "ожидается 20 зон × 9 бинов"


def test_all_nine_bins_are_covered() -> None:
    assert len(BIN_NAME_TO_YAW) == 9
    for name in BIN_NAME_TO_YAW:
        assert isinstance(yaw_for_bin(name), float)


def test_yaw_sign_convention_is_pinned() -> None:
    """D5: между v1 и v3 конвенция знака инвертирована в 96 из 180 ячеек.

    Тест фиксирует конвенцию v3: A01 (лоб слева) виден при повороте влево
    и исключается в правом профиле. Если атлас подменят, тест упадёт.
    """
    assert yaw_for_bin("left_profile") < 0 < yaw_for_bin("right_profile")
    assert zone_applicability("A01", "left_profile")["status"] == "primary"
    assert zone_applicability("A01", "right_profile")["status"] == "exclude"
    assert zone_applicability("A01", "right_profile")["applicable"] is False


def test_excluded_zone_is_not_silently_zero_weighted() -> None:
    rule = zone_applicability("A01", "right_profile")
    assert rule["weight"] == 0.0
    assert rule["applicable"] is False, "exclude обязан отличаться от нулевого веса"


def test_profiles_have_fewer_usable_zones_than_frontal() -> None:
    """Половина лица в профиле не видна — это должно отражаться в политике."""
    assert len(applicable_zones("frontal")) > len(applicable_zones("left_profile"))
    assert len(applicable_zones("frontal")) > len(applicable_zones("right_profile"))


def test_unknown_bin_fails_closed() -> None:
    with pytest.raises(ValueError):
        yaw_for_bin("frontal_yaw15")


def test_legacy_atlas_differs_and_must_not_be_mixed() -> None:
    """Явно фиксируем факт расхождения версий, чтобы подмена была заметна."""
    def read(name: str) -> dict[tuple[str, str], str]:
        with (ATLAS_DIR / name).open(newline="", encoding="utf-8-sig") as handle:
            return {(r["zone_code"], r["yaw_bin_center_deg"]): r["status"]
                    for r in csv.DictReader(handle)}

    legacy = read("pose_policy_9bins.csv")
    current = read("pose_policy_v3_9bins.csv")
    differences = sum(1 for key, value in legacy.items() if current.get(key) != value)
    assert differences == 96, f"ожидалось 96 расхождений v1/v3, найдено {differences}"


def test_summary_records_convention_for_provenance() -> None:
    summary = policy_summary()
    assert summary["zone_count"] == 20
    assert summary["yaw_bin_count"] == 9
    assert "negative yaw" in summary["yaw_convention"]
