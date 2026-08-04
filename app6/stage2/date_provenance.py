"""🚧 GATE → Разрешение даты кадра и её точности.

Основной датасет несёт дату в имени файла — это claimed date, не факт.
Калибровочные наборы дат не имеют и иметь не должны: пары там подбираются по
близости позы. Подстановка фиктивных дат в калибровку запрещена — она
превращает калибровочный набор в источник ложных хронологических флагов.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Final

DATE_PROVENANCE_SCHEMA: Final[str] = "deeputin-date-provenance-v1.0"

#: Приоритет источников: EXIF надёжнее имени файла, имя надёжнее утверждения.
SOURCE_PRIORITY: Final[tuple[str, ...]] = ("exif", "filename", "claimed")

#: Расхождение свыше этого числа дней считается конфликтом, а не округлением.
CONFLICT_DAYS: Final[int] = 3

_DAY = re.compile(r"(19|20)\d{2}[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])")
_MONTH = re.compile(r"(19|20)\d{2}[-_.]?(0[1-9]|1[0-2])(?!\d)")
_YEAR = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")


def parse_filename_date(name: str) -> tuple[str | None, str]:
    """Извлечь дату из имени файла вместе с её точностью."""
    text = str(name)
    m = _DAY.search(text)
    if m:
        digits = re.sub(r"\D", "", m.group(0))
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}", "day"
    m = _MONTH.search(text)
    if m:
        digits = re.sub(r"\D", "", m.group(0))
        return f"{digits[0:4]}-{digits[4:6]}-01", "month"
    m = _YEAR.search(text)
    if m:
        return f"{m.group(0)}-01-01", "year"
    return None, "none"


def _delta_days(a: str | None, b: str | None) -> int | None:
    try:
        return abs((date.fromisoformat(str(a)[:10]) - date.fromisoformat(str(b)[:10])).days)
    except (TypeError, ValueError):
        return None


def resolve_date(*, filename: str | None = None, exif_date: str | None = None,
                 claimed_date: str | None = None,
                 dataset_role: str = "evidence") -> dict[str, Any]:
    """Определить дату кадра, её точность и статус происхождения."""
    if dataset_role == "calibration":
        return {"schema": DATE_PROVENANCE_SCHEMA,
                "date": None, "date_precision": "none",
                "date_provenance_status": "not_applicable",
                "date_delta_days": None, "date_conflict_sources": [],
                "note": "калибровочный набор упорядочивается по позе и sequence"}

    fn_date, fn_precision = parse_filename_date(filename or "")
    # Игнорировать EXIF-даты, лежащие более чем на 365 дней в будущем
    # относительно даты из имени файла: типично для пересканированных
    # фото, где EXIF содержит дату сканирования, а не съёмки.
    if exif_date:
        try:
            exif_d = date.fromisoformat(exif_date[:10])
            if fn_date:
                fn_d = date.fromisoformat(fn_date[:10])
                if (exif_d - fn_d).days > 365:
                    exif_date = None
        except (TypeError, ValueError):
            pass
    candidates = {"exif": (exif_date, "day"),
                  "filename": (fn_date, fn_precision),
                  "claimed": (claimed_date, "day")}
    chosen_source = next((s for s in SOURCE_PRIORITY if candidates[s][0]), None)
    if chosen_source is None:
        return {"schema": DATE_PROVENANCE_SCHEMA,
                "date": None, "date_precision": "none",
                "date_provenance_status": "missing",
                "date_delta_days": None, "date_conflict_sources": []}

    value, precision = candidates[chosen_source]
    conflicts: list[str] = []
    worst = 0
    for other, (other_value, _) in candidates.items():
        if other == chosen_source or not other_value:
            continue
        d = _delta_days(value, other_value)
        if d is not None and d > CONFLICT_DAYS:
            conflicts.append(other)
            worst = max(worst, d)

    status = "conflict" if conflicts else f"resolved_{chosen_source}"
    return {"schema": DATE_PROVENANCE_SCHEMA,
            "date": value,
            "date_precision": precision,
            "date_provenance_status": status,
            "date_source": chosen_source,
            "date_delta_days": (worst or None),
            "date_conflict_sources": conflicts}
