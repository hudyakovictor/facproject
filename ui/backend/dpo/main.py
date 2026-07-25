"""FastAPI adapter. Core storage and dataset services remain framework-independent."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from .health import collect_health
from .guide import build_guide_status
from .photos import PhotoIndex
from .catalog import bind_tests, build_catalog, index_tests, parse_status_audit
from .canvas import LayoutStore, build_canvas_graph
from .calibration import CalibrationRegistry, RunHashes, load_pose_bins
from .datasets import DatasetRegistry
from .readiness import SnapshotStore, evaluate
from .runtime import RunManager, RunnerRegistry, RunnerSpec, TERMINAL
from .timeline import build_timeline, timeline_state_at
from .scenario_lab import ScenarioLab
from .feedback import BackupManager, build_capsule, build_spec, classify_failure
from .indexer import ProjectIndex
from .indexer.events import ProjectEventHub
from .indexer.watcher import IndexWatcher
from .logging import GLOBAL_LOG_BUFFER, configure_logging
from .settings import ProjectSettings


def create_app(config_path: str | Path | None = None):
    try:
        from fastapi import FastAPI
    except ImportError as exc:  # pragma: no cover - exercised after dependencies are installed
        raise RuntimeError("FastAPI is not installed; run: pip install -e 'ui[dev]'") from exc

    config = Path(config_path or os.environ.get("DPO_CONFIG", Path(__file__).resolve().parents[2] / "config" / "project.example.yaml"))
    settings = ProjectSettings.load(config)
    configure_logging()
    app = FastAPI(title="DEEPUTIN Pipeline Observatory", version="0.1.0", docs_url="/api/docs")
    http_logger = logging.getLogger("dpo.http")

    @app.middleware("http")
    async def log_http_request(request, call_next):
        started = time.perf_counter()
        request_id = request.headers.get("x-request-id") or f"http-{time.time_ns()}"
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            http_logger.exception("request crashed", extra={"event": "http_exception", "state": f"{request.method} {request.url.path} {elapsed_ms}ms"})
            raise
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        response.headers["x-request-id"] = request_id
        if request.url.path != "/api/logs":
            level = logging.WARNING if response.status_code >= 400 or elapsed_ms > 1500 else logging.INFO
            http_logger.log(level, "%s %s -> %s in %sms", request.method, request.url.path, response.status_code, elapsed_ms, extra={"event": "http_request", "state": request_id})
        return response
    project_index = ProjectIndex(settings.app6_root)
    project_index.refresh()
    app.state.project_index = project_index
    project_events = ProjectEventHub()
    project_watcher = IndexWatcher(project_index, project_events.publish)
    config_root = Path(__file__).resolve().parents[2] / "config"
    layout_store = LayoutStore(settings.storage.control_root / "layouts")
    readiness_store = SnapshotStore(settings.storage.control_root / "readiness")
    import yaml
    runner_data = yaml.safe_load((config_root / "runners.yaml").read_text())
    runner_registry = RunnerRegistry([RunnerSpec(str(x["id"]), str(x["title"]), str(x["module"]), tuple(str(a) for a in x.get("fixed_args", [])), int(x.get("timeout", 300))) for x in runner_data["runners"]])
    scenario_lab = ScenarioLab(settings.app6_root)
    run_manager = RunManager(runner_registry, settings.app6_root, settings.storage.control_root, settings.storage.heavy_root, int(runner_data.get("max_parallel_runs", 1)))
    backup_manager = BackupManager(settings.storage.control_root / "backups", settings.app6_root)
    capsule_root = settings.storage.control_root / "capsules"
    calibration_registry = CalibrationRegistry(settings.storage.control_root / "calibration_runs")
    dataset_registry = DatasetRegistry(settings.datasets)
    photo_index = PhotoIndex(settings.datasets.main_root)

    def _investigate(run_id: str) -> dict | None:
        record = run_manager.get(run_id).to_dict()
        log_lines = [e["payload"].get("text", "") for e in run_manager.events(run_id) if e.get("type") == "log"]
        classification = classify_failure(record, log_lines, None)
        if classification is None:
            return None
        spec = build_spec(record, classification)
        return {"classification": classification.to_dict(), "spec": spec}

    def catalog_snapshot():
        project_index.refresh()
        statuses = parse_status_audit(settings.app6_root / "STATUS_AUDIT.py", project_index)
        tests = index_tests(settings.app6_root)
        bindings = bind_tests(tests, project_index, config_root / "test_bindings.yaml")
        catalog = build_catalog(project_index, statuses, bindings, config_root / "function_catalog.yaml")
        return statuses, tests, bindings, catalog

    @app.on_event("startup")
    def start_project_watcher() -> None:
        project_watcher.start()

    @app.on_event("shutdown")
    def stop_project_watcher() -> None:
        project_watcher.stop()
        run_manager.shutdown()

    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(KeyError)
    def _handle_key_error(request: Request, exc: KeyError) -> JSONResponse:
        message = exc.args[0] if exc.args else str(exc)
        return JSONResponse(status_code=404, content={"detail": str(message)})

    @app.exception_handler(ValueError)
    def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(RuntimeError)
    def _handle_runtime_error(request: Request, exc: RuntimeError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/api/health")
    def api_health() -> dict:
        return collect_health(settings).to_dict()

    @app.get("/api/logs")
    def api_logs(after: int = 0, limit: int = 500) -> dict:
        entries = GLOBAL_LOG_BUFFER.since(after, limit)
        return {"entries": entries, "last_seq": entries[-1]["seq"] if entries else after}

    @app.get("/api/guide/status")
    def api_guide_status() -> dict:
        health = collect_health(settings, persist=False).to_dict()
        photo_snapshot = photo_index.query(limit=1)
        return build_guide_status(health, run_manager.records.values(), {"photo_index_count": photo_snapshot["summary"]["all_photos"]})

    @app.get("/api/photos")
    def api_photos(offset: int = 0, limit: int = 500, pose: str | None = None, year_from: int | None = None, year_to: int | None = None) -> dict:
        return photo_index.query(offset=offset, limit=limit, pose=pose, year_from=year_from, year_to=year_to)

    @app.get("/api/system/health")
    def api_system_health() -> dict:
        return collect_health(settings).to_dict()

    @app.get("/api/project")
    def api_project() -> dict:
        health = collect_health(settings, persist=False).to_dict()
        return {
            "name": "DEEPUTIN Pipeline Observatory",
            "app6_root": str(settings.app6_root),
            "control_root": str(settings.storage.control_root),
            "heavy_root": str(settings.storage.heavy_root),
            "main_dataset_root": str(settings.datasets.main_root),
            "calibration_dataset_root": str(settings.datasets.calibration_root) if settings.datasets.calibration_root else None,
            "health": health,
        }

    @app.get("/api/modules")
    def api_modules() -> dict:
        delta = project_index.refresh()
        return {"delta": delta.to_dict(), "modules": [module.to_dict() for module in project_index.modules]}

    @app.get("/api/functions")
    def api_functions() -> dict:
        delta = project_index.refresh()
        return {"delta": delta.to_dict(), "functions": [function.to_dict() for function in project_index.functions]}

    @app.get("/api/project/graph")
    def api_project_graph() -> dict:
        delta = project_index.refresh()
        return {"delta": delta.to_dict(), **project_index.snapshot()}

    @app.get("/api/status")
    def api_status() -> dict:
        statuses, _, _, _ = catalog_snapshot(); return {"entries": [x.to_dict() for x in statuses]}

    @app.get("/api/tests")
    def api_tests() -> dict:
        _, tests, bindings, _ = catalog_snapshot(); return {"tests": [x.to_dict() for x in tests], "bindings": [x.to_dict() for x in bindings]}

    @app.get("/api/catalog")
    def api_catalog() -> dict:
        statuses, tests, bindings, catalog = catalog_snapshot(); return {"entries": [x.to_dict() for x in catalog], "summary": {"functions": len(catalog), "status_entries": len(statuses), "tests": len(tests), "bindings": len(bindings), "missing_descriptions": sum(x.task_priority == "P2" for x in catalog)}}

    @app.get("/api/source")
    def api_source(path: str, line_start: int = 1, line_end: int = 200) -> dict:
        candidate=(settings.app6_root/path).resolve(strict=False);root=settings.app6_root.resolve(strict=False)
        if candidate.suffix != ".py" or (candidate != root and root not in candidate.parents): raise ValueError("unsafe source path")
        lines=candidate.read_text(encoding="utf-8").splitlines();start=max(1,line_start);end=min(len(lines),max(start,line_end));return {"path":path,"line_start":start,"line_end":end,"content":"\n".join(lines[start-1:end])}

    @app.get("/api/readiness")
    def api_readiness() -> dict:
        _, _, bindings, catalog = catalog_snapshot()
        items = evaluate(project_index, catalog, bindings)
        snapshot = readiness_store.save(items)
        return {"items": [x.to_dict() for x in items], "snapshot": snapshot.name}

    @app.get("/api/canvas")
    def api_canvas() -> dict:
        _, _, bindings, catalog = catalog_snapshot()
        readiness = evaluate(project_index, catalog, bindings)
        return build_canvas_graph(project_index, catalog, readiness)

    @app.get("/api/layouts/{name}")
    def api_load_layout(name: str) -> dict:
        return layout_store.load(name) or {"schema":"dpo-layout-v1","positions":{}}

    @app.put("/api/layouts/{name}")
    def api_save_layout(name: str, payload: dict) -> dict:
        path=layout_store.save(name,payload.get("positions",{}));return {"saved":True,"name":name,"path":str(path)}



    @app.get("/api/scenarios")
    def api_scenarios() -> dict:
        return {"scenarios": scenario_lab.scenarios(), "matrix": scenario_lab.function_matrix(), "synthetic": scenario_lab.synthetic()}

    @app.get("/api/scenarios/plan")
    def api_scenario_plan(scenario_id: str, pose: str = "frontal", combinations: int = 1) -> dict:
        return scenario_lab.plan(scenario_id, pose, combinations)

    @app.post("/api/scenarios/plan-maximum")
    def api_scenario_plan_maximum() -> dict:
        plan = scenario_lab.maximum_plan()
        target = settings.storage.control_root / "scenario_plans" / "maximum.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        temp.write_text(__import__("json").dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(target)
        return {**plan, "saved": True, "saved_path": str(target)}

    @app.get("/api/scenarios/results-maximum")
    def api_scenario_results_maximum() -> dict:
        return scenario_lab.maximum_results()

    @app.get("/api/runners")
    def api_runners() -> dict:
        return {"runners": [{"id": x.id, "title": x.title, "module": x.module, "fixed_args": list(x.fixed_args), "timeout": x.timeout} for x in runner_registry.list()]}

    @app.post("/api/runs")
    def api_start_run(payload: dict) -> dict:
        health = collect_health(settings, persist=False)
        if health.storage.get("state") != "ready": raise RuntimeError("External heavy storage is not ready")
        return run_manager.submit(str(payload.get("runner_id", "")), int(payload.get("seed", 0))).to_dict()

    @app.get("/api/runs/{run_id}")
    def api_run(run_id: str) -> dict:
        return run_manager.get(run_id).to_dict()

    @app.get("/api/runs/{run_id}/events")
    def api_run_events(run_id: str, after: int = 0) -> dict:
        return {"events": run_manager.events(run_id, after)}

    @app.post("/api/runs/{run_id}/cancel")
    def api_cancel_run(run_id: str) -> dict:
        run_manager.cancel(run_id); return run_manager.get(run_id).to_dict()

    @app.get("/api/runs/{run_id}/investigation")
    def api_run_investigation(run_id: str) -> dict:
        result = _investigate(run_id)
        return result or {"classification": None, "spec": None}

    @app.get("/api/runs/{run_id}/timeline")
    def api_run_timeline(run_id: str) -> dict:
        record = run_manager.get(run_id)
        return build_timeline(run_manager.events(run_id), record.created_at)

    @app.get("/api/runs/{run_id}/timeline/state")
    def api_run_timeline_state(run_id: str, at_seq: int = 0) -> dict:
        record = run_manager.get(run_id)
        timeline = build_timeline(run_manager.events(run_id), record.created_at)
        return timeline_state_at(timeline, at_seq)

    @app.post("/api/capsules")
    def api_create_capsule(payload: dict) -> dict:
        run_id = str(payload.get("run_id", ""))
        result = _investigate(run_id)
        if result is None: raise RuntimeError("run has no failure to capture")
        record = run_manager.get(run_id).to_dict()
        log_lines = [e["payload"].get("text", "") for e in run_manager.events(run_id) if e.get("type") == "log"]
        out = build_capsule(result["spec"], tuple(log_lines), capsule_root=capsule_root)
        return {"id": out["id"], "path": out["path"], "run_id": record.get("id")}

    @app.get("/api/backups")
    def api_list_backups() -> dict:
        return {"backups": backup_manager.list()}

    @app.post("/api/patches/apply")
    def api_apply_patch(payload: dict) -> dict:
        from .feedback import apply_patch
        diff_text = str(payload.get("diff", ""))
        return apply_patch(diff_text, allowed_root=settings.app6_root, backup_manager=backup_manager)

    @app.post("/api/backups/{backup_id}/rollback")
    def api_rollback_backup(backup_id: str) -> dict:
        restored = backup_manager.rollback(backup_id)
        return {"backup_id": backup_id, "restored": restored}

    @app.post("/api/patches/apply-safe")
    def api_apply_patch_safe(payload: dict) -> dict:
        from .feedback import run_isolated_patch
        diff_text = str(payload.get("diff", ""))
        regression = runner_registry.get("app6-regression")
        test_cmd = [sys.executable, "-m", regression.module, *regression.fixed_args]
        commit_message = str(payload.get("commit_message") or "dpo: apply investigated patch")
        return run_isolated_patch(diff_text, allowed_root=settings.app6_root, backup_manager=backup_manager, test_cmd=test_cmd, timeout=regression.timeout, commit_message=commit_message)

    @app.post("/api/patches/{commit_sha}/revert")
    def api_revert_patch(commit_sha: str) -> dict:
        from .feedback import revert_patch_commit
        return revert_patch_commit(commit_sha, allowed_root=settings.app6_root)

    @app.get("/api/calibration/pose-policy")
    def api_pose_policy() -> dict:
        return {
            "bins": load_pose_bins(settings.app6_root),
            "source": "app6/stage1/config.py:POSE_BINS",
            "note": "yaw boundaries and canonical target are the real static policy used by geometry.classify_pose(); pitch/roll boundaries, residual distance, pair eligibility and coverage require an actual calibration run and are not fabricated here.",
        }

    @app.get("/api/calibration/run-groups")
    def api_list_calibration_run_groups() -> dict:
        return {"run_groups": calibration_registry.list()}

    @app.post("/api/calibration/run-groups")
    def api_create_calibration_run_group(payload: dict) -> dict:
        group_id = payload.get("id")
        return calibration_registry.create(str(group_id) if group_id else None).to_dict()

    @app.get("/api/calibration/run-groups/{group_id}")
    def api_get_calibration_run_group(group_id: str) -> dict:
        return calibration_registry.get(group_id).to_dict()

    @app.post("/api/calibration/run-groups/{group_id}/members")
    def api_register_calibration_member(group_id: str, payload: dict) -> dict:
        hashes = RunHashes(
            dataset_hash=str(payload.get("dataset_hash", "")),
            code_hash=str(payload.get("code_hash", "")),
            model_hash=str(payload.get("model_hash", "")),
            config_hash=str(payload.get("config_hash", "")),
        )
        return calibration_registry.register_member(group_id, str(payload.get("role", "")), str(payload.get("run_id", "")), hashes).to_dict()

    @app.post("/api/calibration/run-groups/{group_id}/table")
    def api_attach_calibration_table(group_id: str, payload: dict) -> dict:
        raw_path = payload.get("path")
        path = Path(str(raw_path)) if raw_path else dataset_registry.find_calibration_index()
        if path is None:
            raise RuntimeError("no calibration index path was provided and none was found in the configured calibration root")
        report = dataset_registry.parse_calibration_table(path)
        return calibration_registry.attach_trusted_table(group_id, report).to_dict()

    @app.post("/api/calibration/run-groups/{group_id}/approve")
    def api_approve_calibration_run_group(group_id: str, payload: dict) -> dict:
        return calibration_registry.approve(group_id, approved_by=str(payload.get("approved_by", ""))).to_dict()

    @app.post("/api/calibration/run-groups/{group_id}/reject")
    def api_reject_calibration_run_group(group_id: str, payload: dict) -> dict:
        return calibration_registry.reject(group_id, reason=str(payload.get("reason", ""))).to_dict()

    @app.get("/api/calibration/run-groups/{group_id}/verify")
    def api_verify_calibration_run_group(group_id: str) -> dict:
        return {"group_id": group_id, "bundle_intact": calibration_registry.verify_bundle_integrity(group_id)}

    # ── Serve built React frontend ─────────────────────────────────────���
    _frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if _frontend_dist.is_dir():
        from fastapi.staticfiles import StaticFiles
        from starlette.responses import FileResponse

        app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="static-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def _serve_spa(full_path: str) -> FileResponse:
            candidate = _frontend_dist / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(_frontend_dist / "index.html"))

    # ── WebSockets ──────────────────────────────────────────────────────
    @app.websocket("/ws/runs/{run_id}")
    async def ws_run(websocket, run_id: str) -> None:
        await websocket.accept(); seq = 0
        while True:
            for event in run_manager.events(run_id, seq):
                seq = event["seq"]; await websocket.send_json(event)
            record = run_manager.get(run_id)
            if record.status in TERMINAL:
                await websocket.send_json({"schema": "dpo-run-state-v1", "type": "state", "payload": record.to_dict()}); break
            await asyncio.sleep(0.2)

    @app.websocket("/ws/project")
    async def ws_project(websocket) -> None:
        await websocket.accept()
        queue = project_events.subscribe()
        try:
            await websocket.send_json({"event": "project_index_snapshot", "payload": project_index.snapshot()})
            while True:
                await websocket.send_json(await asyncio.to_thread(queue.get))
        finally:
            project_events.unsubscribe(queue)

    return app


try:  # Allows `uvicorn dpo.main:app`; missing optional deps do not break core imports.
    app = create_app()
except (RuntimeError, OSError, ValueError):
    app = None
