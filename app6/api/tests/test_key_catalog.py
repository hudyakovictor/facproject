"""Тесты распределения ключей пайплайна по разделам интерфейса.

Главная проверка — «ни одна колонка не потеряна»: именно потеря ключей была
исходной проблемой (176 из 186 колонок не покидали диск).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app6.api.key_catalog import (
    ARTIFACT_PLACEMENT, CATEGORY_TITLES, categorize_manifest, categorize_pair_columns,
    categorize_stage1_info, category_for, coerce,
)
from app6.api.pair_metrics import (
    find_pair_row, list_stage2_artifacts, load_pair_metrics, load_run_summary,
    load_stage2_artifact,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STAGE2_FIXTURE = PROJECT_ROOT / "app6" / "test_data" / "S04_fdr_stress_A_p05_v00"
STAGE1_FIXTURE = PROJECT_ROOT / "3ddfa_v3" / "examples" / "results" / "2000_06_14"


def _columns() -> list[str]:
    with (STAGE2_FIXTURE / "pair_metrics.csv").open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def _first_row() -> dict[str, str]:
    with (STAGE2_FIXTURE / "pair_metrics.csv").open(newline="", encoding="utf-8") as handle:
        return next(csv.DictReader(handle))


# --- распределение ----------------------------------------------------------

def test_every_column_has_explicit_category() -> None:
    """Ни одна колонка не должна попадать в fallback `I/other`."""
    unassigned = [c for c in _columns() if category_for(c) == ("I", "other")]
    assert unassigned == [], f"колонки без явной категории: {unassigned}"


def test_all_categories_have_titles() -> None:
    used = {category_for(c)[0] for c in _columns()}
    assert used <= set(CATEGORY_TITLES)
    for title in CATEGORY_TITLES.values():
        assert title["ru"] and title["en"]


def test_categorize_preserves_all_columns() -> None:
    row = _first_row()
    categories = categorize_pair_columns(row)
    flat = {
        key
        for groups in categories.values()
        for values in groups.values()
        for key in values
    }
    assert flat == set(row), "распределение потеряло или выдумало колонки"


def test_unknown_column_falls_back_to_run_summary() -> None:
    """Новая колонка Stage 2 должна стать видимой, а не исчезнуть молча."""
    assert category_for("brand_new_metric_v9") == ("I", "other")


# --- приведение типов -------------------------------------------------------

@pytest.mark.parametrize(("raw", "expected"), [
    ("", None), ("nan", None), ("None", None), ("null", None),
    ("True", True), ("False", False),
    ("12", 12), ("-3", -3), ("0.5", 0.5),
    ("frontal", "frontal"),
])
def test_coerce(raw: str, expected: object) -> None:
    assert coerce(raw) == expected


def test_coerce_never_turns_missing_into_zero() -> None:
    """`AGENTS.md` запрещает подменять пропуск нулём."""
    for missing in ("", "nan", "NaN", "none", "NULL"):
        assert coerce(missing) is None


def test_coerce_keeps_zero_as_zero() -> None:
    assert coerce("0") == 0
    assert coerce("0.0") == 0.0


# --- загрузка пары ----------------------------------------------------------

def test_load_pair_metrics_returns_full_row() -> None:
    row = _first_row()
    payload = load_pair_metrics(STAGE2_FIXTURE, row["photo_a"], row["photo_b"])
    assert payload["column_count"] == len(row)
    assert payload["not_a_verdict"] is True
    assert payload["reversed_order"] is False
    # Категория A обязана содержать поправку на множественные сравнения:
    # без неё интерфейс показывает аномалии, часть которых ложные.
    assert "mt_q_value" in payload["categories"]["A"]["multiple_testing"]


def test_load_pair_metrics_accepts_reversed_order() -> None:
    row = _first_row()
    payload = load_pair_metrics(STAGE2_FIXTURE, row["photo_b"], row["photo_a"])
    assert payload["reversed_order"] is True


def test_load_pair_metrics_missing_pair_raises() -> None:
    with pytest.raises(KeyError):
        load_pair_metrics(STAGE2_FIXTURE, "no_such_a", "no_such_b")


def test_find_pair_row_none_for_unknown() -> None:
    assert find_pair_row(STAGE2_FIXTURE, "x", "y") is None


def test_available_count_excludes_missing() -> None:
    row = _first_row()
    payload = load_pair_metrics(STAGE2_FIXTURE, row["photo_a"], row["photo_b"])
    assert payload["available_count"] <= payload["column_count"]
    # На эталонном прогоне заполнено подавляющее большинство колонок.
    assert payload["available_count"] > payload["column_count"] * 0.8


# --- прогон и артефакты -----------------------------------------------------

def test_load_run_summary() -> None:
    payload = load_run_summary(STAGE2_FIXTURE)
    manifest = json.loads((STAGE2_FIXTURE / "analysis_manifest.json").read_text(encoding="utf-8"))
    flat = {
        key
        for groups in payload["categories"].values()
        for values in groups.values()
        for key in values
    }
    assert flat == set(manifest)


def test_artifacts_list_marks_absent_files() -> None:
    """Отсутствующий артефакт должен быть перечислен, а не пропущен."""
    artifacts = list_stage2_artifacts(STAGE2_FIXTURE)
    assert len(artifacts) == len(ARTIFACT_PLACEMENT)
    assert any(a["present"] for a in artifacts)
    assert any(not a["present"] for a in artifacts)


def test_load_artifact_rejects_arbitrary_name() -> None:
    with pytest.raises(KeyError):
        load_stage2_artifact(STAGE2_FIXTURE, "../../etc/passwd")


def test_load_existing_artifact() -> None:
    payload = load_stage2_artifact(STAGE2_FIXTURE, "calibration_noise_model")
    assert payload["payload"] is not None
    assert payload["truncated"] is False
    assert payload["category"] == "A"


def test_load_absent_artifact_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_stage2_artifact(STAGE2_FIXTURE, "evidence_packets")


def test_manifest_categories_are_known() -> None:
    manifest = json.loads((STAGE2_FIXTURE / "analysis_manifest.json").read_text(encoding="utf-8"))
    for category in categorize_manifest(manifest):
        assert category in CATEGORY_TITLES


# --- Stage 1 ----------------------------------------------------------------

@pytest.mark.skipif(not (STAGE1_FIXTURE / "info.json").is_file(), reason="нет эталонного info.json")
def test_categorize_stage1_info_covers_all_roots() -> None:
    info = json.loads((STAGE1_FIXTURE / "info.json").read_text(encoding="utf-8"))
    categories = categorize_stage1_info(info)
    assert set(categories) <= set(CATEGORY_TITLES)
    # Провенанс обязан содержать хэш исходника: без него результат
    # невоспроизводим.
    assert "source_sha256" in categories["G"]["source"]
    # Параметры кадра — категория C.
    assert "laplacian_variance" in categories["C"]["frame_inputs"]
