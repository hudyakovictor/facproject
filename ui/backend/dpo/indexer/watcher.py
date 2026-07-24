"""Dependency-light polling watcher with debounce; watchfiles adapter can replace it later."""
from __future__ import annotations

import threading
import time
from typing import Callable

from .project_index import IGNORE_PARTS, ProjectIndex

try:
    from watchfiles import watch as watch_files
except ImportError:  # dependency-light offline fallback
    watch_files = None


class IndexWatcher:
    def __init__(self, index: ProjectIndex, callback: Callable[[dict], None], *, interval: float = 0.5, debounce: float = 0.35) -> None:
        self.index, self.callback = index, callback
        self.interval, self.debounce = interval, debounce
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="dpo-index-watcher", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def _run(self) -> None:
        if watch_files is not None:
            self._run_watchfiles()
            return
        self._run_polling()

    def _run_watchfiles(self) -> None:
        for changes in watch_files(self.index.root, stop_event=self._stop, debounce=int(self.debounce * 1000), step=max(10, int(self.interval * 1000))):
            relevant = [path for _change, path in changes if path.endswith(".py") and not any(part in IGNORE_PARTS for part in path.split("/"))]
            if relevant:
                self.callback(self.index.refresh().to_dict())

    def _run_polling(self) -> None:
        pending_at: float | None = None
        previous = self._state()
        while not self._stop.wait(self.interval):
            current = self._state()
            if current != previous:
                previous, pending_at = current, time.monotonic()
            if pending_at is not None and time.monotonic() - pending_at >= self.debounce:
                delta = self.index.refresh()
                self.callback(delta.to_dict())
                pending_at = None

    def _state(self) -> tuple[tuple[str, int, int], ...]:
        out = []
        for path in sorted(self.index.root.rglob("*.py")):
            if not path.is_file():
                continue
            if any(part in IGNORE_PARTS for part in path.relative_to(self.index.root).parts):
                continue
            try:
                stat = path.stat()
                out.append((path.relative_to(self.index.root).as_posix(), stat.st_mtime_ns, stat.st_size))
            except OSError:
                continue
        return tuple(out)
