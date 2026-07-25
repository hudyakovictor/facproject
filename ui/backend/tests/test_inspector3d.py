from __future__ import annotations
import tempfile
from pathlib import Path
import unittest
from dpo.inspector3d import Inspector3DProvider

class Inspector3DTests(unittest.TestCase):
    def test_inspector_3d_fallback_and_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider = Inspector3DProvider(Path(tmp))
            preview = provider.get_mesh_preview("rec-99")
            self.assertEqual(preview["record_id"], "rec-99")
            self.assertIn("vertices", preview)
            self.assertIn("landmarks_106", preview)

            pair = provider.get_pair_comparison("rec-a", "rec-b")
            self.assertEqual(pair["record_a"], "rec-a")
            self.assertEqual(pair["record_b"], "rec-b")
            self.assertIn("landmark_distances", pair)

if __name__ == "__main__":
    unittest.main()
