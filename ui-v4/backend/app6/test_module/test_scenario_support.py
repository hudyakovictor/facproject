from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app6.archive_adapter import load_archive_records, with_synthetic_dates
from app6.run_scenario_planner import build_plan


class ScenarioSupportTests(unittest.TestCase):
    def _tree(self, root: Path) -> None:
        for person in ("person_01", "person_02"):
            for frame in range(3):
                directory = root / person / f"frame_{frame:06d}"
                directory.mkdir(parents=True)
                (directory / "info.json").write_text(json.dumps({
                    "photo_id": f"{person}_{frame}",
                    "pose": {"pose_bin": "frontal"},
                }), encoding="utf-8")

    def test_archive_records_are_pose_validated_and_dates_are_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._tree(root)
            records = load_archive_records(root)
            self.assertEqual(len(records), 6)
            dated = with_synthetic_dates(records)
            self.assertEqual(dated[0].date, "2000-01-01")
            self.assertEqual(dated[-1].date, "2000-01-06")

    def test_aabb_aa_plan_keeps_the_requested_role_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._tree(root)
            plan = build_plan("S03", "frontal", root)
            self.assertTrue(plan["data_available"])
            self.assertEqual(plan["frame_count"], 6)
            self.assertEqual([x["person"] for x in plan["frames"]], [
                "person_01", "person_01", "person_02", "person_02", "person_01", "person_01",
            ])
            self.assertEqual(plan["frames"][0]["date"], "2000-01-01")


if __name__ == "__main__":
    unittest.main()
