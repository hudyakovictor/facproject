"""Phase-aware execution for background jobs (`/api/v1/jobs`).

The Job dataclass tracks coarse-grained ``progress_done/progress_total`` plus
``logs``; here we add an optional list of explicit phases, each with its own
progress and timeline, so the UI can render per-stage progress (Stage 2 → Stage 3
profile runs in particular).

🚨 WARNING: this module is intentionally server-side only and never imports
torch/cv2; importing it must remain cheap at process boot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Iterable


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class JobPhase:
    name: str
    title: str
    status: str = "pending"  # pending | running | complete | failed | blocked | skipped
    started_at: str | None = None
    finished_at: str | None = None
    progress_done: int = 0
    progress_total: int = 0
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": {"done": self.progress_done, "total": self.progress_total},
            "note": self.note,
        }


class PhaseTracker:
    """🧭 Phase-aware bookkeeping attached to a single Job instance.

    The tracker is intentionally allocation-light: phases are dicts in a list,
    guarded by a Lock so the runner thread and any concurrent ``GET /jobs/{id}``
    requests cannot tear the sequence.
    """

    def __init__(self, phases: Iterable[tuple[str, str]], *, job_status_holder: dict[str, str] | None = None) -> None:
        self._lock = Lock()
        self._phases: list[JobPhase] = [
            JobPhase(name=name, title=title) for name, title in phases
        ]
        # When the tracker is told a phase ended in ``failed`` it can pull the
        # attached job out of "running" via this dict (set by the runner).
        self._job_status_holder = job_status_holder or {}

    @property
    def phases(self) -> list[JobPhase]:
        with self._lock:
            return list(self._phases)

    def start(self, name: str, *, note: str | None = None, total: int = 0) -> None:
        with self._lock:
            phase = self._find(name)
            if phase is None:
                raise KeyError(f"unknown phase: {name}")
            if phase.status == "pending":
                phase.status = "running"
                phase.started_at = _utc()
                phase.progress_total = max(int(total), phase.progress_total, 0)
                phase.note = note
            elif phase.status == "running":
                phase.progress_total = max(int(total), phase.progress_total, 0)
                if note is not None:
                    phase.note = note

    def update(self, name: str, *, done: int | None = None, total: int | None = None, note: str | None = None) -> None:
        with self._lock:
            phase = self._find(name)
            if phase is None:
                return
            if phase.status == "pending":
                phase.status = "running"
                phase.started_at = _utc()
            if done is not None:
                phase.progress_done = max(0, int(done))
            if total is not None and int(total) >= phase.progress_done:
                phase.progress_total = max(int(total), phase.progress_done)
            if note is not None:
                phase.note = note

    def finish(self, name: str, *, status: str = "complete", note: str | None = None) -> None:
        with self._lock:
            phase = self._find(name)
            if phase is None:
                return
            phase.status = status
            phase.finished_at = _utc()
            if phase.progress_total == 0:
                phase.progress_total = max(phase.progress_done, 1)
            phase.progress_done = max(phase.progress_done, phase.progress_total)
            if note is not None:
                phase.note = note
            if status == "failed":
                self._job_status_holder["status"] = "failed"

    def skip(self, name: str, *, note: str | None = None) -> None:
        self.finish(name, status="skipped", note=note)

    def to_list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [phase.to_dict() for phase in self._phases]

    def _find(self, name: str) -> JobPhase | None:
        for phase in self._phases:
            if phase.name == name:
                return phase
        return None


#: Phase ladder used by ``make_analysis_runner`` (Stage 2 + Stage 3 profile run).
#: Names must remain stable: they are referenced from logs and from the UI.
PROFILE_ANALYSIS_PHASES: tuple[tuple[str, str], ...] = (
    ("selection_load", "Загрузка замороженной выборки профиля"),
    ("stage2", "Stage 2: попарный анализ включённых фото"),
    ("stage3", "Stage 3: валидация и публичный отчёт"),
    ("summary_persist", "Сохранение сводки прогона"),
)


__all__ = [
    "JobPhase",
    "PhaseTracker",
    "PROFILE_ANALYSIS_PHASES",
]
