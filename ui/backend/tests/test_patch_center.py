from __future__ import annotations
import tempfile
from pathlib import Path
import unittest
from dpo.patch_center import PatchCenter

class PatchCenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "sample.txt").write_text("hello", encoding="utf-8")
        self.patch_center = PatchCenter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_export_fix_capsule(self) -> None:
        raw = self.patch_center.export_fix_capsule("task-1", ["sample.txt"])
        self.assertTrue(len(raw) > 0)

    def test_dry_run_patch(self) -> None:
        diff = "diff --git a/sample.txt b/sample.txt\n--- a/sample.txt\n+++ b/sample.txt\n@@ -1 +1 @@\n-hello\n+world\n"
        res = self.patch_center.dry_run_patch(diff)
        self.assertIn("success", res)

if __name__ == "__main__":
    unittest.main()
