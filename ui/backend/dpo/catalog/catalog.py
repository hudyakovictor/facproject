"""Journalist-first function catalog composed from code, status and tests."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import yaml

from dpo.indexer.project_index import ProjectIndex
from .status_indexer import StatusEntry
from .test_indexer import TestBinding

MODULE_MEANING = {
 "geometry": ("Геометрия лица", "Ошибка искажает сравнение формы и влияние ракурса."),
 "reconstruction": ("Восстановление 3D-модели", "Ошибка делает 3D-геометрию недостоверной."),
 "engine": ("Управление этапом pipeline", "Ошибка может остановить этап или дать неполный результат."),
 "evidence": ("Границы доказательного вывода", "Ошибка может привести к чрезмерно уверенному заключению."),
 "calibration": ("Калибровка по контрольным данным", "Ошибка смешивает различия людей с шумом метода."),
 "loaders": ("Загрузка проверенных данных", "Ошибка может подать в анализ неверные или неполные данные."),
 "quality": ("Контроль качества", "Ошибка пропускает непригодную фотографию или пару."),
 "report": ("Подготовка отчёта", "Ошибка искажает объяснение результатов журналисту."),
}

@dataclass(frozen=True)
class CatalogEntry:
    id: str; title: str; description: str; why_important: str; failure_impact: str
    technical_name: str; source_path: str; line_start: int; line_end: int
    stage: str; criticality: str; status: str; blocker: str | None
    test_count: int; binding_confidence: tuple[str, ...]; description_source: str; task_priority: str | None
    def to_dict(self) -> dict[str, Any]: return asdict(self)


def _stage(source: str) -> str:
    return next((part for part in source.split("/") if part in {"stage1", "stage2", "stage2b", "stage3", "test_module"}), "shared")


def _module_copy(source: str) -> tuple[str, str]:
    stem = Path(source).stem
    for key, copy in MODULE_MEANING.items():
        if key in stem: return copy
    return ("Внутренняя операция pipeline", "Ошибка может изменить промежуточные данные или нарушить воспроизводимость.")


def build_catalog(project: ProjectIndex, statuses: list[StatusEntry], bindings: list[TestBinding], overrides_path: str | Path | None = None) -> list[CatalogEntry]:
    status_by_id = {s.target_id: s for s in statuses if s.target_id}
    bindings_by_id: dict[str, list[TestBinding]] = {}
    for binding in bindings: bindings_by_id.setdefault(binding.function_id, []).append(binding)
    overrides: dict[str, dict] = {}
    if overrides_path and Path(overrides_path).exists():
        payload = yaml.safe_load(Path(overrides_path).read_text(encoding="utf-8")) or {}
        overrides = payload.get("functions", {})
    modules = {m.id: m for m in project.modules}
    result: list[CatalogEntry] = []
    for f in project.functions:
        module = modules[f.module_id]
        meaning, impact = _module_copy(module.source_path)
        stage = _stage(module.source_path)
        critical = "critical" if stage in {"stage1", "stage2", "stage3"} and any(x in module.source_path for x in ("engine.py", "geometry.py", "reconstruction.py", "core.py", "evidence.py", "calibration")) else "normal"
        override = overrides.get(f.id, {})
        human = f.technical_name.strip("_").replace("_", " ") or f.technical_name
        doc = (f.docstring or "").strip().split("\n")[0]
        description = override.get("description") or doc or f"Выполняет операцию «{human}» в разделе «{meaning.lower()}»."
        source_kind = "manual" if override else "docstring" if doc else "generated_fallback"
        status = status_by_id.get(f.id)
        linked = bindings_by_id.get(f.id, [])
        result.append(CatalogEntry(f.id, override.get("title") or human.capitalize(), description, override.get("why_important") or meaning, override.get("failure_impact") or impact, f.technical_name, module.source_path, f.line_start, f.line_end, stage, override.get("criticality") or critical, status.status if status else "discovered", status.blocker if status else None, len({x.test_id for x in linked}), tuple(sorted({x.confidence for x in linked})), source_kind, "P2" if source_kind == "generated_fallback" else None))
    return sorted(result, key=lambda x: (x.stage, x.source_path, x.line_start))
