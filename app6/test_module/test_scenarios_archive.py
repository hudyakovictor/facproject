"""Сценарные тесты на реальном архиве: проверяют поведение системы, а не функции.

Каждый тест отвечает на один вопрос из `docs/future_testing_module.txt`:
может ли система отличить шум от смены личности, устойчива ли она по ракурсам,
не порождает ли ложных аномалий на стабильной серии.

Архив содержит только ландмарки (188 записей, 7 персон × 9 ракурсов), поэтому
проверяется геометрический контур; текстурные каналы здесь неприменимы.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from app6.stage2.core import build_coordinate_zone_map, compare_landmarks
from app6.stage2.irreversible_return import detect_irreversible_return
from app6.test_module.archive_adapter import (
    safe_extract_archive,
    POSE_BINS,
    archive_summary,
    group_by_person_pose,
    load_archive_records,
    with_synthetic_dates,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
#: Архив ландмарок 7×9×3. Не хранится в git (`.gitignore: *.tar.gz`) — это
#: внешний вход исследования, а не артефакт репозитория. Путь переопределяется
#: переменной окружения DEEPUTIN_SCENARIO_ARCHIVE.
ARCHIVE_TARBALL = Path(
    os.environ.get("DEEPUTIN_SCENARIO_ARCHIVE")
    or PROJECT_ROOT / "selected_photos_7x9x3_data.tar.gz"
)

#: DEV_FIX_TZ B1 / P1.10: причина пропуска должна быть выполнимой инструкцией,
#: а не констатацией «недоступен». Синтезировать архив из
#: `calibration_dataset/person_*/frame_*/` НЕЛЬЗЯ: `app6/AGENTS.md` прямо
#: помечает этот набор как устаревший pre-extracted с невыровненными
#: landmarks, и подмена им реальных данных превратила бы 27 сценарных тестов
#: в самообман (зелёный результат на данных, которые сам проект признал
#: непригодными).
_SKIP_REASON = (
    f"сценарный архив ландмарок не найден: {ARCHIVE_TARBALL}\n"
    "Это внешний вход исследования, он намеренно не хранится в git "
    "(.gitignore: *.tar.gz). Чтобы включить эти 27 тестов:\n"
    "  1) положите selected_photos_7x9x3_data.tar.gz в корень репозитория, ИЛИ\n"
    "  2) укажите путь: DEEPUTIN_SCENARIO_ARCHIVE=/path/to/archive.tar.gz pytest ...\n"
    "Ожидаемое содержимое: 188 записей (7 персон × 9 ракурсов × ~3 кадра) в "
    "раскладке person_XX__frame_YYYYYY/ с metadata.json (см. archive_adapter). "
    "Заменять его calibration_dataset/person_*/frame_*/ нельзя: AGENTS.md "
    "помечает тот набор как устаревший с невыровненными landmarks."
)


@pytest.fixture(scope="module")
def archive_records(tmp_path_factory):
    if not ARCHIVE_TARBALL.is_file():
        pytest.skip(_SKIP_REASON)
    extract_dir = tmp_path_factory.mktemp("archive")
    safe_extract_archive(ARCHIVE_TARBALL, extract_dir)
    return load_archive_records(extract_dir)


@pytest.fixture(scope="module")
def archive_zones(archive_records):
    zone106, _ = build_coordinate_zone_map(archive_records, 106)
    zone134, _ = build_coordinate_zone_map(archive_records, 134)
    return zone106, zone134


def test_archive_covers_seven_people_and_nine_poses(archive_records) -> None:
    summary = archive_summary(archive_records)
    assert summary["record_count"] == 188
    assert summary["person_count"] == 7
    assert summary["covers_nine_bins"] is True
    assert set(summary["pose_bins"]) == set(POSE_BINS)


def test_same_person_divergence_below_cross_person(archive_records, archive_zones) -> None:
    """Ключевой вопрос: отличает ли система шум от смены личности.

    Архив собран как худший случай: кадры каждой персоны выбраны с максимальным
    разбросом позы внутри бина (Δyaw ≈ 9.5° при ширине бина 20°). Поэтому
    хвосты распределений соприкасаются, и корректный критерий — разделимость
    распределений (AUC), а не отсутствие пересечения крайних значений.
    На чистой калибровке с малым Δyaw AUC достигает 1.000.
    """
    zone106, zone134 = archive_zones
    grouped = group_by_person_pose(archive_records)
    people = sorted({p for p, _ in grouped})
    same, cross = [], []

    for (person, pose), group in grouped.items():
        if pose != "frontal":
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                result = compare_landmarks(group[i], group[j], zone106, zone134)
                if result.status == "measured":
                    same.append(result.metrics["ldm134_rmse"])

    for i in range(len(people)):
        for j in range(i + 1, len(people)):
            for first in grouped.get((people[i], "frontal"), []):
                for second in grouped.get((people[j], "frontal"), []):
                    result = compare_landmarks(first, second, zone106, zone134)
                    if result.status == "measured":
                        cross.append(result.metrics["ldm134_rmse"])

    assert same and cross
    same_arr, cross_arr = np.asarray(same), np.asarray(cross)
    auc = float(np.mean([(c > s) + 0.5 * (c == s) for s in same_arr for c in cross_arr]))
    assert auc > 0.90, f"слабая разделимость: AUC={auc:.3f}"
    assert np.median(cross_arr) > np.median(same_arr) * 3.0


@pytest.mark.parametrize("pose", list(POSE_BINS))
def test_separability_holds_in_every_pose(archive_records, archive_zones, pose) -> None:
    """Выводы должны быть устойчивы во всех девяти ракурсах, а не только в анфас."""
    zone106, zone134 = archive_zones
    grouped = group_by_person_pose(archive_records)
    people = sorted({p for p, b in grouped if b == pose})
    if len(people) < 2:
        pytest.skip(f"недостаточно персон в ракурсе {pose}")

    same, cross = [], []
    for person in people:
        group = grouped[(person, pose)]
        if len(group) >= 2:
            result = compare_landmarks(group[0], group[1], zone106, zone134)
            if result.status == "measured":
                same.append(result.metrics["ldm134_rmse"])
    for i in range(len(people)):
        for j in range(i + 1, len(people)):
            result = compare_landmarks(grouped[(people[i], pose)][0],
                                       grouped[(people[j], pose)][0], zone106, zone134)
            if result.status == "measured":
                cross.append(result.metrics["ldm134_rmse"])

    if not same or not cross:
        pytest.skip(f"нет измеримых пар в ракурсе {pose}")
    assert np.median(cross) > np.median(same) * 3.0


def test_cross_pose_pairs_are_rejected(archive_records, archive_zones) -> None:
    """Агрессивное выравнивание не должно делать разные ракурсы сопоставимыми."""
    zone106, zone134 = archive_zones
    grouped = group_by_person_pose(archive_records)
    frontal = grouped.get(("person_01", "frontal"), [])
    profile = grouped.get(("person_01", "left_profile"), [])
    if not frontal or not profile:
        pytest.skip("нет пары ракурсов для person_01")
    result = compare_landmarks(frontal[0], profile[0], zone106, zone134)
    assert result.status == "pose_mismatch"


def test_stable_series_produces_no_return_anomaly(archive_records) -> None:
    """Сценарий S01: стабильная серия одного человека — аномалий быть не должно."""
    grouped = group_by_person_pose(archive_records)
    series = with_synthetic_dates(grouped[("person_01", "frontal")])
    timeline = [{"date": r.date, "shape": r.ldm134.reshape(-1), "photo_id": r.record_id}
                for r in series]
    assert detect_irreversible_return(timeline) == []


def test_aba_scenario_is_detected(archive_records) -> None:
    """Сценарий A→B→A: подмена в середине хронологии должна быть замечена."""
    grouped = group_by_person_pose(archive_records)
    a_frames = grouped[("person_01", "frontal")]
    b_frames = grouped[("person_02", "frontal")]
    timeline = [
        {"date": "1999-01-11", "shape": a_frames[0].ldm134.reshape(-1), "photo_id": "A1"},
        {"date": "2008-06-01", "shape": b_frames[0].ldm134.reshape(-1), "photo_id": "B1"},
        {"date": "2017-09-20", "shape": a_frames[1].ldm134.reshape(-1), "photo_id": "A2"},
    ]
    anomalies = detect_irreversible_return(timeline)
    assert len(anomalies) == 1
    assert anomalies[0]["photo_b"] == "B1"
    assert anomalies[0]["not_a_verdict"] is True


def test_synthetic_dates_are_ordered(archive_records) -> None:
    grouped = group_by_person_pose(archive_records)
    dated = with_synthetic_dates(grouped[("person_01", "frontal")])
    dates = [r.date for r in dated]
    assert dates == sorted(dates)
    assert all(d is not None for d in dates)
