"""Regression-тест для `app6/test_module/runner.py` (обязательная лестница, AGENTS.md).

Использует полностью синтетический архив (`synthetic_archive.py`), а не
`selected_photos_7x9x3_data.tar.gz`, поэтому не требует внешних данных и
всегда проверяет реальное поведение раздачи ролей + вызовов Stage 2 core.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app6.test_module.runner import execute
from app6.test_module.scenarios import POSE_BINS, SCENARIOS
from app6.test_module.synthetic_archive import build_synthetic_archive


@pytest.fixture(scope="module")
def synthetic_archive(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("synthetic")
    return build_synthetic_archive(root / "flat")


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_first_rung_passes_for_every_scenario(synthetic_archive, scenario) -> None:
    """Ступень 1 лестницы: один ракурс, одна комбинация — обязана быть зелёной."""
    report = execute(scenario, "frontal", 1, archive=synthetic_archive)
    assert report["overall_status"] == "pass", report


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_all_nine_poses_pass(synthetic_archive, scenario) -> None:
    """Ступень 2 лестницы: тот же сценарий во всех девяти ракурсах."""
    report = execute(scenario, "all", 1, archive=synthetic_archive, fail_fast=False)
    assert report["overall_status"] == "pass", report
    assert report["pass_count"] == len(POSE_BINS)


def test_growing_combinations_stay_green(synthetic_archive) -> None:
    """Ступень 3 лестницы: комбинации 2..4 для S01 не должны деградировать."""
    for combinations in (2, 3, 4):
        report = execute("S01", "frontal", combinations, archive=synthetic_archive, fail_fast=False)
        assert report["overall_status"] == "pass", report
        assert report["fail_count"] == 0


def test_unknown_scenario_rejected(synthetic_archive) -> None:
    with pytest.raises(ValueError):
        execute("S99", "frontal", 1, archive=synthetic_archive)


def test_missing_archive_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        execute("S01", "frontal", 1, archive=tmp_path / "does_not_exist.tar.gz")


def test_negative_control_stable_series_check_can_fail(synthetic_archive) -> None:
    """Гарантия против фальшиво-зелёных тестов: подмена в стабильной серии обязана провалить S01-проверку."""
    from app6.test_module.archive_adapter import group_by_person_pose, load_archive_records
    from app6.test_module.runner import _check_stable_series
    from app6.test_module.scenarios import timeline_from_combo
    from app6.stage2.irreversible_return import detect_irreversible_return
    import tarfile

    extract_dir = synthetic_archive.parent / "extracted_for_negative_control"
    if not extract_dir.exists():
        extract_dir.mkdir()
        with tarfile.open(synthetic_archive) as tar:
            tar.extractall(extract_dir)
    grouped = group_by_person_pose(load_archive_records(extract_dir))
    person_a = grouped[("person_01", "frontal")]
    person_b = grouped[("person_02", "frontal")]
    fake_stable_series = [person_a[0], person_b[0], person_a[1]]  # secretly A-B-A, not A-A-A
    outcome = _check_stable_series(fake_stable_series, timeline_from_combo, detect_irreversible_return)
    assert outcome["passed"] is False
