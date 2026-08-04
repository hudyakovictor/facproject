"""📤 OUTPUT → Валидация табличных выгрузок Stage 2.

ТЗ п.14: заголовки CSV должны быть стабильны между прогонами и соответствовать
эталонному списку. Аудит (D9) показал: `write_csv` корректно объединяет ключи,
но порядок колонок зависит от порядка ключей в первой строке — два прогона на
одних данных давали `a,b` и `b,a`, из-за чего diff артефактов нечитаем.
"""
from __future__ import annotations

from typing import Any, Final, Iterable, Sequence

EXPORT_SCHEMA: Final[str] = "deeputin-stage2-export-v1.0"


class CsvHeaderError(ValueError):
    """Заголовки выгрузки не соответствуют контракту."""


def validate_csv_headers(
    data: list[dict[str, Any]],
    expected_fields: Sequence[str],
    strict: bool = True,
) -> bool:
    """📤 OUTPUT → Проверить соответствие полей строк эталонному списку.

    Args:
        data: строки будущей таблицы.
        expected_fields: эталонный порядок и состав колонок.
        strict: при True отсутствие поля — ошибка; при False — предупреждение.

    Returns:
        True, если все строки содержат все ожидаемые поля и нет лишних.

    Raises:
        CsvHeaderError: при `strict=True` и отсутствующих полях.
        ValueError: если эталонный список пуст или содержит дубликаты.
    """
    expected = list(expected_fields)
    if not expected:
        raise ValueError("expected_fields не может быть пустым")
    if len(set(expected)) != len(expected):
        raise ValueError("expected_fields содержит дубликаты")
    if not data:
        return True

    expected_set = set(expected)
    missing: set[str] = set()
    extra: set[str] = set()
    for row in data:
        keys = set(row)
        missing |= expected_set - keys
        extra |= keys - expected_set

    if missing and strict:
        raise CsvHeaderError(f"в строках отсутствуют обязательные поля: {sorted(missing)[:12]}")
    return not missing and not extra


def stable_fieldnames(rows: Iterable[dict[str, Any]],
                      preferred: Sequence[str] | None = None) -> list[str]:
    """📤 OUTPUT → Детерминированный порядок колонок, не зависящий от порядка строк.

    Поля из `preferred` идут первыми в заданном порядке; остальные добавляются по
    алфавиту. Это устраняет дрейф заголовков между прогонами (D9).
    """
    seen: set[str] = set()
    for row in rows:
        seen.update(row)
    head = [f for f in (preferred or []) if f in seen]
    tail = sorted(seen - set(head))
    return head + tail
