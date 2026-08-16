"""🚪 API-слой → Публичный отчёт Stage 3 (`report_data.json`).

Stage 3 — единственный этап пайплайна, у которого не было ни одного
эндпоинта. Он строит самостоятельный HTML со встроенным JSON и кладёт рядом
`report_data.json` (~45 ключей верхнего уровня и вложенных секций), но
рабочая станция об этом ничего не знала: чтобы увидеть итоговый отчёт,
нужно было открыть файл с диска мимо интерфейса.

🚨 WARNING: ключ `status` в Stage 3 означает НЕ ТО ЖЕ, что в Stage 2.
`stage3.engine.public_pair_projection` подменяет его на `evidence_state`, а
исходный измерительный статус переносит в `measurement_status`. Модуль
сохраняет оба и помечает это в `status_semantics`, иначе сравнение отчёта
с таблицей пары привело бы к ложному выводу о расхождении данных.

🚨 WARNING: Stage 3 намеренно вырезает из публикации колонки `texture_*` и
`uv_*`. Их отсутствие в отчёте — не потеря данных, а политика публикации;
модуль сообщает об этом явно (`withheld_column_prefixes`).

📤 API: load_report_summary(), load_report_section(), REPORT_SCHEMA
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPORT_SCHEMA = "deeputin-api-report-v1.0"

#: Секции `report_data.json`, которые отдаются поимённо. Список закрытый:
#: произвольный ключ запросить нельзя.
REPORT_SECTIONS: dict[str, str] = {
    "narrative": "Расследовательская сводка",
    "timelines": "Хронология движения точек по ракурсам",
    "motion_maps": "Карты движения LDM134",
    "pairs": "Все сравнения",
    "lead_pairs": "Пересечения с архивом зацепок",
    "lead_registry": "Реестр прежних зацепок",
    "change_points": "Кандидаты устойчивых изменений",
    "zones": "Зонные метрики",
    "metric_catalog": "Каталог метрик",
    "methodology": "Методология",
    "publication_drafts": "Публикационные черновики и claims ledger",
    "analysis_manifest": "Манифест Stage 2",
    "summary": "Счётчики отчёта",
}

#: Префиксы колонок, которые Stage 3 не публикует (политика, не пропуск).
WITHHELD_COLUMN_PREFIXES = ("texture_", "uv_")

#: Секции, которые могут быть очень объёмными: `motion_maps` — до 40 пар по
#: 134 точки, `pairs` — все колонки каждой пары. Отдаются страницами.
_PAGED_SECTIONS = frozenset({"motion_maps", "pairs", "zones", "change_points", "lead_pairs"})

#: Размер страницы по умолчанию для крупных секций.
DEFAULT_PAGE_SIZE = 100


def _read_report(stage3_root: Path) -> dict[str, Any]:
    """🔍 QUERY → `report_data.json` прогона Stage 3."""
    path = stage3_root / "report_data.json"
    if not path.is_file():
        raise FileNotFoundError(f"report_data.json not found under {stage3_root}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("report_data.json must contain an object")
    return data


def _read_validation(stage3_root: Path) -> dict[str, Any] | None:
    """🔍 QUERY → `report_validation.json`, если Stage 3 его записал."""
    path = stage3_root / "report_validation.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _section_size(value: Any) -> int | None:
    """Число элементов секции — для честного индикатора объёма."""
    if isinstance(value, (list, dict)):
        return len(value)
    return None


def load_report_summary(stage3_root: Path) -> dict[str, Any]:
    """🏭 FACTORY → Обзор отчёта Stage 3 без тяжёлых секций.

    Возвращает счётчики, нарратив, методологию, статус валидации и перечень
    секций с их размером. Крупные массивы (`pairs`, `motion_maps`) не
    передаются — за ними идёт `load_report_section`.

    Raises:
        FileNotFoundError: прогон Stage 3 не выполнялся.
    """
    data = _read_report(stage3_root)
    validation = _read_validation(stage3_root)

    sections = [
        {
            "name": name,
            "title": title,
            "present": name in data,
            "size": _section_size(data.get(name)),
            "paged": name in _PAGED_SECTIONS,
        }
        for name, title in REPORT_SECTIONS.items()
    ]

    manifest = data.get("analysis_manifest")
    manifest = manifest if isinstance(manifest, dict) else {}

    return {
        "schema": REPORT_SCHEMA,
        "not_a_verdict": True,
        "source_mode": "research",
        "report_schema_version": data.get("schema_version"),
        "stage2_schema_version": manifest.get("schema_version"),
        "created_at_utc": manifest.get("created_at_utc"),
        # Небольшие секции отдаются сразу: без них обзор бессмыслен.
        "summary": data.get("summary") or {},
        "narrative": data.get("narrative") or [],
        "methodology": data.get("methodology") or {},
        "validation": validation,
        "sections": sections,
        # 🚨 Разная семантика `status` между этапами — не деталь реализации,
        # а источник ложных выводов, если о ней умолчать.
        "status_semantics": {
            "status": "evidence_state Stage 2 (публичный статус доказательности)",
            "measurement_status": "исходный status Stage 2 (статус измерения)",
            "note": (
                "Stage 3 публикует evidence_state под именем status. "
                "Измерительный статус той же пары сохранён как "
                "measurement_status и может отличаться."
            ),
        },
        "withheld_column_prefixes": list(WITHHELD_COLUMN_PREFIXES),
        "withheld_note": (
            "Колонки texture_* и uv_* исключены из публичного отчёта "
            "политикой Stage 3, а не отсутствием данных: они доступны "
            "в метриках пары Stage 2."
        ),
    }


def load_report_section(
    stage3_root: Path, name: str, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """🏭 FACTORY → Одна секция отчёта Stage 3, при необходимости страницей.

    Args:
        name: имя из `REPORT_SECTIONS`; произвольные ключи не принимаются.
        offset, limit: применяются только к секциям-спискам.

    Raises:
        KeyError: секция не входит в нормативный перечень.
        FileNotFoundError: нет вывода Stage 3.
    """
    if name not in REPORT_SECTIONS:
        raise KeyError(f"unknown report section: {name}")
    data = _read_report(stage3_root)
    value = data.get(name)

    total = _section_size(value)
    paged = False
    if isinstance(value, list):
        start = max(0, offset)
        stop = start + max(1, limit)
        payload: Any = value[start:stop]
        paged = len(value) > len(payload)
    else:
        payload = value

    return {
        "schema": REPORT_SCHEMA,
        "not_a_verdict": True,
        "name": name,
        "title": REPORT_SECTIONS[name],
        "present": name in data,
        "total": total,
        "offset": offset if isinstance(value, list) else None,
        "returned": len(payload) if isinstance(payload, list) else None,
        "paged": paged,
        "payload": payload,
    }


def resolve_publication_draft(stage3_root: Path, name: str) -> tuple[Path, str]:
    """Resolve one allowlisted Stage-3 publication draft without path traversal."""
    if not name or Path(name).name != name:
        raise ValueError("invalid publication draft name")
    manifest = _read_report(stage3_root).get("publication_drafts")
    manifest = manifest if isinstance(manifest, dict) else {}
    allowed = {
        str(item.get("name"))
        for item in (manifest.get("files") or [])
        if isinstance(item, dict) and item.get("name")
    }
    if name not in allowed:
        raise KeyError(f"unknown publication draft: {name}")
    root = (stage3_root / str(manifest.get("directory") or "drafts")).resolve()
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise FileNotFoundError(f"publication draft not found: {name}")
    media_type = "application/json" if path.suffix.lower() == ".json" else "text/markdown"
    return path, media_type


def report_available(stage3_root: Path | None) -> bool:
    """🔍 QUERY → Есть ли пригодный вывод Stage 3."""
    if stage3_root is None:
        return False
    return (stage3_root / "report_data.json").is_file()


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "REPORT_SCHEMA",
    "REPORT_SECTIONS",
    "WITHHELD_COLUMN_PREFIXES",
    "load_report_section",
    "load_report_summary",
    "resolve_publication_draft",
    "report_available",
]
