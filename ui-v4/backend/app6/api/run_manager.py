"""Stage 2 Run Manager (Iteration 05).

Gives the UI the ability to run Stage 2 (and Stage 2B) from a frozen Analysis
Profile — with preflight estimation, background execution, progress, logs,
cancellation, multi-run coexistence and explicit archiving.

Run layout under ``<storage>/stage2/runs/``:

    run_YYYYMMDD_HHMMSS/
      run_config.json          — frozen config: profile, selection, engine knobs
      selection_manifest.json  — frozen selection snapshot
      status.json              — live status (queued/running/complete/failed/cancelled)
      logs/run.log             — engine log
      analysis_manifest.json   — written by Stage 2 engine
      analysis_validation.json — written by Stage 2 engine
      ...                      — every Stage 2 artifact

Rules:
- Stage 1 and calibration are read-only inputs; a run never writes into them.
- A new run id is unique; existing runs are never overwritten.
- The CLI and the UI produce identical results for the same config (both drive
  ``Stage2Engine(Stage2Config(...))`` with the same parameters).
- The legacy ``<storage>/stage2`` output (pre-run-manager) is registered as a
  read-only "legacy" run and is never modified.
"""
from __future__ import annotations

import json
import shutil
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .runtime_config import RuntimePaths, ensure_runtime_write_dirs, load_runtime_paths
from .event_log import log_event

RUN_MANAGER_SCHEMA = "deeputin-run-manager-v1.0"
RUN_CONFIG_SCHEMA = "deeputin-run-config-v1.0"
RUN_STATUS_SCHEMA = "deeputin-run-status-v1.0"

LEGACY_RUN_ID = "legacy"


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------
def runs_root(paths: RuntimePaths | None = None) -> Path:
    current = paths or load_runtime_paths()
    ensure_runtime_write_dirs(current)
    root = current.stage2_root / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def archive_root(paths: RuntimePaths | None = None) -> Path:
    current = paths or load_runtime_paths()
    ensure_runtime_write_dirs(current)
    root = current.stage2_root / "archive"
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_dir(run_id: str, paths: RuntimePaths | None = None) -> Path:
    root = runs_root(paths)
    directory = (root / run_id).resolve()
    if root.resolve() not in directory.parents:
        raise ValueError(f"invalid run_id: {run_id}")
    return directory


def _next_run_id(paths: RuntimePaths | None = None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"run_{stamp}"
    root = runs_root(paths)
    candidate = base
    counter = 1
    while (root / candidate).exists():
        candidate = f"{base}_{counter:02d}"
        counter += 1
    return candidate


# --------------------------------------------------------------------------
# listing / status
# --------------------------------------------------------------------------
def list_runs(paths: RuntimePaths | None = None) -> list[dict[str, Any]]:
    """All runs, newest first. The legacy Stage-2 output is a read-only entry."""
    current = paths or load_runtime_paths()
    runs: list[dict[str, Any]] = []

    root = current.stage2_root
    if (root / "analysis_manifest.json").is_file() and not (root / "runs").is_dir():
        runs.append(_run_summary(LEGACY_RUN_ID, root, legacy=True))

    runs_dir = root / "runs"
    if runs_dir.is_dir():
        for item in sorted(runs_dir.iterdir(), key=lambda p: p.name, reverse=True):
            if not item.is_dir() or not item.name.startswith("run_"):
                continue
            runs.append(_run_summary(item.name, item, legacy=False))

    runs.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return runs


def _run_summary(run_id: str, directory: Path, legacy: bool) -> dict[str, Any]:
    status = _read_json(directory / "status.json") or _read_json(directory.parent / f"{run_id}.status.json") or {}
    config = _read_json(directory / "run_config.json") or {}
    manifest = _read_json(directory / "analysis_manifest.json")
    validation = _read_json(directory / "analysis_validation.json")
    completed = bool(manifest and manifest.get("status") == "complete" and
                     validation and validation.get("status") == "complete")
    return {
        "schema": RUN_MANAGER_SCHEMA,
        "run_id": run_id,
        "legacy": legacy,
        "label": config.get("label") or run_id,
        "profile_id": config.get("profile_id"),
        "profile_name": config.get("profile_name"),
        "created_at": config.get("created_at") or status.get("created_at"),
        "status": status.get("status") or ("complete" if completed else "unknown"),
        "progress": status.get("progress") or {"done": 0, "total": 0, "phase": ""},
        "started_at": status.get("started_at"),
        "finished_at": status.get("finished_at"),
        "error": status.get("error"),
        "has_manifest": bool(manifest),
        "valid": completed,
        "validation_status": (validation or {}).get("status"),
        "record_count": (manifest or {}).get("main_record_count"),
        "pair_count": (manifest or {}).get("pair_count"),
        "included_count": (config.get("selection") or {}).get("included_count"),
        "directory": str(directory),
    }


def get_run(run_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    if run_id == LEGACY_RUN_ID:
        directory = current.stage2_root
        if not (directory / "analysis_manifest.json").is_file():
            raise FileNotFoundError("legacy Stage 2 output not found")
        summary = _run_summary(LEGACY_RUN_ID, directory, legacy=True)
    else:
        directory = run_dir(run_id, current)
        if not directory.is_dir():
            raise FileNotFoundError(f"run not found: {run_id}")
        summary = _run_summary(run_id, directory, legacy=False)

    status = _read_json(directory / "status.json") or _read_json(directory.parent / f"{run_id}.status.json") or {}
    config = _read_json(directory / "run_config.json") or {}
    log_path = directory / "logs" / "run.log"
    if not log_path.is_file():
        log_path = directory.parent / f"{run_id}.status.log"
    log_tail: list[str] = []
    if log_path.is_file():
        try:
            with log_path.open(encoding="utf-8", errors="replace") as handle:
                log_tail = handle.readlines()[-400:]
        except OSError:
            pass
    artifacts = sorted(
        p.name for p in directory.iterdir()
        if p.is_file() and p.name not in ("status.json", "run_config.json", "selection_manifest.json")
    )
    summary["logs"] = [line.rstrip("\n") for line in log_tail]
    summary["artifacts"] = artifacts
    summary["config"] = config
    summary["selection"] = config.get("selection")
    return summary


# --------------------------------------------------------------------------
# preflight estimation
# --------------------------------------------------------------------------
def preflight_stage2(profile_id: str | None, min_points106: int, min_points134: int,
                     calibration_root: str | None = None,
                     paths: RuntimePaths | None = None) -> dict[str, Any]:
    """Validate inputs and estimate pair counts WITHOUT starting a run."""
    from app6.stage2.loaders import load_calibration, load_main

    current = paths or load_runtime_paths()
    stage1_root = current.stage1_root
    if not (stage1_root / "main_timeline.csv").is_file():
        raise FileNotFoundError(f"Stage 1 not ready: {stage1_root}/main_timeline.csv")

    cal_root = Path(calibration_root) if calibration_root else current.calibration_root

    records = load_main(stage1_root)
    cal = load_calibration(cal_root)
    cal_persons = sorted({record.dataset_id for record in cal})

    selection_ids: set[str] | None = None
    selection: dict[str, Any] | None = None
    if profile_id:
        from .analysis_profiles import _profile_paths  # noqa: PLC2701 - internal reuse
        files = _profile_paths(profile_id, current)
        manifest = _read_json(files["manifest"])
        if not manifest:
            from .analysis_profiles import freeze_selection_manifest
            from .stage1_timeline import build_stage1_inventory
            inventory = build_stage1_inventory(stage1_root)
            manifest = freeze_selection_manifest(profile_id, inventory["photos"], paths=current, stage1_root=str(stage1_root))["manifest"]
        included = manifest.get("included_ids")
        if not isinstance(included, list):
            raise ValueError(f"profile {profile_id} has no valid included_ids in selection manifest")
        selection_ids = set(str(item) for item in included)
        selection = {
            "profile_id": profile_id,
            "profile_name": manifest.get("profile_name") or profile_id,
            "included_count": len(selection_ids),
            "excluded_count": manifest.get("excluded_count", 0),
        }

    work = [r for r in records if selection_ids is None or r.record_id in selection_ids]
    per_bin: dict[str, dict[str, int]] = {}
    for record in work:
        entry = per_bin.setdefault(record.pose_bin, {"records": 0, "adjacent_pairs": 0, "baseline_pairs": 0})
        entry["records"] += 1
    for pose, entry in per_bin.items():
        n = entry["records"]
        entry["adjacent_pairs"] = max(0, n - 1)
        entry["baseline_pairs"] = max(0, n - 2) if n > 2 else 0
    total_adjacent = sum(entry["adjacent_pairs"] for entry in per_bin.values())
    total_baseline = sum(entry["baseline_pairs"] for entry in per_bin.values())
    cal_bins = sorted({record.pose_bin for record in cal})
    return {
        "schema": RUN_MANAGER_SCHEMA,
        "ready": True,
        "stage1": {
            "root": str(stage1_root),
            "record_count": len(records),
            "selected_count": len(work),
            "per_bin": per_bin,
        },
        "calibration": {
            "root": str(cal_root),
            "record_count": len(cal),
            "person_count": len(cal_persons),
            "persons": cal_persons,
            "pose_bins": cal_bins,
        },
        "pairs": {
            "adjacent": total_adjacent,
            "baseline": total_baseline,
            "total_estimate": total_adjacent + total_baseline,
        },
        "selection": selection,
        "min_points106": min_points106,
        "min_points134": min_points134,
        "not_a_verdict": True,
    }


# --------------------------------------------------------------------------
# execution
# --------------------------------------------------------------------------
@dataclass
class RunHandle:
    run_id: str
    directory: Path
    status_path: Path  # live status: sibling of the run dir (outside engine output)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None

    def finalize_metadata(self, config: dict[str, Any], manifest: dict[str, Any] | None) -> None:
        """Copy live status + config into the run dir AFTER the engine finished.

        The engine refuses non-empty output dirs (overwrite=False) and wipes
        them on overwrite=True, so run metadata must not sit in the run dir
        while the engine is running. Once the engine is done, the run dir
        becomes the immutable frozen record.
        """
        status = _read_json(self.status_path) or {}
        if manifest is not None:
            _atomic_json(self.directory / "selection_manifest.json", manifest)
        _atomic_json(self.directory / "run_config.json", config)
        _atomic_json(self.directory / "status.json", status)
        log_path = self.directory / "logs" / "run.log"
        live_log = self.status_path.with_suffix(".log")
        if live_log.is_file() and not log_path.is_file():
            log_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(live_log, log_path)
            except OSError:
                pass

    def write_status(self, status: str, *, progress: dict[str, Any] | None = None,
                     error: str | None = None, started_at: str | None = None,
                     finished_at: str | None = None, append_log: str | None = None) -> None:
        previous = _read_json(self.status_path) or {}
        if append_log:
            live_log = self.status_path.with_suffix(".log")
            try:
                with live_log.open("a", encoding="utf-8") as handle:
                    handle.write(f"[{_utc()}] {append_log}\n")
            except OSError:
                pass
        payload = {
            "schema": RUN_STATUS_SCHEMA,
            "run_id": self.run_id,
            "status": status,
            "progress": progress or previous.get("progress") or {"done": 0, "total": 0, "phase": ""},
            "created_at": previous.get("created_at") or _utc(),
            "started_at": started_at if started_at is not None else previous.get("started_at"),
            "finished_at": finished_at if finished_at is not None else previous.get("finished_at"),
            "error": error if error is not None else previous.get("error"),
        }
        _atomic_json(self.status_path, payload)


_ACTIVE_RUNS: dict[str, RunHandle] = {}
_ACTIVE_LOCK = threading.Lock()


def _log_runner(handle: RunHandle, config: dict[str, Any], stage1_root: Path,
                calibration_root: Path, lead_archive: Path | None,
                selection_manifest: dict[str, Any] | None) -> None:
    try:
        from app6.stage2 import Stage2Config, Stage2Engine
        engine_config = Stage2Config(
            stage1_root=stage1_root,
            calibration_root=calibration_root,
            # The run directory is created fresh with a unique id; overwrite is
            # intentionally False so the engine never wipes run metadata
            # (run_config.json / status.json / logs).
            output_dir=handle.directory,
            overwrite=False,
            min_points106=int(config.get("min_points106", 24)),
            min_points134=int(config.get("min_points134", 30)),
            lead_archive=lead_archive,
            selection_ids=set(config.get("selection_ids") or []) if config.get("selection_ids") is not None else None,
            cancel_event=handle.cancel_event,
            progress_callback=lambda done, total, phase: handle.write_status(
                "running", progress={"done": done, "total": total, "phase": phase}),
        )
        handle.write_status("running", progress={"done": 0, "total": 1, "phase": "initialising"})
        Stage2Engine(engine_config).run()
        if handle.cancel_event.is_set():
            handle.write_status("cancelled", finished_at=_utc(), append_log="run cancelled after engine exit")
        else:
            validation = _read_json(handle.directory / "analysis_validation.json") or {}
            handle.write_status(
                "complete" if validation.get("status") == "complete" else "failed",
                progress={"done": 1, "total": 1, "phase": "complete"},
                finished_at=_utc(),
                error=None if validation.get("status") == "complete" else "analysis_validation.json status != complete",
                append_log="Stage 2 finished",
            )
        handle.finalize_metadata(config, selection_manifest)
        log_event("info", "runs", f"Stage 2 run completed: {handle.run_id}", run_id=handle.run_id)
    except Exception as exc:  # noqa: BLE001 - boundary: any failure is recorded
        handle.write_status("failed", finished_at=_utc(), error=f"{type(exc).__name__}: {exc}",
                            append_log=traceback.format_exc())
        handle.finalize_metadata(config, selection_manifest)
        log_event("error", "runs", f"Stage 2 run failed: {handle.run_id}: {exc}",
                  stack=traceback.format_exc(), run_id=handle.run_id)
    finally:
        with _ACTIVE_LOCK:
            _ACTIVE_RUNS.pop(handle.run_id, None)


def start_stage2_run(profile_id: str | None, *, label: str | None = None,
                     calibration_root: str | None = None, min_points106: int = 24,
                     min_points134: int = 30, lead_archive: str | None = None,
                     paths: RuntimePaths | None = None) -> dict[str, Any]:
    """Create a run directory and launch Stage 2 in a background thread."""
    from app6.stage2.loaders import load_calibration, load_main

    current = paths or load_runtime_paths()
    stage1_root = current.stage1_root
    if not (stage1_root / "main_timeline.csv").is_file():
        raise FileNotFoundError(f"Stage 1 not ready: {stage1_root}/main_timeline.csv")
    cal_root = Path(calibration_root) if calibration_root else current.calibration_root
    if not (cal_root / "main_timeline.csv").is_file() and not (cal_root / "photos").is_dir():
        raise FileNotFoundError(f"calibration not ready: {cal_root}")
    lead_path = Path(lead_archive).resolve() if lead_archive else None
    if lead_path is not None and not lead_path.exists():
        raise FileNotFoundError(f"lead archive not found: {lead_path}")

    # validate heavy inputs BEFORE creating the run dir
    records = load_main(stage1_root)
    load_calibration(cal_root)
    if not records:
        raise RuntimeError("Stage 1 contains no valid records")

    selection_ids: set[str] | None = None
    selection: dict[str, Any] | None = None
    if profile_id:
        from .analysis_profiles import _profile_paths  # noqa: PLC2701 - internal reuse
        files = _profile_paths(profile_id, current)
        manifest = _read_json(files["manifest"])
        if not manifest:
            from .analysis_profiles import freeze_selection_manifest
            from .stage1_timeline import build_stage1_inventory
            inventory = build_stage1_inventory(stage1_root)
            manifest = freeze_selection_manifest(profile_id, inventory["photos"], paths=current,
                                                 stage1_root=str(stage1_root))["manifest"]
        included = manifest.get("included_ids")
        if not isinstance(included, list):
            raise ValueError(f"profile {profile_id} has no valid selection manifest")
        selection_ids = set(str(item) for item in included)
        selection = {
            "profile_id": profile_id,
            "profile_name": manifest.get("profile_name") or profile_id,
            "included_count": len(selection_ids),
            "excluded_count": manifest.get("excluded_count", 0),
        }
    else:
        selection = {"profile_id": None, "profile_name": "full stage1", "included_count": len(records), "excluded_count": 0}

    run_id = _next_run_id(current)
    directory = run_dir(run_id, current)
    directory.mkdir(parents=True, exist_ok=False)

    config: dict[str, Any] = {
        "schema": RUN_CONFIG_SCHEMA,
        "run_id": run_id,
        "label": label or f"Stage 2 · {run_id}",
        "created_at": _utc(),
        "profile_id": profile_id,
        "profile_name": selection.get("profile_name"),
        "selection": selection,
        "selection_ids": sorted(selection_ids) if selection_ids is not None else None,
        "stage1_root": str(stage1_root),
        "calibration_root": str(cal_root),
        "lead_archive": str(lead_path) if lead_path else None,
        "min_points106": int(min_points106),
        "min_points134": int(min_points134),
        "engine": "app6.stage2.Stage2Engine",
        "immutable_inputs": True,
        "not_a_verdict": True,
    }
    # Live status/logs live OUTSIDE the run dir while the engine runs; they
    # are finalized into the run dir when the engine finishes.
    live_status = runs_root(current) / f"{run_id}.status.json"
    handle = RunHandle(run_id=run_id, directory=directory, status_path=live_status)
    handle.write_status("queued", progress={"done": 0, "total": 1, "phase": "queued"},
                        append_log=f"run created; profile={profile_id or 'none'}")
    log_event("info", "runs", f"Stage 2 run started: {run_id}",
              detail=f"profile={profile_id or 'none'} included={selection.get('included_count')}",
              run_id=run_id)
    thread = threading.Thread(
        target=_log_runner,
        args=(handle, config, stage1_root, cal_root, lead_path, manifest if selection_ids is not None else None),
        name=f"stage2-{run_id}",
        daemon=True,
    )
    handle.thread = thread
    with _ACTIVE_LOCK:
        _ACTIVE_RUNS[run_id] = handle
    thread.start()
    return get_run(run_id, current)


def cancel_run(run_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    directory = run_dir(run_id, current)
    if not directory.is_dir():
        raise FileNotFoundError(f"run not found: {run_id}")
    handle = _ACTIVE_RUNS.get(run_id)
    log_event("warn", "runs", f"Stage 2 run cancellation requested: {run_id}", run_id=run_id)
    if handle is not None:
        handle.cancel_event.set()
        handle.write_status("cancelling", append_log="cancellation requested")
    else:
        status = _read_json(directory / "status.json") or {}
        if status.get("status") in ("queued", "running"):
            status["status"] = "cancelled"
            status["finished_at"] = _utc()
            _atomic_json(directory / "status.json", status)
    return get_run(run_id, current)


def start_stage2b(run_id: str, *, prior_root: str | None = None,
                  paths: RuntimePaths | None = None) -> dict[str, Any]:
    """Run Stage 2B post-processing on a completed Stage 2 run.

    Stage 2B output lives OUTSIDE the Stage 2 run tree (``<storage>/stage2b/
    <run_id>/``) because ``Stage2BConfig`` forbids output inside ``stage2_root``.
    """
    current = paths or load_runtime_paths()
    directory = run_dir(run_id, current)
    if not directory.is_dir():
        raise FileNotFoundError(f"run not found: {run_id}")
    manifest = _read_json(directory / "analysis_manifest.json")
    if not manifest or manifest.get("status") != "complete":
        raise RuntimeError("Stage 2 run is not complete; Stage 2B requires a completed run")

    stage2b_root = current.storage_root / "stage2b"
    output = (stage2b_root / run_id).resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("Stage 2B output already exists for this run (regeneration not allowed)")

    prior = Path(prior_root).resolve() if prior_root else None
    if prior is not None and not prior.exists():
        raise FileNotFoundError(f"prior root not found: {prior}")

    from app6.stage2b import Stage2BConfig, Stage2BEngine
    output.mkdir(parents=True, exist_ok=True)
    try:
        result = Stage2BEngine(Stage2BConfig(directory, output, prior_root=prior, overwrite=True)).run()
    except Exception:
        # do not leave a half-written Stage 2B output behind
        if output.exists():
            shutil.rmtree(output, ignore_errors=True)
        raise
    summary = get_run(run_id, current)
    summary["stage2b"] = result
    summary["stage2b_output"] = str(output)
    return summary


def archive_run(run_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    current = paths or load_runtime_paths()
    directory = run_dir(run_id, current)
    if not directory.is_dir():
        raise FileNotFoundError(f"run not found: {run_id}")
    status = _read_json(directory / "status.json") or {}
    if status.get("status") in ("queued", "running", "cancelling"):
        raise RuntimeError("cannot archive a run that is queued or running")
    destination = archive_root(current) / run_id
    if destination.exists():
        raise RuntimeError(f"archive destination already exists: {destination}")
    shutil.move(str(directory), str(destination))
    log_event("info", "runs", f"Stage 2 run archived: {run_id} → {destination}", run_id=run_id)
    return {
        "schema": RUN_MANAGER_SCHEMA,
        "run_id": run_id,
        "archived": True,
        "destination": str(destination),
    }
