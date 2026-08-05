"""Event log for the forensic workstation (Iteration 12).

Append-only JSONL journal of everything that matters when something breaks:

- every HTTP response with status >= 400 (request-level, via middleware),
- every unhandled exception (with stack, via the exception handler),
- pipeline events: Stage 2 run start/complete/failed/cancel, Stage 2B,
  report generation, profile freeze, selection save,
- client-side (browser) errors pushed by the UI (`POST /api/v1/logs/client`).

Events are stored under ``<storage>/registry/logs/events.jsonl`` and mirrored
in an in-memory ring (last 2000) for fast reads. The journal is append-only —
nothing is ever deleted by the UI; "clearing" only empties the local browser
ring.

Levels: debug < info < warn < error.
"""
from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime_config import ensure_runtime_write_dirs, load_runtime_paths

EVENT_LOG_SCHEMA = "deeputin-event-log-v1.0"
RING_SIZE = 2000
VALID_LEVELS = {"debug", "info", "warn", "error"}
# client ingestion caps (avoid flooding the journal from a buggy page)
CLIENT_MAX_EVENTS_PER_REQUEST = 100
CLIENT_MAX_MESSAGE = 2000
CLIENT_MAX_DETAIL = 4000
CLIENT_MAX_STACK = 4000

_lock = threading.Lock()
_ring: deque[dict[str, Any]] = deque(maxlen=RING_SIZE)


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _log_path() -> Path:
    paths = load_runtime_paths()
    ensure_runtime_write_dirs(paths)
    directory = paths.registry_root / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "events.jsonl"


def _load_ring() -> None:
    """Load the last RING_SIZE events from disk into memory (module import)."""
    global _ring
    path = _log_path()
    if not path.is_file():
        return
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        parsed: list[dict[str, Any]] = []
        for line in lines[-RING_SIZE:]:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                parsed.append(event)
        _ring = deque(parsed, maxlen=RING_SIZE)
    except OSError:
        pass


def log_event(
    level: str,
    source: str,
    message: str,
    *,
    detail: Any = None,
    stack: str | None = None,
    path: str | None = None,
    run_id: str | None = None,
    job_id: str | None = None,
    origin: str = "server",
) -> dict[str, Any]:
    """Record one event: append to disk + mirror in the in-memory ring."""
    if level not in VALID_LEVELS:
        level = "info"
    event: dict[str, Any] = {
        "schema": EVENT_LOG_SCHEMA,
        "ts": _utc(),
        "level": level,
        "source": str(source)[:64],
        "origin": "server" if origin != "client" else "client",
        "message": str(message)[:2000],
    }
    if detail is not None:
        event["detail"] = str(detail)[:4000]
    if stack:
        event["stack"] = str(stack)[:4000]
    if path:
        event["path"] = str(path)[:300]
    if run_id:
        event["run_id"] = str(run_id)[:80]
    if job_id:
        event["job_id"] = str(job_id)[:80]

    with _lock:
        _ring.append(event)
        path_file = _log_path()
        try:
            with path_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            pass  # journal write must never break the API
    return dict(event)


def list_events(*, limit: int = 500, level: str | None = None,
                source: str | None = None, origin: str | None = None,
                since: str | None = None) -> list[dict[str, Any]]:
    """Newest first, with optional filters."""
    limit = max(1, min(int(limit), 2000))
    with _lock:
        events = list(_ring)
    events.reverse()  # newest first
    if level and level in VALID_LEVELS:
        events = [event for event in events if event.get("level") == level]
    if source:
        events = [event for event in events if event.get("source") == source]
    if origin:
        events = [event for event in events if event.get("origin") == origin]
    if since:
        events = [event for event in events if str(event.get("ts", "")) >= since]
    return events[:limit]


def summary() -> dict[str, Any]:
    with _lock:
        events = list(_ring)
    levels: dict[str, int] = {}
    sources: dict[str, int] = {}
    origins: dict[str, int] = {}
    for event in events:
        levels[event.get("level", "info")] = levels.get(event.get("level", "info"), 0) + 1
        sources[event.get("source", "?")] = sources.get(event.get("source", "?"), 0) + 1
        origins[event.get("origin", "server")] = origins.get(event.get("origin", "server"), 0) + 1
    errors = events[-20:] if any(event.get("level") == "error" for event in events) else []
    errors.reverse()
    return {
        "schema": EVENT_LOG_SCHEMA,
        "total": len(events),
        "levels": levels,
        "sources": sources,
        "origins": origins,
        "recent_errors": errors,
    }


def ingest_client_events(payload: Any) -> dict[str, Any]:
    """Validate and store events pushed by the browser UI."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    raw = payload.get("events")
    if not isinstance(raw, list):
        raise ValueError("payload.events must be a list")
    received = 0
    for item in raw[:CLIENT_MAX_EVENTS_PER_REQUEST]:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not message:
            continue
        log_event(
            str(item.get("level") or "info"),
            str(item.get("source") or "client"),
            str(message),
            detail=item.get("detail"),
            stack=item.get("stack"),
            path=item.get("path"),
            origin="client",
        )
        received += 1
    return {"schema": EVENT_LOG_SCHEMA, "received": received}


_load_ring()
