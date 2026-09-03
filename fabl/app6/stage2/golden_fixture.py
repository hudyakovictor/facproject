"""🎯 GOLDEN → Детерминированный синтетический snapshot E2E (ER-168 / R-G05).

Покрывает сценарии golden-synthetic fixture: конфликты дат, чистая пара, NULL
(отсутствующие метрики → null, а не ноль-подмена), резкое изменение ("step") и
возврат ("return" A→B→A), а также все 9 канонических pose bins (D-001).

Все данные — строго детерминированные (без случайности). Модуль переиспользует
ER-173 (канонизация) и ER-177 (сравнение с допуском), поэтому snapshot побайтово
стабилен между прогонами (R-G04).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Final

from .snapshot_canonical import canonical_json, write_snapshot

GOLDEN_FIXTURE_SCHEMA: Final[str] = "deeputin-golden-synthetic-v1.0"
GOLDEN_FIXTURE_VERSION: Final[str] = "v2"  # + NULL/step/return/pose-bins (R-G05)
CONFLICT_DAYS: Final[int] = 3  # совпадает с date_provenance.CONFLICT_DAYS

#: Канонические pose bins (D-001) — согласовано с pose_policy.py.
CANONICAL_POSE_BINS: Final[tuple[str, ...]] = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)

#: Сценарные пары: (photo_a, photo_b, date_a, date_b, scenario, pose_bin).
#: scenario ∈ {date_conflict, clean, null, step, return_a_b_a}; покрывает все 9 pose bins.
_PAIRS: Final[tuple[tuple[str, str, str, str, str, str], ...]] = (
    ("2020_01_01_1", "2020_01_15_1", "2020-01-01", "2020-01-15", "date_conflict", "frontal"),
    ("2019_06_10_1", "2019_06_20_1", "2019-06-10", "2019-06-20", "clean", "left_light"),
    # NULL: отсутствующие метрики даты — маркер, а не ноль-подмена.
    ("2018_02_01_1", "2018_02_05_1", "2018-02-01", "2018-02-05", "null", "right_mid"),
    # step: резкое согласованное изменение (скачок).
    ("2017_03_01_1", "2017_03_30_1", "2017-03-01", "2017-03-30", "step", "left_deep"),
    # return: A→B→A — Tstab уже близка к ранней дате (возврат).
    ("2016_04_02_1", "2016_04_18_1", "2016-04-02", "2016-04-18", "return_a_b_a", "right_profile"),
    # Доп. пары для покрытия оставшихся 4 бинов (чистые/Clean = диагностически нейтральные).
    ("2015_05_01_1", "2015_05_11_1", "2015-05-01", "2015-05-11", "clean", "right_light"),
    ("2014_06_01_1", "2014_06_12_1", "2014-06-01", "2014-06-12", "clean", "left_mid"),
    ("2013_07_01_1", "2013_07_13_1", "2013-07-01", "2013-07-13", "clean", "left_profile"),
    ("2012_08_01_1", "2012_08_14_1", "2012-08-01", "2012-08-14", "clean", "right_deep"),
)


def _deltat_days(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def _scenario_metrics(scenario: str, pose: str, conflict: bool) -> dict[str, Any]:
    """Детерминированные метрики по сценарию (None для отсутствующего)."""
    if scenario == "null":
        # Отсутствующие метрики → None (канонизируется в null), а не 0.
        return {
            "mesh_p95": None,
            "primary_robust_z": None,
            "significant_point_fraction": None,
            "looked_up": False,
        }
    base: dict[str, Any] = {"looked_up": True}
    if scenario == "date_conflict":
        base.update({"mesh_p95": 1.25, "primary_robust_z": 2.4})
    elif scenario == "clean":
        base.update({"mesh_p95": 0.75, "primary_robust_z": 0.4})
    elif scenario == "step":
        base.update({"mesh_p95": 2.1, "primary_robust_z": 3.9})
    elif scenario == "return_a_b_a":
        # Возврат: Tstab снова близка к ранней дате (диагностический маркер).
        base.update({"mesh_p95": 0.9, "primary_robust_z": 0.6, "return_ab_a": True})
    base["pose_bin"] = pose
    return base


def build_golden_snapshot_data() -> dict[str, Any]:
    """Детерминированные синтетические данные со всеми сценариями R-G05.

    Возвращает dict с парами, покрывающими 9 pose bins и сценарии date_conflict
    / clean / null / step / return_a_b_a.
    """
    pairs: list[dict[str, Any]] = []
    for i, (pa, pb, da, db, scenario, pose) in enumerate(_PAIRS):
        conflict = bool(i % 2 == 0 and i < 2)  # 1-я пара — date-conflict
        row: dict[str, Any] = {
            "photo_a": pa, "photo_b": pb,
            "date_a": da, "date_b": db,
            "date_span_days": _deltat_days(da, db),
            "date_conflict_sources": ["filename", "exif"] if (conflict and i == 0) else [],
            "date_provenance_status": "conflict" if (conflict and i == 0) else "resolved_filename",
            "scenario": scenario,
            "pose_bin": pose,
        }
        row.update(_scenario_metrics(scenario, pose, conflict))
        pairs.append(row)
    pose_bins_present = sorted({p["pose_bin"] for p in pairs})
    return {
        "schema": GOLDEN_FIXTURE_SCHEMA,
        "fixture_version": GOLDEN_FIXTURE_VERSION,
        "source": "deterministic_synthetic",
        "pair_count": len(pairs),
        "scenarios": sorted({p["scenario"] for p in pairs}),
        "pose_bin_count": len(pose_bins_present),
        "pose_bins": pose_bins_present,
        "has_date_conflict_pair": any(bool(p["date_conflict_sources"]) for p in pairs),
        "has_null_pair": any(p["scenario"] == "null" for p in pairs),
        "has_step_pair": any(p["scenario"] == "step" for p in pairs),
        "has_return_pair": any(p["scenario"] == "return_a_b_a" for p in pairs),
        "pairs": pairs,
    }


def write_golden_snapshot(path: Any, *, float_precision: int = 6) -> Any:
    """Записать детерминированный golden snapshot (R-G05) в канонической форме."""
    return write_snapshot(path, build_golden_snapshot_data(), float_precision=float_precision)


def golden_canonical() -> dict[str, Any]:
    """Каноническая форма golden-данных (для сравнения/тестов)."""
    return canonical_json(build_golden_snapshot_data())