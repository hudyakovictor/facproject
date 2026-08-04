"""🏭 FACTORY → Асинхронный JobManager для пакетных операций (`/api/v1/jobs`).

Реализует "extract" (Stage 1 по загруженным фото) и "recompute_metrics"
(Stage 2 по существующему Stage-1 выводу) как настоящие фоновые задачи —
не заглушки. Если веса 3DDFA_V3 или `torch`/`cv2` недоступны в окружении,
задание получает честный терминальный статус `blocked` с причиной, а не
притворяется завершённым: это соответствует `app6/AGENTS.md`
("технический QA без verdict и искусственного overall score").
"""
from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

JOB_SCHEMA = "deeputin-api-job-v1.0"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"  # queued | running | complete | blocked | failed | cancelled
    created_at: str = field(default_factory=_utc)
    started_at: str | None = None
    finished_at: str | None = None
    progress_done: int = 0
    progress_total: int = 0
    logs: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    _cancel_requested: bool = field(default=False, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": JOB_SCHEMA, "id": self.id, "kind": self.kind, "status": self.status,
            "created_at": self.created_at, "started_at": self.started_at, "finished_at": self.finished_at,
            "progress": {"done": self.progress_done, "total": self.progress_total},
            "logs": self.logs[-200:], "result": self.result, "error": self.error,
        }


class JobManager:
    """🎯 CRITICAL → Потокобезопасный реестр фоновых заданий процесса API.

    🚨 WARNING: заданиями управляет один процесс в памяти; при перезапуске
    сервера история заданий не сохраняется. Для forensic-воспроизводимости
    источником истины остаются артефакты Stage 1/2 на диске
    (`analysis_manifest.json`, `info.json` и т.д.), а не этот реестр.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [job.to_dict() for job in sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)]

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status not in ("queued", "running"):
                return False
            job._cancel_requested = True
            return True

    def submit(self, kind: str, runner: Callable[[Job], None]) -> str:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job

        def _run() -> None:
            job.status = "running"
            job.started_at = _utc()
            try:
                runner(job)
                if job.status == "running":  # runner didn't set a terminal status itself
                    job.status = "complete"
            except _JobBlocked as exc:
                job.status = "blocked"
                job.error = str(exc)
                job.logs.append(f"BLOCKED: {exc}")
            except Exception as exc:  # noqa: BLE001 - job execution boundary, must not crash the server
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
                job.logs.append(traceback.format_exc())
            finally:
                job.finished_at = _utc()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return job.id


class _JobBlocked(RuntimeError):
    """Задание не может выполниться из-за отсутствующей внешней зависимости."""


def _check_stage1_dependencies() -> list[str]:
    """🚧 GATE → Список отсутствующих зависимостей Stage 1, если есть."""
    missing = []
    for module_name in ("torch", "cv2"):
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)
    return missing


def make_extract_runner(input_dir: Path, output_dir: Path, project_root: Path,
                        device: str = "auto", limit: int = 0, sampling_mode: str = "full",
                        per_year: int = 5) -> Callable[[Job], None]:
    """🏭 FACTORY → Runner Stage 1 extract job для `JobManager.submit`."""

    def _extract_runner(job: Job) -> None:
        missing = _check_stage1_dependencies()
        assets_dir = project_root / "assets"
        required_weights = [
            "face_model.npy", "net_recon.pth", "large_base_net.pth",
            "retinaface_resnet50_2020-07-20_old_torch.pth", "similarity_Lm3D_all.mat",
        ]
        missing_weights = [w for w in required_weights if not (assets_dir / w).is_file()]
        if missing or missing_weights:
            reasons = []
            if missing:
                reasons.append(f"отсутствуют Python-пакеты: {', '.join(missing)}")
            if missing_weights:
                reasons.append(f"отсутствуют веса модели: {', '.join(missing_weights)}")
            raise _JobBlocked(
                "Stage 1 extract job недоступен в этом окружении. " + "; ".join(reasons) +
                ". См. app6/scripts/fetch_external_assets.py и app6/README.md."
            )

        from app6.stage1.config import Stage1Config
        from app6.stage1.engine import Stage1Engine

        photos = sorted(
            p for p in input_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png") and not p.name.startswith("._")
        )
        # P3.14 (DEV_FIX_TZ): пустой вход — это blocked, а не "успешно
        # обработано 0 фото". Раньше задание завершалось как complete и
        # создавало ложное впечатление выполненного извлечения.
        if not photos:
            raise _JobBlocked(
                f"нет входных изображений (.jpg/.jpeg/.png) в {input_dir}; "
                "извлечение не запускалось"
            )
        cfg = Stage1Config(project_root=project_root, input_dir=input_dir, output_dir=output_dir,
                           device=device, overwrite=True, limit=limit, sampling_mode=sampling_mode, per_year=per_year)
        engine = Stage1Engine(cfg)
        # `Stage1Engine.run()` не только обрабатывает отдельные кадры: он
        # финализирует main_index.csv, main_timeline.csv, provenance и manifest.
        # Вызов приватного `_one()` здесь оставлял API-job в статусе complete,
        # но делал результат непригодным для UI и Stage 2.
        selected = engine.photos[:limit] if limit > 0 else engine.photos
        job.progress_total = len(selected)
        job.logs.append(f"найдено {len(selected)} фото в {input_dir}")
        if job._cancel_requested:
            job.status = "cancelled"
            job.logs.append("отменено до запуска извлечения")
            return
        manifest = engine.run()
        job.progress_done = int(manifest.get("input_count", len(selected)))
        job.result = {
            "ok": int(manifest.get("success_count", 0)),
            "fail": int(manifest.get("error_count", 0)),
            "total": int(manifest.get("input_count", len(selected))),
            "output_dir": str(output_dir),
            "manifest": manifest,
        }
        if manifest.get("error_count"):
            job.logs.append(f"Stage 1 завершён с ошибками: {manifest['error_count']}")

    return _extract_runner


def make_recompute_metrics_runner(stage1_root: Path, calibration_root: Path,
                                  output_dir: Path) -> Callable[[Job], None]:
    """🏭 FACTORY → Runner Stage 2 recompute job для `JobManager.submit`."""

    def _recompute_runner(job: Job) -> None:
        if not (stage1_root / "main_timeline.csv").is_file():
            raise _JobBlocked(f"нет валидного вывода Stage 1 в {stage1_root} (main_timeline.csv отсутствует)")
        from app6.stage2 import Stage2Config, Stage2Engine  # local import: heavy deps only if reachable

        job.logs.append(f"запуск Stage 2: stage1={stage1_root} calibration={calibration_root}")
        job.progress_total = 1
        engine = Stage2Engine(Stage2Config(stage1_root=stage1_root, calibration_root=calibration_root,
                                           output_dir=output_dir, overwrite=True))
        manifest = engine.run()
        job.progress_done = 1
        job.result = {"manifest": manifest if isinstance(manifest, dict) else str(manifest),
                     "output_dir": str(output_dir)}

    return _recompute_runner
