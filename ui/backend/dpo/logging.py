"""Structured JSON logging plus an in-memory ring buffer that feeds the UI log console."""
from __future__ import annotations

import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("event", "run_id", "function_id", "state"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class LogBuffer:
    """Thread-safe bounded buffer of structured log entries with a monotonic seq.

    The buffer never blocks logging: old entries are dropped once capacity is
    reached, while ``seq`` keeps growing so clients can poll incrementally via
    ``since(after)`` without ever seeing duplicates.
    """

    def __init__(self, capacity: int = 2000) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._lock = threading.Lock()
        self._entries: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._seq = 0

    def append(self, level: str, logger_name: str, message: str, **extra: Any) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            entry: dict[str, Any] = {
                "seq": self._seq,
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "logger": logger_name,
                "message": message,
            }
            for key, value in extra.items():
                if value is not None:
                    entry[key] = value
            self._entries.append(entry)
            return entry

    def since(self, after: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        with self._lock:
            items = [dict(entry) for entry in self._entries if entry["seq"] > after]
        return items[-max(1, limit):]

    @property
    def last_seq(self) -> int:
        with self._lock:
            return self._seq


GLOBAL_LOG_BUFFER = LogBuffer()


class BufferHandler(logging.Handler):
    """Mirrors python logging records into a LogBuffer for the UI console."""

    def __init__(self, buffer: LogBuffer) -> None:
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            extra = {key: getattr(record, key, None) for key in ("event", "run_id", "function_id", "state")}
            message = record.getMessage()
            if record.exc_info:
                message = f"{message}\n{logging.Formatter().formatException(record.exc_info)}"
            self._buffer.append(record.levelname.lower(), record.name, message, **extra)
        except Exception:  # pragma: no cover - logging must never crash the app
            self.handleError(record)


def configure_logging(level: int = logging.INFO, buffer: LogBuffer | None = None) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler, BufferHandler(buffer or GLOBAL_LOG_BUFFER)]
    root.setLevel(level)
