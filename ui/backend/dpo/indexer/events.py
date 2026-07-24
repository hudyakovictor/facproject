"""Thread-safe project update fan-out for WebSocket clients."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Queue
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class ProjectUpdate:
    event: str
    occurred_at: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event, "occurred_at": self.occurred_at, "payload": self.payload}


class ProjectEventHub:
    def __init__(self) -> None:
        self._subscribers: set[Queue] = set()
        self._lock = RLock()

    def subscribe(self) -> Queue:
        queue: Queue = Queue(maxsize=32)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: Queue) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def publish(self, payload: dict[str, Any]) -> None:
        update = ProjectUpdate("project_index_updated", datetime.now(timezone.utc).isoformat(), payload).to_dict()
        with self._lock:
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except Exception:
                    pass
            queue.put_nowait(update)
