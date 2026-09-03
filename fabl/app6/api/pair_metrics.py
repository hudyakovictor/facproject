"""🚪 API-слой → Полная строка `pair_metrics.csv` и артефакты прогона Stage 2.

До этого модуля интерфейс видел 13 колонок из 186: `research_timeline.py`
читал ровно то, что нужно таймлайну, а остальные 173 колонки — статистику
множественных сравнений, mesh-канал, текстуру, дескрипторы, корроборацию —
оставались на диске.

Модуль ничего не пересчитывает: он читает уже сохранённый CSV/JSON, приводит
типы (`key_catalog.coerce`) и раскладывает по категориям интерфейса
(`key_catalog.categorize_pair_columns`).

🚨 WARNING: отсутствующее значение остаётся `None`. Ноль вместо пропуска не
подставляется — `app6/AGENTS.md` это прямо запрещает.

📤 API: load_pair_metrics(), load_run_summary(), load_stage2_artifact(),
        list_stage2_artifacts(), PAIR_METRICS_SCHEMA
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .key_catalog import (
    ARTIFACT_EXTENSIONS, ARTIFACT_PLACEMENT, CATEGORY_TITLES, categorize_manifest,
    categorize_pair_columns, coerce,
)

PAIR_METRICS_SCHEMA = "deeputin-api-pair-metrics-v1.0"
RUN_SUMMARY_SCHEMA = "deeputin-api-run-summary-v1.0"

#: Максимальный размер артефакта, который отдаётся целиком (МиБ).
#: `evidence_packets.json` на большом прогоне может весить десятки мегабайт —
#: такое в браузер не отправляется, вместо этого возвращается срез.
_MAX_ARTIFACT_BYTES = 8 * 1024 * 1024


def _read_pairs(stage2_root: Path) -> list[dict[str, str]]:
    """🔍 QUERY → Все строки `pair_metrics.csv` прогона."""
    path = stage2_root / "pair_metrics.csv"
    if not path.is_file():
        raise FileNotFoundError(f"pair_metrics.csv not found under {stage2_root}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def find_pair_row(stage2_root: Path, photo_a: str, photo_b: str) -> dict[str, str] | None:
    """🔍 QUERY → Строка пары (A,B) или (B,A), если она есть в прогоне.

    Порядок фото в паре не фиксирован: Stage 2 хранит хронологический
    порядок, а пользователь мог выбрать кадры в обратном. Ищем оба варианта
    и сообщаем интерфейсу, был ли порядок перевёрнут.
    """
    for row in _read_pairs(stage2_root):
        if row.get("photo_a") == photo_a and row.get("photo_b") == photo_b:
            return {**row, "_reversed": "False"}
        if row.get("photo_a") == photo_b and row.get("photo_b") == photo_a:
            return {**row, "_reversed": "True"}
    return None


def load_pair_metrics(stage2_root: Path, photo_a: str, photo_b: str) -> dict[str, Any]:
    """🏭 FACTORY → Полный набор метрик одной пары, разложенный по категориям.

    Args:
        stage2_root: каталог вывода Stage 2 (`analysis_manifest.json` рядом).
        photo_a, photo_b: идентификаторы фотографий.

    Returns:
        Словарь с ключами `categories` (A–I), `header`, `column_count`,
        `available_count` — сколько колонок реально имеют значение.

    Raises:
        FileNotFoundError: нет `pair_metrics.csv`.
        KeyError: пара отсутствует в прогоне (её не строил Stage 2 —
            например, кадры в разных pose bin).
    """
    row = find_pair_row(stage2_root, photo_a, photo_b)
    if row is None:
        raise KeyError(f"pair not found in Stage 2 output: {photo_a} / {photo_b}")
    reversed_order = row.pop("_reversed", "False") == "True"

    categories = categorize_pair_columns(row)
    available = sum(
        1
        for groups in categories.values()
        for values in groups.values()
        for value in values.values()
        if value is not None
    )
    return {
        "schema": PAIR_METRICS_SCHEMA,
        "not_a_verdict": True,
        "source_mode": "research",
        "photo_a": photo_a,
        "photo_b": photo_b,
        "reversed_order": reversed_order,
        "column_count": len(row),
        "available_count": available,
        "category_titles": CATEGORY_TITLES,
        "categories": categories,
    }


def load_run_summary(stage2_root: Path) -> dict[str, Any]:
    """🏭 FACTORY → Сводка прогона: манифест + техотчёт + перечень артефактов.

    Читает `analysis_manifest.json` (40 ключей), `technical_summary.json`
    (счётчики статусов, ограничения) и составляет список артефактов Stage 2
    с указанием, какой раздел интерфейса их читает.
    """
    manifest_path = stage2_root / "analysis_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"analysis_manifest.json not found under {stage2_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    technical: dict[str, Any] | None = None
    tech_path = stage2_root / "technical_summary.json"
    if tech_path.is_file():
        try:
            technical = json.loads(tech_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            technical = None

    metric_catalog: dict[str, Any] | None = None
    catalog_path = stage2_root / "metric_catalog.json"
    if catalog_path.is_file():
        try:
            metric_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metric_catalog = None

    return {
        "schema": RUN_SUMMARY_SCHEMA,
        "not_a_verdict": True,
        "source_mode": "research",
        "category_titles": CATEGORY_TITLES,
        "categories": categorize_manifest(manifest),
        "technical_summary": technical,
        "metric_catalog": metric_catalog,
        "artifacts": list_stage2_artifacts(stage2_root),
    }


def list_stage2_artifacts(stage2_root: Path) -> list[dict[str, Any]]:
    """🔍 QUERY → Перечень артефактов Stage 2 с их местом в интерфейсе.

    Отсутствующие файлы тоже перечисляются (`present: false`) — иначе
    невозможно отличить «артефакт не создан» от «раздел не реализован».
    """
    out: list[dict[str, Any]] = []
    for name, (category, purpose) in sorted(ARTIFACT_PLACEMENT.items()):
        extension = ARTIFACT_EXTENSIONS.get(name, "json")
        path = stage2_root / f"{name}.{extension}"
        present = path.is_file()
        out.append({
            "name": name,
            "format": extension,
            "category": category,
            "purpose": purpose,
            "present": present,
            "size_bytes": path.stat().st_size if present else None,
        })
    return out


def load_stage2_artifact(stage2_root: Path, name: str) -> dict[str, Any]:
    """🔍 QUERY → Содержимое одного артефакта Stage 2.

    Args:
        name: имя без расширения; принимается только из
            `ARTIFACT_PLACEMENT` — произвольные пути невозможны.

    Raises:
        KeyError: имя не входит в нормативный перечень.
        FileNotFoundError: артефакт не создан этим прогоном.
    """
    if name not in ARTIFACT_PLACEMENT:
        raise KeyError(f"unknown Stage 2 artifact: {name}")
    extension = ARTIFACT_EXTENSIONS.get(name, "json")
    path = stage2_root / f"{name}.{extension}"
    if not path.is_file():
        raise FileNotFoundError(f"artifact not produced by this run: {name}.{extension}")

    size = path.stat().st_size
    truncated = size > _MAX_ARTIFACT_BYTES
    payload: Any
    row_count: int | None = None
    if truncated:
        # Крупный артефакт не отдаём целиком: интерфейсу нужна структура и
        # начало, а не десятки мегабайт. Факт усечения указывается явно.
        payload = None
    elif extension == "csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = []
            total_rows = 0
            for row in reader:
                total_rows += 1
                if len(rows) < 1000:
                    rows.append({key: coerce(value) for key, value in row.items()})
            payload = rows
            row_count = total_rows
            truncated = truncated or total_rows > len(rows)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))

    category, purpose = ARTIFACT_PLACEMENT[name]
    return {
        "schema": PAIR_METRICS_SCHEMA,
        "not_a_verdict": True,
        "name": name,
        "format": extension,
        "category": category,
        "purpose": purpose,
        "size_bytes": size,
        "truncated": truncated,
        "row_count": row_count,
        "payload": payload,
    }


def load_stage1_info(stage1_root: Path, photo_id: str) -> dict[str, Any]:
    """🔍 QUERY → `info.json` одного фото, разложенный по категориям C/D/G/H.

    Raises:
        FileNotFoundError: нет каталога фото или `info.json` в нём.
    """
    from .key_catalog import categorize_stage1_info

    photo_dir = stage1_root / photo_id
    try:
        resolved = photo_dir.resolve()
        resolved.relative_to(stage1_root.resolve())
    except ValueError:
        raise KeyError(f"invalid photo_id: {photo_id}") from None
    info_path = resolved / "info.json"
    if not info_path.is_file():
        raise FileNotFoundError(f"no info.json for {photo_id}")

    info = json.loads(info_path.read_text(encoding="utf-8"))
    categories = categorize_stage1_info(info)
    leaf_count = _count_leaves(info)
    return {
        "schema": PAIR_METRICS_SCHEMA,
        "not_a_verdict": True,
        "source_mode": "research",
        "photo_id": photo_id,
        "leaf_count": leaf_count,
        "category_titles": CATEGORY_TITLES,
        "categories": categories,
    }


def _count_leaves(node: Any) -> int:
    """Число листовых значений вложенной структуры (для честного счётчика)."""
    if isinstance(node, dict):
        return sum(_count_leaves(v) for v in node.values())
    return 1


__all__ = [
    "PAIR_METRICS_SCHEMA",
    "RUN_SUMMARY_SCHEMA",
    "coerce",
    "find_pair_row",
    "list_stage2_artifacts",
    "load_pair_metrics",
    "load_run_summary",
    "load_stage1_info",
    "load_stage2_artifact",
]
