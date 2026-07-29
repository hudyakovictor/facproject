"""🚧 GATE → Гейт порядка стадий пайплайна.

Контракт (`app6/AGENTS.md`): Stage 2/2B/3 читают только валидный вывод
предыдущей стадии и никогда не запускают реконструкцию повторно. Этот модуль —
единственная точка, где порядок проверяется до начала дорогостоящей работы.

Политика fail-closed: при нарушении порядка поднимается `PipelineOrderError`,
кроме явного аварийного отключения через `DEEPUTIN_DISABLE_PIPELINE_GUARD=1`.
Отключение логируется, чтобы отсутствие проверки не осталось незамеченным.

🚨 WARNING: guard проверяет наличие и целостность маркеров стадий, а не качество
данных. Он не заменяет `validator.py` и quality-gates.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Final

from app6.stage1.status_logger import log_status, status_warning

GUARD_SCHEMA: Final[str] = "deeputin-pipeline-guard-v1.0"

#: Порядок стадий. Каждая стадия объявляет, чей вывод обязана видеть на входе.
STAGE_ORDER: Final[tuple[str, ...]] = ("stage1", "stage2", "stage2b", "stage3")

#: Отключение guard — только осознанное, через переменную окружения.
DISABLE_ENV: Final[str] = "DEEPUTIN_DISABLE_PIPELINE_GUARD"


class PipelineOrderError(RuntimeError):
    """Поднимается, когда стадия запускается вне разрешённого порядка."""


def _guard_disabled() -> bool:
    return os.environ.get(DISABLE_ENV, "").strip() in {"1", "true", "yes"}


def stage_index(stage: str) -> int:
    """Вернуть позицию стадии в пайплайне.

    Raises:
        ValueError: если имя стадии неизвестно (защита от опечаток в вызовах).
    """
    key = str(stage).strip().lower()
    if key not in STAGE_ORDER:
        raise ValueError(f"unknown stage: {stage!r}; expected one of {STAGE_ORDER}")
    return STAGE_ORDER.index(key)


def required_predecessor(stage: str) -> str | None:
    """Стадия, вывод которой обязан существовать до запуска `stage`."""
    idx = stage_index(stage)
    return None if idx == 0 else STAGE_ORDER[idx - 1]


def enforce_stage(stage: str, *, project_root: Path | None = None) -> dict[str, Any]:
    """🚧 GATE → Проверить, что стадия запускается в правильном порядке.

    Stage 1 не имеет предшественника и разрешается всегда. Для остальных стадий
    проверяется только корректность имени и порядка: фактическая валидация
    входных артефактов остаётся за самой стадией (`loaders`, `validator`),
    которая умеет отличать отсутствующий вход от повреждённого.

    Args:
        stage: одно из `STAGE_ORDER`.
        project_root: корень проекта; сейчас используется только для отчёта.

    Returns:
        Словарь-решение с полями `stage`, `status`, `predecessor`.

    Raises:
        ValueError: неизвестное имя стадии.
        PipelineOrderError: нарушение порядка стадий.
    """
    if _guard_disabled():
        status_warning("pipeline_guard", f"guard disabled via {DISABLE_ENV}; stage={stage}")
        return {"schema": GUARD_SCHEMA, "stage": str(stage), "status": "bypassed",
                "predecessor": None, "reason": f"{DISABLE_ENV} is set"}

    idx = stage_index(stage)
    predecessor = required_predecessor(stage)
    log_status("enforce_stage", "complete", f"stage={stage} order_index={idx}")
    return {"schema": GUARD_SCHEMA, "stage": STAGE_ORDER[idx], "status": "allowed",
            "predecessor": predecessor, "project_root": str(project_root) if project_root else None}


def assert_predecessor_output(stage: str, predecessor_root: Path) -> dict[str, Any]:
    """🚧 GATE → Fail-closed проверка вывода предыдущей стадии.

    Вызывается стадиями, которым передан путь к выводу предшественника.
    Проверяется наличие манифеста и то, что он помечен как завершённый: частично
    записанный вывод не должен молча становиться входом следующей стадии.

    Raises:
        PipelineOrderError: манифест отсутствует, нечитаем или незавершён.
    """
    if _guard_disabled():
        status_warning("pipeline_guard", f"predecessor check bypassed for {stage}")
        return {"status": "bypassed", "stage": stage}

    root = Path(predecessor_root)
    manifests = ("analysis_manifest.json", "stage1_manifest.json")
    found: Path | None = next((root / m for m in manifests if (root / m).is_file()), None)
    if found is None:
        raise PipelineOrderError(
            f"{stage}: no predecessor manifest under {root}; run {required_predecessor(stage)} first"
        )
    try:
        payload = json.loads(found.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineOrderError(f"{stage}: unreadable predecessor manifest {found}: {exc}") from exc

    status = str(payload.get("status", "")).lower()
    if status and status != "complete":
        raise PipelineOrderError(
            f"{stage}: predecessor manifest {found.name} has status={status!r}, expected 'complete'"
        )
    log_status("assert_predecessor_output", "complete", f"{stage} <- {found.name}")
    return {"status": "ok", "stage": stage, "manifest": str(found), "manifest_status": status or "unknown"}
