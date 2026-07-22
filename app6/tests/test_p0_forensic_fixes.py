"""🔄 CALLBACK (pytest) → регрессии P0-фиксов форензик-слоя (evidence gates).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from app6.stage2.alpha_chronology import apply_alpha_chronology
from app6.stage2.chronology import apply_chronology_rate_flags
from app6.stage2.core import Record, compare_landmarks
from app6.stage2.evidence import STATUS_TO_EVIDENCE_STATE, evidence_state
from app6.stage2.loaders import load_calibration, load_calibration_from_sidecar
from app6.stage2.motion import pose_motion_support
from app6.stage2.multiple_testing import apply_pair_fdr
from app6.stage2.texture_image import _glcm_stats, _load_texture, _stats


class _FakeAlphaModel:
    def reference(self, pose: str, key: str):
        return {"median": 0.1, "mad": 0.05, "p95": 0.3, "count": 20}


class P0ForensicFixesTests(unittest.TestCase):
    def test_evidence_jump_is_not_persistent(self):
        self.assertEqual(
            STATUS_TO_EVIDENCE_STATE["coherent_jump_candidate"],
            "coherent_jump_candidate",
        )
        self.assertEqual(evidence_state("coherent_jump_candidate"), "coherent_jump_candidate")

    def test_chronology_date_missing_not_eff_one(self):
        rows = [
            {
                "pair_type": "adjacent",
                "pose_bin": "frontal",
                "pair_index": 1,
                "date_a": None,
                "date_b": "2020-01-01",
                "p95_point_z": 5.0,
                "coherent_motion_fraction": 0.5,
                "significant_point_fraction": 0.2,
                "status": "coherent_jump_candidate",
            },
            {
                "pair_type": "adjacent",
                "pose_bin": "frontal",
                "pair_index": 2,
                "date_a": "2020-01-01",
                "date_b": "2020-02-01",
                "p95_point_z": 1.0,
                "coherent_motion_fraction": 0.1,
                "significant_point_fraction": 0.01,
                "status": "within_reconstruction_noise",
            },
        ]
        apply_chronology_rate_flags(rows)
        self.assertEqual(rows[0]["chronology_rate_status"], "date_missing")
        self.assertIsNone(rows[0]["days_delta"])
        self.assertEqual(rows[0].get("date_status"), "date_missing")
        self.assertEqual(rows[1]["days_delta"], 31)

    def test_alpha_l2_nan_when_missing(self):
        rng = np.random.default_rng(0)
        a = Record(
            "a",
            "d",
            None,
            0,
            "frontal",
            np.zeros(3, np.float32),
            rng.normal(size=(106, 3)).astype(np.float32),
            rng.normal(size=(134, 3)).astype(np.float32),
            np.ones(106, bool),
            np.ones(134, bool),
            np.full(80, np.nan, np.float32),
            np.full(64, np.nan, np.float32),
        )
        b = Record(
            "b",
            "d",
            None,
            1,
            "frontal",
            np.zeros(3, np.float32),
            a.ldm106 + 0.01,
            a.ldm134 + 0.01,
            np.ones(106, bool),
            np.ones(134, bool),
            np.full(80, np.nan, np.float32),
            np.full(64, np.nan, np.float32),
        )
        comp = compare_landmarks(a, b, np.zeros(106, np.int32), np.zeros(134, np.int32))
        self.assertFalse(np.isfinite(comp.metrics["alpha_id_l2"]))
        self.assertFalse(np.isfinite(comp.metrics["alpha_exp_l2"]))

    def test_alpha_chronology_skips_nan(self):
        rows = [{"pose_bin": "frontal", "alpha_id_l2": float("nan"), "alpha_exp_l2": float("nan")}]
        apply_alpha_chronology(rows, _FakeAlphaModel())
        self.assertEqual(rows[0]["alpha_channel_status"], "disabled_or_missing")
        self.assertEqual(rows[0]["alpha_id_status"], "unavailable")

    def test_fdr_is_diagnostic_only(self):
        rows = [{"p95_point_z": 4.0}, {"p95_point_z": 0.5}]
        report = apply_pair_fdr(rows)
        self.assertTrue(report.get("diagnostic_only"))
        self.assertTrue(report.get("not_a_verdict"))
        self.assertEqual(rows[0].get("mt_role"), "diagnostic_only")
        self.assertIn("mt_fdr10_diagnostic_flag", rows[0])

    def test_profile_support_gate(self):
        self.assertEqual(pose_motion_support("left_profile"), "profile_limited")
        self.assertEqual(pose_motion_support("frontal"), "supported")
        self.assertEqual(pose_motion_support("out_of_supported_range"), "unsupported_pose")

    def test_glcm_uses_masked_pairs_not_median_fill(self):
        # Source must keep skimage median-fill path disabled.
        src = Path(__file__).resolve().parents[1] / "stage2" / "texture_image.py"
        text = src.read_text(encoding="utf-8")
        self.assertIn("if False and _HAS_SKIMAGE", text)
        rng = np.random.default_rng(1)
        gray = rng.integers(0, 255, (64, 64), np.uint8)
        mask = np.zeros((64, 64), bool)
        mask[16:48, 16:48] = True
        stats = _glcm_stats(gray, mask)
        for k in ("glcm_contrast", "glcm_homogeneity", "glcm_energy", "glcm_correlation"):
            self.assertTrue(np.isfinite(stats[k]), k)

    def test_texture_face_mask_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            img = np.full((80, 80, 3), 120, np.uint8)
            cv2.imwrite(str(d / "original.png"), img)
            mask = np.zeros((80, 80), np.uint8)
            mask[10:70, 10:70] = 255
            cv2.imwrite(str(d / "face_mask.png"), mask)
            (d / "info.json").write_text(
                json.dumps({"files": {"original": "original.png"}}),
                encoding="utf-8",
            )

            class R:
                record_dir = str(d)

            loaded = _load_texture(R())
            self.assertEqual(loaded["status"], "ok")
            self.assertEqual(loaded.get("texture_mask_source"), "face_mask")
            self.assertIn("face_mask_full", loaded["masks"])

    def test_sidecar_loader_on_archive_sample(self):
        root = Path(__file__).resolve().parents[2] / "calibration_dataset"
        if not root.is_dir():
            self.skipTest("calibration_dataset not mounted")
        nested = root / "calibration_datasets"
        if not nested.is_dir():
            self.skipTest("no calibration data")

        # Test the sidecar loader directly (bypasses record.npz path)
        recs = load_calibration_from_sidecar(nested)
        self.assertGreaterEqual(len(recs), 1)
        r0 = recs[0]
        self.assertEqual(r0.ldm106.shape, (106, 3))
        self.assertEqual(r0.ldm134.shape, (134, 3))
        # Sidecar has no alpha → NaN vectors
        self.assertTrue(np.isnan(r0.alpha_id).all())
        # Space QA: normalized landmarks should be O(1), not raw mesh units >> 10
        rms = float(np.sqrt(np.nanmean(np.sum(r0.ldm134.astype(np.float64) ** 2, axis=1))))
        self.assertLess(rms, 5.0)
        self.assertGreater(rms, 0.05)


if __name__ == "__main__":
    unittest.main()
