from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import unittest

from dpo.retention import move_to_trash, preview_candidates


class RetentionTests(unittest.TestCase):
    def test_preview_preserves_manifests_and_move_is_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            heavy = Path(tmp)
            run = heavy / "runs" / "run-1"
            run.mkdir(parents=True)
            old = run / "preview.bin"
            manifest = run / "manifest.json"
            old.write_bytes(b"old")
            manifest.write_text("{}", encoding="utf-8")
            timestamp = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
            os.utime(old, (timestamp, timestamp))
            os.utime(manifest, (timestamp, timestamp))
            candidates = preview_candidates(heavy / "runs", older_than_days=7)
            self.assertEqual([item.path for item in candidates], [old])
            destination = move_to_trash(candidates[0], heavy_root=heavy, batch_id="cleanup-001")
            self.assertFalse(old.exists())
            self.assertTrue(destination.is_file())
            self.assertTrue(manifest.is_file())


if __name__ == "__main__":
    unittest.main()
