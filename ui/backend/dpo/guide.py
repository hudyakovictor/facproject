"""Deterministic guided-workflow state for non-technical operators.

The guide is intentionally fail-closed: a later step is never presented as
available until every earlier gate has objective evidence of completion.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class GuideStep:
    id: str
    phase: str
    title: str
    purpose: str
    status: str
    action: str
    action_label: str | None
    runner_id: str | None
    blocking_reason: str | None
    evidence: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run_succeeded(runs: Iterable[Any], runner_id: str) -> tuple[bool, str | None]:
    candidates = []
    for item in runs:
        payload = item.to_dict() if hasattr(item, "to_dict") else dict(item)
        if payload.get("runner_id") == runner_id:
            candidates.append(payload)
    candidates.sort(key=lambda x: str(x.get("finished_at") or x.get("created_at") or ""), reverse=True)
    if not candidates:
        return False, None
    latest = candidates[0]
    return latest.get("status") == "succeeded", str(latest.get("id") or "")


def build_guide_status(health: dict[str, Any], runs: Iterable[Any], capabilities: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return ordered steps and the single current gate.

    Product surfaces that do not exist yet are explicit development gates,
    rather than pretending the workstation is ready or letting the operator
    configure scientific parameters prematurely.
    """
    backend_ok = bool(health)
    app6_ok = bool(health.get("app6", {}).get("available"))
    storage_ok = bool(health.get("storage", {}).get("ready"))
    main_ok = bool(health.get("datasets", {}).get("main", {}).get("available"))
    calibration_ok = bool(health.get("datasets", {}).get("calibration", {}).get("available"))
    ui_ok, ui_run = _run_succeeded(runs, "ui-backend-regression")
    app6_tests_ok, app6_run = _run_succeeded(runs, "app6-regression")
    capability_state = capabilities or {}
    photo_count = int(capability_state.get("photo_index_count") or 0)
    photo_index_ok = photo_count > 0

    definitions = [
        ("system", "setup", "Проверка приложения", "Убедиться, что backend отвечает и app6 доступен только для чтения.", backend_ok and app6_ok, "refresh", "Проверить снова", None, None if backend_ok and app6_ok else "Backend или каталог app6 недоступен.", "health.app6.available" if app6_ok else None),
        ("storage", "setup", "Безопасное хранилище", "Подтвердить SDCARD и запрет тяжёлого fallback на системный диск.", storage_ok, "refresh", "Проверить диск", None, None if storage_ok else (health.get("storage", {}).get("reasons") or ["SDCARD не готова."])[0], health.get("storage", {}).get("heavy_root") if storage_ok else None),
        ("main-dataset", "setup", "Основной фотоархив", "Проверить доступность исходных фотографий без изменения файлов.", main_ok, "refresh", "Пересканировать", None, None if main_ok else (health.get("datasets", {}).get("main", {}).get("reasons") or ["Основной датасет не найден."])[0], f"{health.get('datasets', {}).get('main', {}).get('file_count', 0)} файлов" if main_ok else None),
        ("calibration-dataset", "setup", "Калибровка · 7 лиц", "Проверить контрольный датасет до любых научных настроек.", calibration_ok, "refresh", "Пересканировать", None, None if calibration_ok else (health.get("datasets", {}).get("calibration", {}).get("reasons") or ["Калибровочный датасет не настроен."])[0], f"{health.get('datasets', {}).get('calibration', {}).get('file_count', 0)} файлов" if calibration_ok else None),
        ("backend-tests", "validation", "Проверка управляющего backend", "Исключить ошибки control plane перед запуском app6.", ui_ok, "run", "Запустить backend-тесты", "ui-backend-regression", None if ui_ok else "Нужен успешный свежий прогон backend-тестов.", f"успешный run {ui_run}" if ui_ok else None),
        ("app6-tests", "validation", "Регрессия app6", "Зафиксировать зелёную исходную точку перед дальнейшей разработкой.", app6_tests_ok, "run", "Запустить полную проверку app6", "app6-regression", None if app6_tests_ok else "Нужен успешный прогон всех regression-тестов app6.", f"успешный run {app6_run}" if app6_tests_ok else None),
        ("photo-index", "implementation", "Индекс фотографий", "Подключить даты, pose hints и файловый статус к UI без изменения исходных фото.", photo_index_ok, "development", "Открыть техническое задание", None, None if photo_index_ok else "Photo Index не нашёл ни одной фотографии. Проверьте структуру архива и строгий формат дат YYYY_MM_DD.", f"{photo_count} фотографий в read-only индексе" if photo_index_ok else None),
        ("timeline", "implementation", "Настоящая хронология", "Построить девять дорожек и реальные временные ряды метрик.", False, "development", "Открыть ТЗ хронологии", None, "Read-only точки фото готовы; ещё нет Stage-1 pose, quality и metric series.", None),
        ("pair-workbench", "implementation", "Сравнение A/B", "Реализовать raw/corrected/residual и калибровочную поправку.", False, "development", "Открыть ТЗ A/B", None, "Сначала завершите хронологию и photo contracts.", None),
        ("calibration-lab", "implementation", "Calibration Lab", "Проверить девять pose bins, coverage и noise references.", False, "development", "Открыть ТЗ калибровки", None, "Сначала завершите A/B contracts.", None),
        ("analysis-unlock", "release", "Разблокировать исследование", "Открыть параметры только после проверенного end-to-end пути.", False, "locked", None, None, "Требуются photo index, timeline, A/B и calibration gates.", None),
    ]

    steps: list[GuideStep] = []
    previous_complete = True
    current_id: str | None = None
    for step_id, phase, title, purpose, complete, action, action_label, runner_id, reason, evidence in definitions:
        if complete and previous_complete:
            status = "complete"
        elif previous_complete and current_id is None:
            status = "current"
            current_id = step_id
        else:
            status = "locked"
        steps.append(GuideStep(step_id, phase, title, purpose, status, action if status == "current" else "none", action_label if status == "current" else None, runner_id if status == "current" else None, reason, evidence))
        previous_complete = previous_complete and complete

    completed = sum(step.status == "complete" for step in steps)
    foundation_complete = all(step.status == "complete" for step in steps[:6])
    return {
        "schema": "dpo-guided-workflow-v1",
        "mode": "guided",
        "current_step_id": current_id,
        "completed": completed,
        "total": len(steps),
        "foundation_complete": foundation_complete,
        "analysis_unlocked": all(step.status == "complete" for step in steps),
        "steps": [step.to_dict() for step in steps],
    }
