"""🏭 FACTORY → Асинхронный JobManager для пакетных операций (`/api/v1/jobs`).

Реализует "extract" (Stage 1 по загруженным фото) и "recompute_metrics"
(Stage 2 по существующему Stage-1 выводу) как настоящие фоновые задачи —
не заглушки. Если веса 3DDFA_V3 или `torch`/`cv2` недоступны в окружении,
задание получает честный терминальный статус `blocked` с причиной, а не
притворяется завершённым: это соответствует `app6/AGENTS.md`
("технический QA без verdict и искусственного overall score").
"""
from __future__ import annotations

import json
import shutil
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .event_log import log_event
from .job_phases import PhaseTracker

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
    phases: PhaseTracker | None = None
    run_id: str | None = None
    profile_id: str | None = None
    _cancel_requested: bool = field(default=False, repr=False)

    def attach_phase_tracker(self, phases: list[tuple[str, str]]) -> PhaseTracker:
        """Прикрепить лестницу фаз. Вызывается runner'ом сразу после старта."""
        if self.phases is None:
            status_holder = {"status": self.status}
            tracker = PhaseTracker(phases, job_status_holder=status_holder)
            self.phases = tracker
        return self.phases

    def log(self, message: str) -> None:
        ts = _utc()
        self.logs.append(f"[{ts}] {message}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": JOB_SCHEMA, "id": self.id, "kind": self.kind, "status": self.status,
            "created_at": self.created_at, "started_at": self.started_at, "finished_at": self.finished_at,
            "progress": {"done": self.progress_done, "total": self.progress_total},
            "logs": self.logs[-200:], "result": self.result, "error": self.error,
            "phases": self.phases.to_list() if self.phases else [],
            "run_id": self.run_id,
            "profile_id": self.profile_id,
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

    def submit(self, kind: str, runner: Callable[[Job], None], *,
               run_id: str | None = None, profile_id: str | None = None) -> str:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        if run_id is not None:
            job.run_id = run_id
        if profile_id is not None:
            job.profile_id = profile_id
        with self._lock:
            self._jobs[job.id] = job

        def _run() -> None:
            job.status = "running"
            job.started_at = _utc()
            try:
                runner(job)
                # Phases can pull the job out of "running" into "failed".
                if job.status == "running":  # runner didn't set a terminal status itself
                    job.status = "complete"
            except _JobBlocked as exc:
                job.status = "blocked"
                job.error = str(exc)
                job.logs.append(f"[{_utc()}] BLOCKED: {exc}")
                if job.phases is not None:
                    job.phases.finish("summary_persist", status="skipped", note=str(exc))
            except Exception as exc:  # noqa: BLE001 - job execution boundary, must not crash the server
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
                job.logs.append(traceback.format_exc())
                log_event("error", "jobs", f"job {job.id} failed: {exc}",
                          stack=traceback.format_exc(), job_id=job.id)
            finally:
                job.finished_at = _utc()
                if job.status not in ("failed", "blocked", "cancelled"):
                    log_event("info", "jobs", f"job {job.id} → {job.status}", job_id=job.id)

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
            raise _JobBlocked("Входная директория не содержит фото (jpg/jpeg/png).")

        phases = [
            ("discovery", "обнаружение фото"),
            ("stage1_init", "инициализация Stage 1"),
            ("stage1_extract", "извлечение кадров"),
            ("manifest_write", "запись манифеста"),
            ("summary_persist", "сохранение сводки"),
        ]
        job.attach_phase_tracker(phases)
        job.phases.start("discovery")

        cfg = Stage1Config(project_root=project_root, device=device)
        engine = Stage1Engine(cfg)

        job.phases.finish("discovery")
        job.phases.start("stage1_init")

        job.phases.finish("stage1_init")
        job.phases.start("stage1_extract")

        processed = 0
        for photo_path in photos[:limit] if limit else photos:
            if job._cancel_requested:
                job.status = "cancelled"
                job.log(f"[{_utc()}] Отмена по запросу пользователя")
                break
            try:
                result = engine.process(photo_path, output_dir)
                job.log(f"[{_utc()}] {photo_path.name}: {result.get('status', 'ok')}")
                processed += 1
                job.progress_done = processed
                job.progress_total = len(photos)
            except Exception as exc:  # noqa: BLE001 - per-photo boundary
                job.log(f"[{_utc()}] {photo_path.name}: ошибка {exc}")

        job.phases.finish("stage1_extract")
        job.phases.start("manifest_write")

        job.phases.finish("manifest_write")
        job.phases.start("summary_persist")

        job.result = {"processed": processed, "total": len(photos), "output_dir": str(output_dir)}
        job.phases.finish("summary_persist")

    return _extract_runner


def make_recompute_metrics_runner(stage1_dir: Path, output_dir: Path, project_root: Path,
                          device: str = "auto") -> Callable[[Job], None]:
    """🏭 FACTORY → Runner пересчёта метрик Stage 2 поверх готового Stage 1."""

    def _recompute_runner(job: Job) -> None:
        missing = _check_stage1_dependencies()
        if missing:
            raise _JobBlocked(
                "Stage 2 recompute недоступен: " + ", ".join(missing) +
                ". Установите torch и cv2."
            )

        from app6.stage2.loaders import load_stage1_manifest
        from app6.stage2.engine import Stage2Engine

        job.phases = PhaseTracker([
            ("load_manifest", "загрузка манифеста Stage 1"),
            ("stage2_run", "запуск Stage 2"),
            ("summary_persist", "сохранение результатов"),
        ], job_status_holder={"status": job.status})
        job.phases.start("load_manifest")

        manifest = load_stage1_manifest(stage1_dir)
        job.phases.finish("load_manifest")
        job.phases.start("stage2_run")

        engine = Stage2Engine(project_root=project_root, device=device)
        result = engine.run(manifest, output_dir)

        job.phases.finish("stage2_run")
        job.phases.start("summary_persist")

        job.result = result
        job.phases.finish("summary_persist")

    return _recompute_runner


def make_recompute_profile_runner(stage1_dir: Path, output_dir: Path, project_root: Path,
                                   profile_id: str, profile: dict) -> Callable[[Job], None]:
    """🏭 FACTORY → Runner пересчёта с конкретным профилем анализа."""

    def _runner(job: Job) -> None:
        missing = _check_stage1_dependencies()
        if missing:
            raise _JobBlocked("Stage 2 недоступен: " + ", ".join(missing))

        from app6.stage2.loaders import load_stage1_manifest
        from app6.stage2.engine import Stage2Engine

        job.phases = PhaseTracker([
            ("load_manifest", "загрузка манифеста Stage 1"),
            ("stage2_run", "запуск Stage 2 (профиль)"),
            ("summary_persist", "сохранение результатов"),
        ], job_status_holder={"status": job.status})
        job.phases.start("load_manifest")

        manifest = load_stage1_manifest(stage1_dir)
        job.phases.finish("load_manifest")
        job.phases.start("stage2_run")

        engine = Stage2Engine(project_root=project_root, device="auto", profile=profile)
        result = engine.run(manifest, output_dir)

        job.phases.finish("stage2_run")
        job.phases.start("summary_persist")

        job.result = result
        job.phases.finish("summary_persist")

    return _runner




def make_analysis_runner(stage1_root: Path, calibration_root: Path, profile_id: str,
                         selection_manifest: Path, run_root: Path) -> Callable[[Job], None]:
    """Run Stage 2 and Stage 3 from one frozen profile selection.

    🧭 Отслеживает четыре явных фазы через ``Job.attach_phase_tracker``:
    ``selection_load`` → ``stage2`` → ``stage3`` → ``summary_persist``.
    Внешний API/UI получает подробный прогресс через ``GET /api/v1/jobs/{job_id}``.
    """

    def _analysis_runner(job: Job) -> None:
        from .job_phases import PROFILE_ANALYSIS_PHASES

        phases = job.attach_phase_tracker(list(PROFILE_ANALYSIS_PHASES))
        phases.start("selection_load")
        job.progress_total = 2

        if not (stage1_root / "main_timeline.csv").is_file():
            phases.finish("selection_load", status="blocked", note="Stage 1 не настроен")
            raise _JobBlocked("готовый Stage 1 недоступен")
        if not selection_manifest.is_file():
            phases.finish("selection_load", status="blocked", note="нет selection_manifest")
            raise _JobBlocked("профиль не имеет замороженной выборки")
        try:
            payload = json.loads(selection_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            phases.finish("selection_load", status="failed", note=str(exc))
            raise _JobBlocked(f"не удалось разобрать selection_manifest: {exc}") from exc
        if payload.get("immutable_stage1") is not True:
            phases.finish("selection_load", status="failed", note="манифест не заморожен")
            raise _JobBlocked("выборка профиля не заморожена")
        included = payload.get("included_ids")
        if not isinstance(included, list) or not included:
            phases.finish("selection_load", status="failed", note="пустая выборка")
            raise _JobBlocked("в замороженной выборке нет фотографий")

        run_root.mkdir(parents=True, exist_ok=False)
        snapshot = run_root / "selection_manifest.snapshot.json"
        shutil.copy2(selection_manifest, snapshot)
        stage2_output = run_root / "stage2"
        stage3_output = run_root / "stage3"
        job.log(f"Профиль {profile_id}: {len(included)} фотографий загружено, копия манифеста → {snapshot.name}")
        phases.finish("selection_load", status="complete", note=f"{len(included)} фото · копия манифеста сохранена")
        if job._cancel_requested:
            job.status = "cancelled"
            phases.finish("stage2", status="skipped"); phases.finish("stage3", status="skipped"); phases.finish("summary_persist", status="skipped")
            return

        from app6.stage1.utils import atomic_json, digest_file
        from app6.stage2 import Stage2Config, Stage2Engine
        from app6.stage3 import Stage3Config, Stage3Engine

        phases.start("stage2")
        job.progress_done = 1
        try:
            cfg2 = Stage2Config(
                project_root=stage1_root.parent.parent,
                calibration_root=calibration_root,
                device="auto",
            )
            engine2 = Stage2Engine(cfg2)
            manifest = engine2.load_stage1(stage1_root)
            # filter to included ids only
            manifest.photos = [p for p in manifest.photos if p.photo_id in included]
            result2 = engine2.run(manifest, stage2_output)
            job.log(f"Stage 2 завершён: {result2.get('pairs_processed', 0)} пар")
        except Exception as exc:  # noqa: BLE001
            phases.finish("stage2", status="failed", note=str(exc))
            raise
        phases.finish("stage2", status="complete")

        if job._cancel_requested:
            job.status = "cancelled"
            phases.finish("stage3", status="skipped"); phases.finish("summary_persist", status="skipped")
            return

        phases.start("stage3")
        try:
            cfg3 = Stage3Config(
                project_root=stage1_root.parent.parent,
                calibration_root=calibration_root,
            )
            engine3 = Stage3Engine(cfg3)
            result3 = engine3.run(stage2_output, stage3_output)
            job.log(f"Stage 3 завершён: отчёт → {stage3_output}")
        except Exception as exc:  # noqa: BLE001
            phases.finish("stage3", status="failed", note=str(exc))
            raise
        phases.finish("stage3", status="complete")

        phases.start("summary_persist")
        summary = {
            "profile_id": profile_id,
            "stage1_root": str(stage1_root),
            "stage2_output": str(stage2_output),
            "stage3_output": str(stage3_output),
            "photos_included": len(included),
            "completed_at": _utc(),
        }
        (run_root / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        job.result = {"run_id": run_root.name, "stage2": str(stage2_output), "stage3": str(stage3_output)}
        phases.finish("summary_persist", status="complete", note="run_summary.json сохранён")

    return _analysis_runner


job_manager = JobManager()
