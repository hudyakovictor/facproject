"""🚧 GATE → Единая точка решения: применима ли временная ось.

Временные детекторы (irreversible_return, same_day_gate, chronology,
alpha_chronology, motion, baseline_return) обязаны спрашивать этот модуль,
а не проверять `record.date` россыпью условий. Отсутствие даты у калибровки —
не ошибка данных, а свойство набора, и результат должен это отражать.
"""
from __future__ import annotations

from typing import Any, Final, Sequence

TEMPORAL_AXIS_SCHEMA: Final[str] = "deeputin-temporal-axis-v1.0"

#: Минимум датированных кадров и различных дат для любого временного вывода.
MIN_DATED_RECORDS: Final[int] = 3
MIN_DISTINCT_DATES: Final[int] = 2

SKIPPED_NO_AXIS: Final[str] = "skipped_no_temporal_axis"


def temporal_status(records: Sequence[Any]) -> dict[str, Any]:
    total = len(records)
    roles = {getattr(r, "dataset_role", "evidence") for r in records}
    usable = [r for r in records if getattr(r, "has_temporal_axis", lambda: False)()]
    dates = {str(getattr(r, "date", ""))[:10] for r in usable}
    coarse = sum(1 for r in usable if getattr(r, "date_precision", "day") != "day")

    if roles == {"calibration"}:
        return {"schema": TEMPORAL_AXIS_SCHEMA, "applicable": False,
                "status": SKIPPED_NO_AXIS, "reason": "calibration_dataset",
                "record_count": total, "dated_count": 0,
                "note": "калибровка упорядочивается по позе и sequence"}
    if len(usable) < MIN_DATED_RECORDS or len(dates) < MIN_DISTINCT_DATES:
        return {"schema": TEMPORAL_AXIS_SCHEMA, "applicable": False,
                "status": SKIPPED_NO_AXIS, "reason": "insufficient_dated_records",
                "record_count": total, "dated_count": len(usable),
                "distinct_dates": len(dates)}
    return {"schema": TEMPORAL_AXIS_SCHEMA, "applicable": True,
            "status": "ok", "record_count": total, "dated_count": len(usable),
            "distinct_dates": len(dates),
            "coarse_precision_count": int(coarse),
            "confidence": "limited_coarse_dates" if coarse else "normal"}


def require_temporal_axis(records: Sequence[Any]) -> dict[str, Any] | None:
    """Вернуть готовый skip-результат либо None, если ось применима."""
    st = temporal_status(records)
    return None if st["applicable"] else st
