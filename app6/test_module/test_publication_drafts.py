import json
import tempfile
import unittest
from pathlib import Path

from app6.api.report import resolve_publication_draft
from app6.stage2.postprocess_reports import build_journalist_handoff
from app6.stage3 import Stage3Config, Stage3Engine
from app6.stage3.publication_drafts import (
    ASSERTIVE_FORBIDDEN_PATTERNS,
    build_publication_bundle,
    write_publication_drafts,
)


class JournalistHandoffTests(unittest.TestCase):
    def test_handoff_keeps_denominators_and_evidence_refs(self) -> None:
        rows = [
            {
                "pair_id": "adjacent__a__b",
                "pair_type": "adjacent",
                "photo_a": "a",
                "photo_b": "b",
                "date_a": "2010-01-01",
                "date_b": "2010-02-01",
                "pose_bin": "frontal",
                "evidence_state": "persistent_geometric_change",
                "status": "persistent_geometric_change",
                "p95_point_z": 5.2,
                "calibrated_point_count": 91,
                "matched_calibration_sets": 7,
                "quality_limited": False,
                "calibration_limited": False,
                "pose_leakage_limited": False,
                "date_provenance_limited": False,
                "near_duplicate_pair": False,
                "source_provenance_status_a": "provided",
                "source_provenance_status_b": "provided",
                "common_visible134": 100,
                "pose_distance": 0.5,
            }
        ]
        changes = [
            {
                "pair_id": "adjacent__a__b",
                "pair_type": "adjacent",
                "photo_a": "a",
                "photo_b": "b",
                "date": "2010-02-01",
                "pose_bin": "frontal",
                "evidence_state": "persistent_geometric_change",
                "p95_point_z": 5.2,
            }
        ]
        handoff = build_journalist_handoff(rows, changes)
        self.assertTrue(handoff["draft"])
        self.assertTrue(handoff["not_a_verdict"])
        self.assertEqual(handoff["counts"]["adjacent_pair_count"], 1)
        self.assertEqual(handoff["counts"]["reportable_candidate_count"], 1)
        card = handoff["candidate_cards"][0]
        self.assertEqual(card["calibrated_point_count"], 91)
        self.assertIn("pair_metrics.csv#pair_id=adjacent__a__b", card["evidence_refs"])


class PublicationDraftTests(unittest.TestCase):
    def _report_data(self, change_count: int = 1) -> dict:
        changes = []
        if change_count:
            changes.append(
                {
                    "pair_id": "adjacent__a__b",
                    "photo_a": "a",
                    "photo_b": "b",
                    "date": "2010-02-01",
                    "pose_bin": "frontal",
                    "evidence_state": "persistent_geometric_change",
                    "p95_point_z": 5.2,
                    "days_delta": 31,
                }
            )
        return {
            "schema_version": "deeputin-stage3-test",
            "analysis_manifest": {
                "schema_version": "deeputin-stage2-test",
                "created_at_utc": "2026-08-05T00:00:00Z",
                "main_record_count": 126,
                "calibration_dataset_count": 7,
            },
            "summary": {
                "pair_count": 300,
                "change_count": change_count,
                "pose_counts": {"frontal": 40},
                "provenance": {
                    "date_conflict_pair_count": 2,
                    "near_duplicate_pair_count": 3,
                    "source_chain_incomplete_pair_count": 4,
                },
            },
            "change_points": changes,
        }

    def test_bundle_has_four_audiences_and_machine_claims(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = build_publication_bundle(self._report_data(), root)
        self.assertEqual(
            set(bundle["audiences"]),
            {"general", "technical", "skeptical", "machine_review"},
        )
        self.assertTrue(bundle["draft"])
        self.assertTrue(bundle["not_a_verdict"])
        self.assertGreaterEqual(len(bundle["claims"]), 7)
        for claim in bundle["claims"]:
            self.assertTrue(claim["evidence_refs"])
            self.assertEqual(claim["review_state"], "unreviewed_draft")

    def test_write_creates_reviewable_drafts_and_passes_assertive_lint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "stage3"
            analysis = Path(td) / "stage2"
            out.mkdir()
            analysis.mkdir()
            (analysis / "journalist_handoff.json").write_text(
                json.dumps(
                    {
                        "counts": {
                            "adjacent_pair_count": 100,
                            "limited_adjacent_pairs": {
                                "quality": 10,
                                "calibration": 5,
                                "pose_leakage": 2,
                            },
                        },
                        "candidate_cards": [],
                    }
                ),
                encoding="utf-8",
            )
            manifest = write_publication_drafts(out, self._report_data(), analysis)
            self.assertEqual(manifest["lint_status"], "pass")
            self.assertEqual(manifest["claim_count"], 7)
            expected = {
                "README.md",
                "01_METHOD_EXPLAINER_PUBLIC.md",
                "02_METHOD_TECHNICAL_APPENDIX.md",
                "03_RESULTS_STORY_DRAFT.md",
                "04_SKEPTIC_QA.md",
                "05_EXAMPLE_DEMONSTRATION_PROTOCOL.md",
                "publication_bundle.json",
                "claims_ledger.json",
                "machine_review_packet.json",
                "glossary.json",
                "draft_lint.json",
            }
            self.assertEqual({path.name for path in (out / "drafts").iterdir()}, expected)
            text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (out / "drafts").glob("*.md")
            ).lower()
            for pattern in ASSERTIVE_FORBIDDEN_PATTERNS:
                self.assertNotIn(pattern, text)

            report_data = self._report_data()
            report_data["publication_drafts"] = manifest
            (out / "report_data.json").write_text(json.dumps(report_data), encoding="utf-8")
            resolved, media_type = resolve_publication_draft(out, "03_RESULTS_STORY_DRAFT.md")
            self.assertEqual(resolved.name, "03_RESULTS_STORY_DRAFT.md")
            self.assertEqual(media_type, "text/markdown")
            with self.assertRaises((KeyError, ValueError)):
                resolve_publication_draft(out, "../report_data.json")

    def test_zero_candidates_is_not_worded_as_proof_of_absence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bundle = build_publication_bundle(self._report_data(change_count=0), Path(td))
        claim = next(item for item in bundle["claims"] if item["claim_id"] == "RESULT-002")
        self.assertIn("не выделила кандидатов", claim["plain_language"])
        self.assertTrue(any("не доказывает отсутствие" in item for item in claim["limitations"]))

    def test_stage3_writes_publication_package(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            analysis = root / "stage2"
            output = root / "stage3"
            analysis.mkdir()
            (analysis / "analysis_validation.json").write_text(
                json.dumps({"status": "complete", "errors": []}), encoding="utf-8"
            )
            (analysis / "analysis_manifest.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "schema_version": "stage2-test",
                        "created_at_utc": "2026-08-05T00:00:00Z",
                        "main_record_count": 0,
                        "calibration_dataset_count": 7,
                        "descriptor_family_count": 13,
                    }
                ),
                encoding="utf-8",
            )
            (analysis / "pair_metrics.csv").write_text("status\nno_pairs\n", encoding="utf-8")
            (analysis / "zone_metrics.csv").write_text("status\nno_zones\n", encoding="utf-8")
            (analysis / "change_points.json").write_text(
                json.dumps({"change_points": []}), encoding="utf-8"
            )
            validation = Stage3Engine(Stage3Config(analysis, output)).run()
            self.assertEqual(validation["status"], "complete")
            self.assertEqual(validation["publication_drafts"]["lint_status"], "pass")
            report = json.loads((output / "report_data.json").read_text(encoding="utf-8"))
            self.assertTrue(report["publication_drafts"]["human_review_required"])
            self.assertTrue((output / "drafts" / "machine_review_packet.json").is_file())


if __name__ == "__main__":
    unittest.main()
