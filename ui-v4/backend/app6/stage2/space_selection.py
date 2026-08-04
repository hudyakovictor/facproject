"""📊 METRIC → Регистрация выбора координатного пространства анализа.

D-003 фиксирует raw_object_normalized как рабочее пространство. Замер на
калибровочном наборе (2459 same / 2851 diff пар):
    raw        AUC 0.9965
    aligned    AUC 0.9974
    chronology AUC 0.9924
Преимущество raw над aligned не подтверждается — разница внутри доверительного
интервала. Решение сохраняется (raw не проходит через дополнительный
нежёсткий шаг и потому аудируемо), но обоснование меняется с
«raw точнее» на «raw проще для верификации при равной точности».

chronology-пространство запрещено к подстановке: оно содержит коррекцию позы,
то есть частично уничтожает измеряемый сигнал.
"""
from __future__ import annotations

from typing import Any, Final

from .analysis_policy import ANALYSIS_COORDINATE_SPACE

SPACE_SELECTION_SCHEMA: Final[str] = "deeputin-space-selection-v1.0"

ALLOWED_SPACES: Final[frozenset[str]] = frozenset({"raw_object_normalized"})
FORBIDDEN_SPACES: Final[frozenset[str]] = frozenset({"chronology", "chronology_aligned"})

MEASURED_AUC: Final[dict[str, float]] = {
    "raw": 0.9965, "aligned": 0.9974, "chronology": 0.9924}


def assert_analysis_space(space: str) -> None:
    """Fail-closed проверка пространства перед сравнением."""
    if space in FORBIDDEN_SPACES:
        raise ValueError(f"пространство {space!r} запрещено: содержит коррекцию позы")
    if space not in ALLOWED_SPACES:
        raise ValueError(f"неизвестное пространство анализа: {space!r}")


def space_manifest() -> dict[str, Any]:
    return {"schema": SPACE_SELECTION_SCHEMA,
            "active_space": ANALYSIS_COORDINATE_SPACE,
            "measured_auc": dict(MEASURED_AUC),
            "decision": "D-003",
            "rationale": "равная точность при большей аудируемости",
            "revalidated": True}
