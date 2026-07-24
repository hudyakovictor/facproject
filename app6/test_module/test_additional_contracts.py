"""Regression coverage added by the 50-check implementation audit."""
from __future__ import annotations
import csv, json, tempfile, unittest
from pathlib import Path
import numpy as np
from app6.stage1.assets import _bbox, _letterbox, technical_quality
from app6.stage1.config import Stage1Config
from app6.stage1.engine import _landmark_rows
from app6.stage1.geometry import classify_pose, pack_mask, unpack_mask
from app6.stage1.naming import parse_photo_name
from app6.stage1.utils import atomic_json, sha256_paths, write_csv
from app6.stage2.baseline_return import _reversal_stats
from app6.stage2.core import robust_rigid_align
from app6.stage2.evidence import alternative_reasons, evidence_state
from app6.stage2.multiple_testing import apply_pair_fdr, apply_zone_fdr
from app6.stage2b.engine import Stage2BConfig, Stage2BEngine
from app6.stage3.engine import Stage3Config, Stage3Engine

class AdditionalContractTest(unittest.TestCase):
 def test_config_rejects_output_inside_input(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp)
   with self.assertRaisesRegex(ValueError,"inside input_dir"): Stage1Config(r,r/"photos",r/"photos"/"out")
 def test_config_rejects_negative_limit(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp)
   with self.assertRaisesRegex(ValueError,"non-negative"): Stage1Config(r,r/"photos",r/"out",limit=-1)
 def test_pose_classifier_rejects_nan(self):
  with self.assertRaises(ValueError): classify_pose(float("nan"))
 def test_mask_pack_requires_vector(self):
  with self.assertRaises(ValueError): pack_mask(np.zeros((2,2),bool))
 def test_mask_unpack_rejects_short_payload(self):
  with self.assertRaises(ValueError): unpack_mask(np.zeros(1,np.uint8),9)
 def test_robust_alignment_requires_three_finite_points(self):
  a=np.zeros((2,3),np.float32)
  with self.assertRaisesRegex(ValueError,"at least 3"): robust_rigid_align(a,a)
 def test_compact_date_filename_is_rejected(self):
  with self.assertRaises(ValueError): parse_photo_name(Path("20260724.jpg"))
 def test_bbox_rejects_nonfinite_points(self):
  with self.assertRaises(ValueError): _bbox(np.array([[0,0],[1,1],[np.nan,2]],np.float32),(100,100,3))
 def test_letterbox_rejects_empty_image(self):
  with self.assertRaises(ValueError): _letterbox(np.empty((0,10,3),np.uint8))
 def test_technical_quality_rejects_empty_bbox(self):
  with self.assertRaises(ValueError): technical_quality(np.zeros((10,10,3),np.uint8),[0,0,0,1],None,np.ones(3))
 def test_landmark_rows_reject_length_mismatch(self):
  with self.assertRaises(ValueError): _landmark_rows(np.zeros((3,3)),np.ones(2),np.arange(3))
 def test_atomic_writers_replace_complete_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp); atomic_json(r/"a.json",{"x":np.float32(1)}); write_csv(r/"a.csv",[{"x":1},{"x":2}])
   self.assertEqual(json.loads((r/"a.json").read_text())["x"],1.0)
   with (r/"a.csv").open(newline="") as f:self.assertEqual(len(list(csv.DictReader(f))),2)
   self.assertFalse(list(r.glob("*.tmp")))
 def test_sha256_paths_rejects_empty_input(self):
  with self.assertRaises(ValueError): sha256_paths([])
 def test_fdr_skips_nonfinite_values(self):
  rows=[{"p95_point_z":float("nan"),"calibrated_point_count":134}]
  self.assertEqual(apply_pair_fdr(rows)["test_count"],0)
  self.assertEqual(apply_zone_fdr([{"status":"measured","robust_z":float("inf")}])["test_count"],0)
 def test_reversal_stats_rejects_shape_mismatch(self):
  self.assertEqual(_reversal_stats(np.zeros((10,3)),np.zeros((11,3)))["common_vector_count"],0)
 def test_evidence_maps_inapplicable_pose(self):
  self.assertEqual(evidence_state("pose_mismatch"),"inapplicable_pose");self.assertEqual(evidence_state("residual_pose_mismatch"),"inapplicable_pose")
 def test_expected_rate_is_not_an_alternative_reason(self):
  self.assertNotIn("short_interval_rate_flag_requires_review",alternative_reasons({"biological_rate_status":"within_expected_rate"}))
 def test_stage3_rejects_unvalidated_stage2(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);a=r/"analysis";a.mkdir()
   with self.assertRaisesRegex(RuntimeError,"not valid"):Stage3Engine(Stage3Config(a,r/"report")).run()
   self.assertFalse((r/"report").exists())
 def test_stage2b_requires_validation_file(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);s=r/"stage2";s.mkdir();(s/"analysis_manifest.json").write_text("{}");(s/"evidence_packets.json").write_text('{"packets": []}')
   with self.assertRaises(FileNotFoundError):Stage2BEngine(Stage2BConfig(s,r/"out")).run()
   self.assertFalse((r/"out").exists())
if __name__=="__main__":unittest.main()
