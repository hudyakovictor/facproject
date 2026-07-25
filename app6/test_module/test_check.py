"""Регрессия для чекера: sentinel no_pairs не является измеренной парой."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app6.test_module.check import run_checks


class CheckNoPairsRegressionTest(unittest.TestCase):
    def test_no_pairs_sentinel_fails_no_red_pairs(self) -> None:
        manifest = {
            "scenario": {"id": "sentinel-regression", "expect": [{"type": "no_red_pairs"}]},
            "frames": [{"n": 1, "tag": "p05f000001"}, {"n": 2, "tag": "p05f000002"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            (stage2 / "analysis_validation.json").write_text(
                json.dumps({"status": "complete", "errors": []}), encoding="utf-8"
            )
            (stage2 / "pair_metrics.csv").write_text(
                "status,photo_a,photo_b\nno_pairs,,\n", encoding="utf-8"
            )
            (stage2 / "skipped_pairs.csv").write_text(
                "skip_reason,photo_a,photo_b\nexpression_too_strong,p05f000001,p05f000002\n",
                encoding="utf-8",
            )

            result = run_checks(manifest, Path(tmp))

        no_red_pairs = next(item for item in result["checks"] if item["check"] == "no_red_pairs")
        self.assertFalse(result["passed"])
        self.assertFalse(no_red_pairs["ok"])
        self.assertIn("contains no measured pairs", no_red_pairs["detail"])
        self.assertIn("expression_too_strong", no_red_pairs["detail"])

    def test_limited_red_pair_blocks_instead_of_failing(self) -> None:
        manifest = {
            "scenario": {"id": "limited-red", "expect": [{"type": "no_red_pairs"}]},
            "frames": [{"n": 1, "tag": "p05f000001"}, {"n": 2, "tag": "p05f000002"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            stage2 = Path(tmp) / "stage2"
            stage2.mkdir()
            (stage2 / "analysis_validation.json").write_text(
                json.dumps({"status": "complete", "errors": []}), encoding="utf-8"
            )
            (stage2 / "pair_metrics.csv").write_text(
                "status,evidence_state,quality_limited,photo_a,photo_b\n"
                "coherent_jump_candidate,quality_limited,True,p05f000001,p05f000002\n",
                encoding="utf-8",
            )
            (stage2 / "skipped_pairs.csv").write_text(
                "skip_reason,photo_a,photo_b\n", encoding="utf-8"
            )
            result = run_checks(manifest, Path(tmp))

        self.assertEqual(result["outcome"], "blocked")
        self.assertTrue(result["blocked"])
        self.assertFalse(result["passed"])
        no_red = next(item for item in result["checks"] if item["check"] == "no_red_pairs")
        self.assertEqual(no_red["state"], "blocked")


if __name__ == "__main__":
    unittest.main()
