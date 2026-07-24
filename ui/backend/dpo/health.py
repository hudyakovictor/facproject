"""Project health composition for API, CLI, and the future dashboard."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .database import ControlDatabase
from .datasets import DatasetRegistry
from .settings import ProjectSettings
from .storage import StorageManager


@dataclass(frozen=True)
class ProjectHealth:
    status: str
    app6: dict[str, Any]
    storage: dict[str, Any]
    datasets: dict[str, Any]
    database: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def collect_health(settings: ProjectSettings, *, persist: bool = True) -> ProjectHealth:
    registry = DatasetRegistry(settings.datasets)
    datasets = {name: item.to_dict() for name, item in registry.inspect_all().items()}
    manager = StorageManager(
        settings.storage,
        protected_roots=(settings.app6_root, settings.datasets.main_root) + ((settings.datasets.calibration_root,) if settings.datasets.calibration_root else ()),
    )
    storage = manager.check().to_dict()
    app6 = {
        "root": str(settings.app6_root),
        "available": settings.app6_root.is_dir(),
        "python_file_count": sum(1 for _ in settings.app6_root.rglob("*.py")) if settings.app6_root.is_dir() else 0,
        "read_only_observation": True,
    }
    db = ControlDatabase(settings.storage.control_root / "studio.sqlite")
    version = db.migrate()
    if persist:
        db.record_storage(storage)
        for role, payload in datasets.items():
            db.upsert_dataset(role, payload)
    database = {"path": str(db.path), "schema_version": version, **db.counts()}
    critical_ready = bool(app6["available"] and storage["ready"] and datasets["main"]["available"])
    status = "ready" if critical_ready else "configuration_required"
    return ProjectHealth(status, app6, storage, datasets, database)
