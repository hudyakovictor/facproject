"""🎯 GUARD → Формулировки Stage 2B / AA01 (ER-192).

Совпадение с prior-лидами НЕ является независимым подтверждением: сильный overlap
обозначается `prior_overlap_strong`, а строка «confirmed_independently» больше не
эмитится нигде в выводе Stage 2B.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app6.stage2b import Stage2BConfig, Stage2BEngine


def _write_stage2(root: Path, state: str = "coherent_jump_candidate") -> Path:
    """Создать минимально валидный Stage2 вывод с одним evidence packet."""
    (root / "analysis_manifest.json").write_text(
        json.dumps({"status": "complete", "schema_version": "v1"}), encoding="utf-8")
    (root / "analysis_validation.json").write_text(
        json.dumps({"status": "complete", "errors": []}), encoding="utf-8")
    evidence = {
        "schema": "deeputin-stage2-evidence-v1.1",
        "packets": [
            {
                "pair_id": "p1",
                "evidence_state": state,
                "status": state,
                "pose_bin": "frontal",
                "date_a": "2020-01-01",
                "date_b": "2020-06-01",
                "photo_a": "A",
                "photo_b": "B",
            }
        ],
    }
    (root / "evidence_packets.json").write_text(json.dumps(evidence), encoding="utf-8")
    # Реестр prior лидов: дата A имеет priority >= 4 → сильный overlap.
    (root / "lead_registry.json").write_text(
        json.dumps({"status": "loaded", "dates": {
            "2020-01-01": {"priority": 5, "regions": [], "events": [], "metrics": []},
        }}),
        encoding="utf-8")
    return root


class Stage2BStatusWordingTests(unittest.TestCase):
    def test_strong_overlap_is_prior_overlap_strong_not_confirmed(self):
        with TemporaryDirectory() as td, TemporaryDirectory() as out_td:
            root = Path(td); out = Path(out_td)
            _write_stage2(root)
            cfg = Stage2BConfig(stage2_root=root, output_dir=out)
            Stage2BEngine(cfg).run()
            csv_text = (out / "corroboration_results.csv").read_text(encoding="utf-8")
        self.assertIn("prior_overlap_strong", csv_text)
        self.assertNotIn("confirmed_independently", csv_text)

    def test_strong_overlap_row_carries_explicit_prior_fields(self):
        with TemporaryDirectory() as td, TemporaryDirectory() as out_td:
            root = Path(td); out = Path(out_td)
            _write_stage2(root)
            Stage2BEngine(Stage2BConfig(stage2_root=root, output_dir=out)).run()
            summary = json.loads((out / "private_summary.json").read_text(encoding="utf-8"))
            status_counts = summary["status_counts"]
        self.assertEqual(status_counts.get("prior_overlap_strong", 0), 1)
        self.assertNotIn("confirmed_independently", status_counts)

    def test_no_occurrence_of_confirmed_wording_in_manifest(self):
        with TemporaryDirectory() as td, TemporaryDirectory() as out_td:
            root = Path(td); out = Path(out_td)
            _write_stage2(root)
            Stage2BEngine(Stage2BConfig(stage2_root=root, output_dir=out)).run()
            manifest = (out / "stage2b_manifest.json").read_text(encoding="utf-8")
        self.assertNotIn("confirmed_independently", manifest)


if __name__ == "__main__":
    unittest.main()