"""🎯 GUARD → Техсводка и манифест прогона (ER-158, волна сводок).

technical_summary: честные счётчики, событийная/evidence-агрегация, декларация
texture как visualization-only (не evidence-канал).
run_manifest: хеши артефактов, готовность и обязательная декларация зависимости —
воспроизводимость прогона (D-029, C-критерий готовности).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app6.stage2.run_manifest import TRACKED_ARTIFACTS, artifact_hashes, build_manifest
from app6.stage2.technical_summary import build_technical_summary


ROW = {
    "status": "coherent_jump_candidate", "evidence_state": "candidate",
    "quality_limited": False, "calibration_limited": False,
    "pose_leakage_limited": False, "mesh_status": "measured_calibrated",
    "texture_pair_status": "texture_ready",
}


class TechnicalSummaryTests(unittest.TestCase):
    def test_counts_are_honest(self):
        rows = [dict(ROW), dict(ROW, status="within_noise", evidence_state="accepted"),
                dict(ROW, status="excluded", quality_limited=True)]
        out = build_technical_summary(rows, changes=[{"p": 1}, {"p": 2}], manifest={})
        self.assertEqual(out["pair_count"], 3)
        self.assertEqual(out["change_point_count"], 2)
        self.assertEqual(out["status_counts"]["coherent_jump_candidate"], 1)
        self.assertEqual(out["status_counts"]["excluded"], 1)
        # ROW по умолчанию имеет evidence_state="candidate" — сохраняется в 1 и 3.
        self.assertEqual(out["evidence_state_counts"]["candidate"], 2)
        self.assertEqual(out["quality_limited_pair_count"], 1)

    def test_limited_flags_summed(self):
        rows = [dict(ROW, calibration_limited=True),
                dict(ROW, pose_leakage_limited=True)]
        out = build_technical_summary(rows, changes=[], manifest={})
        self.assertEqual(out["calibration_limited_pair_count"], 1)
        self.assertEqual(out["pose_leakage_limited_pair_count"], 1)

    def test_mesh_measured_only_for_measured_states(self):
        rows = [dict(ROW, mesh_status="measured_uncalibrated"),
                dict(ROW, mesh_status="measured_calibrated"),
                dict(ROW, mesh_status="mesh_unavailable"),
                dict(ROW, mesh_status="not_applicable")]
        out = build_technical_summary(rows, changes=[], manifest={})
        self.assertEqual(out["mesh_measured_pair_count"], 2)

    def test_texture_ready_and_visualization_only_declared(self):
        rows = [dict(ROW, texture_pair_status="texture_ready"),
                dict(ROW, texture_pair_status="texture_mismatch")]
        out = build_technical_summary(rows, changes=[], manifest={})
        self.assertEqual(out["texture_ready_pair_count"], 1)
        self.assertIn("visualization", out["texture_policy"])
        self.assertIn("excluded", out["texture_policy"])  # не evidence-канал

    def test_manifest_core_forwarded(self):
        manifest = {"schema_version": "v2", "main_record_count": 12,
                    "calibration_record_count": 3}
        out = build_technical_summary([dict(ROW)], changes=[], manifest=manifest)
        self.assertEqual(out["manifest_core"]["schema_version"], "v2")
        self.assertEqual(out["manifest_core"]["main_record_count"], 12)

    def test_public_safety_observations_only(self):
        out = build_technical_summary([dict(ROW)], changes=[], manifest={})
        self.assertIn("observations only", out["public_safety"])


def _write_artifacts(root: Path) -> None:
    for rel in TRACKED_ARTIFACTS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture-artifact-not-research-data")


class RunManifestTests(unittest.TestCase):
    def test_missing_artifacts_report_none_and_not_ready(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            manifest = build_manifest(root, code_hash="c", config_hash="g", model_hash="m")
            self.assertFalse(manifest["ready"])
            self.assertEqual(set(manifest["missing_artifacts"]), set(TRACKED_ARTIFACTS))
            hashes = artifact_hashes(root)
            self.assertTrue(all(v is None for v in hashes.values()))

    def test_all_artifacts_present_ready(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_artifacts(root)
            manifest = build_manifest(root, code_hash="c", config_hash="g", model_hash="m")
            self.assertTrue(manifest["ready"])
            self.assertEqual(manifest["missing_artifacts"], [])

    def test_hashes_are_deterministic(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _write_artifacts(root)
            self.assertEqual(artifact_hashes(root), artifact_hashes(root))

    def test_dependence_and_space_default_to_not_reported(self):
        with TemporaryDirectory() as td:
            manifest = build_manifest(Path(td), code_hash="c", config_hash="g", model_hash="m")
            self.assertEqual(manifest["dependence"]["status"], "not_reported")
            self.assertEqual(manifest["analysis_space"]["status"], "not_reported")

    def test_explicit_reuse_report_forwarded(self):
        with TemporaryDirectory() as td:
            _write_artifacts(Path(td))
            manifest = build_manifest(
                Path(td), code_hash="c", config_hash="g", model_hash="m",
                reuse_report={"status": "cross_bin_corroboration"},
            )
            self.assertEqual(manifest["dependence"]["status"], "cross_bin_corroboration")

    def test_modules_separate_imported_from_applied(self):
        with TemporaryDirectory() as td:
            modules = {"same_day_gate_v2": {"imported": True, "applied": False}}
            manifest = build_manifest(Path(td), code_hash="c", config_hash="g", model_hash="m", modules=modules)
            self.assertEqual(manifest["modules"], modules)

    def test_required_gates_declared(self):
        with TemporaryDirectory() as td:
            manifest = build_manifest(Path(td), code_hash="c", config_hash="g", model_hash="m")
            self.assertIn("temporal_axis", manifest["gates"])
            self.assertIn("same_day_gate_v2", manifest["gates"])


if __name__ == "__main__":
    unittest.main()