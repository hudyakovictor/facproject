from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from app6.api.selection_filters import (
    DEFAULT_FILTER_STATE,
    build_selection_manifest,
    evaluate_selection,
    save_selection_manifest,
)
from app6.api.stage1_timeline import build_stage1_inventory
from app6.api.runtime_config import load_runtime_paths
import os
from unittest import mock


def _photo(pid: str, **kwargs):
    base = {
        "id": pid,
        "bucket": "frontal",
        "yaw": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "visibility": 0.9,
        "quality": 0.9,
        "confidence": 0.8,
        "faceResolution": 0.2,
        "blur": 100.0,
        "exposure": 0.7,
        "alignmentQuality": 0.9,
        "landmarkVisibility": 0.95,
        "textureApplicability": 0.8,
        "expressionMagnitude": 0.1,
        "jawOpenRatio": 0.05,
        "smileScore": 0.01,
        "smileDetected": False,
        "jawOpenDetected": False,
        "dateProvenanceStatus": "verified",
        "exifAnomaly": False,
        "near_duplicate_of": None,
        "sourceProvenanceStatus": "available",
    }
    base.update(kwargs)
    return base


class IterationThreeSelectionTests(unittest.TestCase):
    def test_quality_range_excludes_with_reason(self):
        photos = [
            _photo("a", visibility=0.95),
            _photo("b", visibility=0.2),
            _photo("c", visibility=0.7),
        ]
        state = json.loads(json.dumps(DEFAULT_FILTER_STATE))
        state["enabled"]["visibility"] = True
        state["ranges"]["visibility"] = {"min": 0.5, "max": 1.0}
        result = evaluate_selection(photos, state)
        self.assertEqual(result["included_count"], 2)
        self.assertEqual(result["excluded_count"], 1)
        self.assertIn("b", result["excluded_ids"])
        reasons = {d["photo_id"]: d["reasons"] for d in result["decisions"]}
        self.assertTrue(any(r.startswith("visibility:") for r in reasons["b"]))
        self.assertFalse(result.get("mutates_stage1", False))

    def test_pose_outlier_master_percentile(self):
        photos = []
        for i, yaw in enumerate([0, 1, -1, 2, -2, 25]):
            photos.append(_photo(f"p{i}", yaw=float(yaw), pitch=0.0, roll=0.0))
        state = json.loads(json.dumps(DEFAULT_FILTER_STATE))
        state["poseOutlier"]["enabled"] = True
        state["poseOutlier"]["masterPercentile"] = 80.0
        result = evaluate_selection(photos, state)
        self.assertLess(result["excluded_count"], len(photos))
        self.assertGreaterEqual(result["excluded_count"], 1)
        # extreme yaw should be among excluded
        self.assertIn("p5", result["excluded_ids"])

    def test_boolean_smile_and_date_conflict(self):
        photos = [
            _photo("ok"),
            _photo("smile", smileDetected=True),
            _photo("conflict", dateProvenanceStatus="conflict", exifAnomaly=True),
        ]
        state = json.loads(json.dumps(DEFAULT_FILTER_STATE))
        state["booleans"]["excludeSmileDetected"] = True
        state["booleans"]["excludeDateConflict"] = True
        result = evaluate_selection(photos, state)
        self.assertEqual(set(result["excluded_ids"]), {"smile", "conflict"})
        self.assertEqual(result["included_ids"], ["ok"])

    def test_manual_include_overrides_auto_exclude(self):
        photos = [_photo("x", visibility=0.1), _photo("y", visibility=0.9)]
        state = json.loads(json.dumps(DEFAULT_FILTER_STATE))
        state["enabled"]["visibility"] = True
        state["ranges"]["visibility"] = {"min": 0.5, "max": 1.0}
        state["manualInclude"] = ["x"]
        result = evaluate_selection(photos, state)
        self.assertIn("x", result["included_ids"])

    def test_selection_manifest_saved_outside_stage1(self):
        photos = [_photo("a"), _photo("b", visibility=0.1)]
        state = json.loads(json.dumps(DEFAULT_FILTER_STATE))
        state["enabled"]["visibility"] = True
        state["ranges"]["visibility"] = {"min": 0.5, "max": 1.0}
        with tempfile.TemporaryDirectory() as tmp:
            storage = Path(tmp) / "storage"
            stage1 = storage / "stage1"
            stage1.mkdir(parents=True)
            env = {
                "DEEPUTIN_STORAGE_ROOT": str(storage),
                "DEEPUTIN_STAGE1_ROOT": str(stage1),
                "DEEPUTIN_CALIBRATION_ROOT": str(Path(tmp) / "cal"),
            }
            with mock.patch.dict(os.environ, env, clear=False):
                manifest = build_selection_manifest(photos, state, label="t", stage1_root=str(stage1))
                path = save_selection_manifest(manifest)
                self.assertTrue(path.is_file())
                self.assertIn("profiles", str(path))
                self.assertEqual(list(stage1.iterdir()), [])
                loaded = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(loaded["excluded_count"], 1)
                self.assertTrue(loaded["immutable_stage1"])

    def test_stage1_timeline_enrichment_from_info_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "stage1"
            root.mkdir()
            photo_id = "1999_01_01__a"
            fields = ["photo_id", "date", "pose_bin", "combined_visible_fraction", "yaw", "pitch", "roll", "skin_mask_coverage", "uv_observed_coverage", "date_provenance_status"]
            with (root / "main_timeline.csv").open("w", newline="", encoding="utf-8") as stream:
                w = csv.DictWriter(stream, fieldnames=fields)
                w.writeheader()
                w.writerow({"photo_id": photo_id, "date": "1999-01-01", "pose_bin": "frontal", "combined_visible_fraction": "0.88", "yaw": "1", "pitch": "0", "roll": "0", "skin_mask_coverage": "0.7", "uv_observed_coverage": "0.6", "date_provenance_status": "verified"})
            folder = root / photo_id
            folder.mkdir()
            info = {
                "quality_inputs": {"combined_visible_fraction": 0.88, "laplacian_variance": 120.0, "face_bbox_area_ratio": 0.15, "skin_mask_coverage": 0.7, "uv_observed_coverage": 0.6},
                "chronology": {
                    "alignment_quality": 0.91,
                    "expression_magnitude": 0.2,
                    "jaw_open_ratio": 0.04,
                    "corner_lift_ioc": 0.01,
                    "smile_detected": False,
                    "jaw_open_detected": False,
                    "pose_confidence": 0.85,
                    "visible_landmarks_106": 100,
                    "reprojection_p95": 0.02,
                },
                "skin_quality_status": "pass",
                "skin_authenticity_score": 0.4,
            }
            (folder / "info.json").write_text(json.dumps(info), encoding="utf-8")
            payload = build_stage1_inventory(root)
            row = payload["photos"][0]
            self.assertEqual(payload["enriched_info_count"], 1)
            self.assertAlmostEqual(row["blur"], 120.0)
            self.assertAlmostEqual(row["alignmentQuality"], 0.91)
            self.assertAlmostEqual(row["landmarkVisibility"], 100 / 106)
            self.assertEqual(row["smileDetected"], False)


if __name__ == "__main__":
    unittest.main()
