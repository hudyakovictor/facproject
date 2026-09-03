"""📸 CANONICAL → Детерминированная канонизация snapshot-данных (ER-173 / ER-029).

Golden snapshot должен быть независим от порядка ключей dict, нестабильной
float-точности и "-0.0". Эта функция приводит произвольное JSON-совместимое
значение к канонической форме:

- ключи dict рекурсивно сортируются;
- float округляются до фиксированной точности (default 6 знаков), в т.ч.
  внутри списков и вложенных dict;
- ``-0.0`` нормализуется в ``0.0`` (иначе строковая форма "-0.0" ≠ "0.0");
- NaN/Inf → ``None`` (нефабрикуемое отсутствие, а не битая запись).

Применяется перед сравнением/записью snapshot-артефактов, чтобы два прогона на
одинаковых данных давали побайтово одинаковый вывод.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Final

SNAPSHOT_CANONICAL_SCHEMA: Final[str] = "deeputin-snapshot-canonical-v1.0"


def canonical_snapshot(value: Any, *, float_precision: int = 6) -> Any:
    """Вернуть каноническую JSON-совместимую копию `value`.

    Args:
        value: произвольное JSON-совместимое значение (dict/list/float/int/str/bool/None)
        float_precision: число знаков после запятой для float (default 6).

    Returns:
        Каноническая копия: ключи dict отсортированы, float округлены,
        ``-0.0``→``0.0``, non-finite→``None``.
    """
    if isinstance(value, dict):
        return {str(k): canonical_snapshot(v, float_precision=float_precision)
                for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [canonical_snapshot(v, float_precision=float_precision) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        if value == 0.0:
            return 0.0  # нормализует -0.0 → 0.0
        return round(value, float_precision)
    return value


def canonical_json(value: Any, *, float_precision: int = 6) -> dict[str, Any]:
    """Обёртка: метаданные канонизации + каноническое значение для snapshot-файла.

    Returns:
        dict с `schema`, `canonical_version`, `float_precision` и
        `payload` (каноническая копия `value`).
    """
    return {
        "schema": SNAPSHOT_CANONICAL_SCHEMA,
        "canonical_version": "v1",
        "float_precision": int(float_precision),
        "payload": canonical_snapshot(value, float_precision=float_precision),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ER-177: сравнение канонических snapshot-ов с допусками по категориям полей.
# Golden-сравнение «всё или ничего» ломается от незначащего float-дрейфа. Вместо
# этого допуск определяется категорией поля, а точные поля сравниваются строго.
# ─────────────────────────────────────────────────────────────────────────────

#: Дефолтные категории и их допуски.
#:   tolerance      — допустимое абсолютное/относительное отклонение float;
#:   exact          — True если поле обязано совпасть точно (строка/целое/булево).
#: Категория назначается подстрокой в имени поля (первое совпадение выигрывает).
DEFAULT_FIELD_CATEGORIES: Final[tuple[tuple[str, dict[str, Any]], ...]] = (
    ("p95", {"tolerance": 1e-3, "exact": False}),
    ("median", {"tolerance": 1e-3, "exact": False}),
    ("rmse", {"tolerance": 1e-3, "exact": False}),
    ("z", {"tolerance": 1e-2, "exact": False}),
    ("hash", {"tolerance": 0.0, "exact": True}),
    ("digest", {"tolerance": 0.0, "exact": True}),
    ("schema", {"tolerance": 0.0, "exact": True}),
    ("version", {"tolerance": 0.0, "exact": True}),
    ("date", {"tolerance": 0.0, "exact": True}),
)


def snapshot_category(field_name: str, categories=DEFAULT_FIELD_CATEGORIES) -> dict[str, Any]:
    """Определить категорию допуска поля по подстроке в имени (default: exact)."""
    low = str(field_name).lower()
    for substr, spec in categories:
        if substr in low:
            return spec
    return {"tolerance": 0.0, "exact": True}


def _near(a: float, b: float, tol: float) -> bool:
    if tol <= 0:
        return a == b
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def compare_snapshots(
    expected: Any, actual: Any,
    *,
    categories=DEFAULT_FIELD_CATEGORIES,
    float_precision: int = 6,
) -> dict[str, Any]:
    """Сравнить канонические snapshot-ы с допуском по категориям полей.

    Args:
        expected: ожидаемый (golden) канонический snapshot.
        actual: фактический snapshot.
        categories: допуски по категориям полей (подстрока имени → spec).
        float_precision: точность канонизации float до сравнения.

    Returns:
        ``{"match": bool, "field_count": int, "mismatches": [...]}`` — где каждая
        запись в ``mismatches``: ``{ "field": path, "status": "numeric_drift" |
        "mismatch" | "missing", "expected": ..., "actual": ...}``.
    """
    exp = canonical_snapshot(expected, float_precision=float_precision)
    act = canonical_snapshot(actual, float_precision=float_precision)
    mismatches: list[dict[str, Any]] = []
    field_count = 0

    def _walk(e, a, path: str) -> None:
        nonlocal field_count
        if isinstance(e, dict) and isinstance(a, dict):
            keys = sorted(set(e) | set(a))
            for k in keys:
                child = f"{path}." + str(k) if path else str(k)
                if k not in e:
                    mismatches.append({"field": child, "status": "unexpected", "expected": None, "actual": a[k]})
                elif k not in a:
                    mismatches.append({"field": child, "status": "missing", "expected": e[k], "actual": None})
                else:
                    _walk(e[k], a[k], child)
            return
        if isinstance(e, list) and isinstance(a, list):
            if len(e) != len(a):
                mismatches.append({"field": path or "<root>", "status": "length", "expected": len(e), "actual": len(a)})
                return
            for i, (x, y) in enumerate(zip(e, a, strict=True)):
                _walk(x, y, f"{path}[{i}]")
            return
        field_count += 1
        if isinstance(e, float) and isinstance(a, float):
            tol = snapshot_category(path.split(".")[-1], categories)["tolerance"]
            if not _near(e, a, tol):
                mismatches.append({"field": path or "<root>", "status": "numeric_drift",
                                   "expected": e, "actual": a, "tolerance": tol})
            return
        if e != a:
            mismatches.append({"field": path or "<root>", "status": "mismatch",
                               "expected": e, "actual": a})

    _walk(exp, act, "")
    return {"match": not mismatches, "field_count": field_count, "mismatches": mismatches}


# ─────────────────────────────────────────────────────────────────────────────
# ER-168: детерминированная сериализация/чтение канонического snapshot-файла.
# Golden fixture хранится на диске; повторная запись обязана давать побайтово
# тот же файл, иначе сравнение «golden vs fresh» не имеет смысла.


def write_snapshot(path: Path, value: Any, *, float_precision: int = 6,
                   pretty: bool = True) -> Path:
    """Детерминированно записать канонический snapshot на диск.

    Args:
        path: целевой файл.
        value: значение для канонизации и записи.
        float_precision: точность канонизации float.
        pretty: True — отступ 2 (читаемо), False — компактно; и то и другое
            остаётся детерминированным (sort_keys=True, фиксир. separators).

    Returns:
        path (для проверки).
    """
    canonical = canonical_json(value, float_precision=float_precision)
    payload = json.dumps(
        canonical, indent=2 if pretty else None,
        sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":") if not pretty else (",", ": "),
    ) + "\n"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(p)
    return p


def read_snapshot(path: Path) -> dict[str, Any]:
    """Прочитать канонический snapshot-файл (возвращает включая metadata)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def snapshot_file_roundtrip_is_deterministic(path: Path, value: Any, *, float_precision: int = 6) -> bool:
    """True, если повторная запись даёт побайтово идентичный файл (ER-029)."""
    write_snapshot(path, value, float_precision=float_precision)
    first = Path(path).read_text(encoding="utf-8")
    write_snapshot(path, value, float_precision=float_precision)
    second = Path(path).read_text(encoding="utf-8")
    return first == second