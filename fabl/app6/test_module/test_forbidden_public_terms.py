"""🎯 GUARD → Lint запрещённых публичных терминов (R-F02).

FORBIDDEN_PUBLIC_TERMS проверяется в evidence packets — если попадается
запрещённый термин → public_safety_report.json: status=fail, hits не пусты.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app6.stage2.postprocess_reports import (
    write_postprocess_reports,
)


class ForbiddenPublicTermsLintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _min_rows(self):
        # Минимальный набор строк для вызова write_postprocess_reports
        return [
            {
                        "pair_id": "test_pair_1",
                        "status": "measured",
                        "evidence_state": "measured",
                        "mesh_status": "measured_calibrated",
                        "p95_point_z": 1.0,
                        "mesh_max_robust_z": 1.0,
                        "quality_limited": False,
                        "calibration_limited": False,
                        "pose_leakage_limited": False,
                        "mesh_calibration_status": "measured_calibrated",
                        "texture_image_status": "measured",
                        "point_motion_status": "measured",
                    }
        ]

    def _min_evidence(self, text: str):
        return [{"pair_id": "test_pair_1", "summary": text}]

    def test_clean_evidence_passes(self):
        rows = self._min_rows()
        evidence = self._min_evidence("normal description without forbidden terms")
        write_postprocess_reports(self.out, rows=rows, zones=[], mesh_zones=[], texture_zone_rows=[], changes=[], evidence_packets=evidence)
        report_path = self.out / "public_safety_report.json"
        self.assertTrue(report_path.exists())
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["forbidden_term_hit_count"], 0)
        self.assertEqual(report["hits"], [])

    def test_forbidden_term_detected(self):
            for term in ["двойник", "подмена", "силикон", "маска", "другой человек",
                           "double", "impostor", "silicone", "mask", "different person"]:
                with self.subTest(term=term):
                    evidence = self._min_evidence(f"found {term} in analysis")
                    write_postprocess_reports(self.out, rows=self._min_rows(), zones=[], mesh_zones=[], texture_zone_rows=[], changes=[], evidence_packets=evidence)
                    report = json.loads(self.out.joinpath("public_safety_report.json").read_text(encoding="utf-8"))
                    self.assertEqual(report["status"], "fail")
                    self.assertGreater(report["forbidden_term_hit_count"], 0)
                    self.assertTrue(any(h["term"] == term for h in report["hits"]))

    def test_case_insensitive(self):
        rows = self._min_rows()
        evidence = self._min_evidence("Found ДВОЙНИК in text")
        write_postprocess_reports(self.out, rows=rows, zones=[], mesh_zones=[], texture_zone_rows=[], changes=[], evidence_packets=evidence)
        report = json.loads(self.out.joinpath("public_safety_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "fail")
        self.assertTrue(any(h["term"] == "двойник" for h in report["hits"]))


if __name__ == "__main__":
    import unittest
    unittest.main()