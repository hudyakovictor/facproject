"""🔄 GUARD → Приватные лиды-подсказки (ER-190, ER-194 / AA02, AA01).

load_leads: при отсутствии prior-root возвращает not_provided (fail-closed), а не
сфабрикованные лиды; все лиды помечаются как «audit targets only, никогда ground
truth / подбор порогов».
pair_leads: свёртка лидов по датам для пары — приоритет/регионы/события.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app6.stage2.leads import load_leads, pair_leads


class LoadLeadsTests(unittest.TestCase):
    def test_no_prior_root_is_not_provided(self):
        reg = load_leads(None)
        self.assertEqual(reg["status"], "not_provided")
        self.assertEqual(reg["dates"], {})
        self.assertEqual(reg["metrics"], [])
        self.assertEqual(reg["regions"], [])
        self.assertEqual(reg["coverage"], [])

    def test_never_used_as_ground_truth(self):
        # Полноценный ответ (loaded) всегда декларирует: лиды — это цели аудита,
        # а не ground truth и не средство подбора порогов.
        reg = load_leads(Path("/nonexistent_prior_root"))
        self.assertIn("never", reg["policy"])
        self.assertIn("threshold", reg["policy"])

    def test_empty_prior_dir_loads_empty_but_honest(self):
        with TemporaryDirectory() as td:
            reg = load_leads(Path(td))
            self.assertEqual(reg["status"], "loaded")
            self.assertEqual(reg["date_count"], 0)

    def test_loads_events_from_prior_dir(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "chronology_events.json").write_text(json.dumps({"events": [
                {"date_str": "1999-08-12", "photo_id": "1999_08_12_1",
                 "event_types": ["hard_cut"]},
            ]}), encoding="utf-8")
            reg = load_leads(root)
            self.assertEqual(reg["date_count"], 1)
            self.assertIn("hard_cut", reg["dates"]["1999-08-12"]["events"])


def _date_bucket(priority=4, regions=(), events=(), metrics=()):
    return {"priority": priority, "regions": set(regions), "events": set(events),
            "metrics": set(metrics)}


class PairLeadsTests(unittest.TestCase):
    def test_no_overlap_returns_zero(self):
        reg = {"dates": {"2020-01-01": _date_bucket()}}
        out = pair_leads(reg, "2020-01-05", "2020-06-01")
        self.assertFalse(out["lead_overlap"])
        self.assertEqual(out["lead_priority"], 0)
        self.assertEqual(out["lead_metric_count"], 0)

    def test_overlap_sums_priority_and_joins(self):
        reg = {"dates": {
            "2020-01-01": _date_bucket(priority=4, regions={"orbit"}, events={"hard_cut"}, metrics={"span_lateral"}),
            "2020-06-01": _date_bucket(priority=3, regions={"chin"}, events={"return"}, metrics={"bbox_volume"}),
        }}
        out = pair_leads(reg, "2020-01-01", "2020-06-01")
        self.assertTrue(out["lead_overlap"])
        self.assertEqual(out["lead_priority"], 7)
        self.assertEqual(out["lead_regions"], "chin|orbit")
        self.assertEqual(out["lead_events"], "hard_cut|return")
        self.assertEqual(out["lead_metric_count"], 2)

    def test_single_side_overlap_counts(self):
        reg = {"dates": {"2020-01-01": _date_bucket(priority=4, regions={"orbit"})}}
        out = pair_leads(reg, "2020-01-01", "2020-06-01")
        self.assertTrue(out["lead_overlap"])
        self.assertEqual(out["lead_priority"], 4)

    def test_ignores_dates_not_in_registry(self):
        reg = {"dates": {}}
        out = pair_leads(reg, "2020-01-01", None)
        self.assertFalse(out["lead_overlap"])


if __name__ == "__main__":
    unittest.main()