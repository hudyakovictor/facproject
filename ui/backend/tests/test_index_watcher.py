from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import time
import unittest

from dpo.indexer.project_index import ProjectIndex
from dpo.indexer.watcher import IndexWatcher


class WatcherTests(unittest.TestCase):
    def test_watcher_debounces_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "app6"
            root.mkdir()
            source = root / "a.py"
            source.write_text("def a():\n    return 1\n", encoding="utf-8")
            index = ProjectIndex(root)
            index.refresh()
            event = threading.Event()
            payloads: list[dict] = []
            watcher = IndexWatcher(index, lambda payload: (payloads.append(payload), event.set()), interval=0.02, debounce=0.04)
            watcher.start()
            try:
                time.sleep(0.04)
                source.write_text("def a():\n    return 2\n", encoding="utf-8")
                self.assertTrue(event.wait(1.0))
            finally:
                watcher.stop()
            self.assertEqual(len(payloads), 1)
            self.assertEqual(payloads[0]["changed"], ["a.py"])


if __name__ == "__main__":
    unittest.main()
