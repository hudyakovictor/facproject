"""ТЗ п.4: детекция необратимого возврата A→B→A."""
from __future__ import annotations

import numpy as np
import pytest

from app6.stage2.irreversible_return import (
    detect_irreversible_return,
    summarize_returns,
)


@pytest.fixture(scope="module")
def shapes(records_by_person_pose):
    person_a = records_by_person_pose[("person_01", "frontal")]
    person_b = records_by_person_pose[("person_02", "frontal")]
    return person_a, person_b


def test_detects_return_over_ten_years(shapes) -> None:
    """Реальные лица: A(2000) → B(2008) → A(2016)."""
    person_a, person_b = shapes
    timeline = [
        {"date": "2000-01-01", "shape": person_a[0].ldm134.reshape(-1), "photo_id": "A1"},
        {"date": "2008-01-01", "shape": person_b[0].ldm134.reshape(-1), "photo_id": "B1"},
        {"date": "2016-01-01", "shape": person_a[1].ldm134.reshape(-1), "photo_id": "A2"},
    ]
    anomalies = detect_irreversible_return(timeline)
    assert len(anomalies) == 1
    event = anomalies[0]
    assert event["status"] == "irreversible_return_anomaly"
    assert event["gap_years"] >= 5.0
    assert event["not_a_verdict"] is True
    assert event["alternative_explanations"]


def test_no_false_positive_on_monotonic_series(shapes) -> None:
    """Стабильная серия одного человека не должна давать аномалию."""
    person_a, _ = shapes
    timeline = [{"date": f"{2000 + i * 4}-01-01",
                 "shape": person_a[i].ldm134.reshape(-1),
                 "photo_id": f"A{i}"} for i in range(5)]
    assert detect_irreversible_return(timeline) == []


def test_requires_three_points(shapes) -> None:
    person_a, person_b = shapes
    timeline = [
        {"date": "2000-01-01", "shape": person_a[0].ldm134.reshape(-1), "photo_id": "A1"},
        {"date": "2010-01-01", "shape": person_b[0].ldm134.reshape(-1), "photo_id": "B1"},
    ]
    assert detect_irreversible_return(timeline) == []


def test_short_gap_is_ignored(shapes) -> None:
    """Возврат внутри 5 лет не считается необратимым по ТЗ."""
    person_a, person_b = shapes
    timeline = [
        {"date": "2010-01-01", "shape": person_a[0].ldm134.reshape(-1), "photo_id": "A1"},
        {"date": "2011-01-01", "shape": person_b[0].ldm134.reshape(-1), "photo_id": "B1"},
        {"date": "2012-01-01", "shape": person_a[1].ldm134.reshape(-1), "photo_id": "A2"},
    ]
    assert detect_irreversible_return(timeline) == []


def test_points_without_dates_are_skipped(shapes) -> None:
    person_a, person_b = shapes
    timeline = [
        {"date": None, "shape": person_a[0].ldm134.reshape(-1), "photo_id": "A1"},
        {"date": "2008-01-01", "shape": person_b[0].ldm134.reshape(-1), "photo_id": "B1"},
        {"date": "2016-01-01", "shape": person_a[1].ldm134.reshape(-1), "photo_id": "A2"},
    ]
    assert detect_irreversible_return(timeline) == []


def test_invalid_threshold_rejected() -> None:
    with pytest.raises(ValueError):
        detect_irreversible_return([], similarity_threshold=0.0)


def test_summary_is_neutral() -> None:
    empty = summarize_returns([])
    assert empty["event_count"] == 0
    assert empty["not_a_verdict"] is True
