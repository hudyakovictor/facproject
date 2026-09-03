import unittest
import csv
import json
from inspect import getdoc
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from app6.run_stage2 import build_parser
from app6.run_stage2b import build_parser as build_stage2b_parser
from app6.stage2.core import compare_landmarks
from app6.stage2.engine import Stage2Engine
from app6.stage2.engine import _pair_qc_decision
from app6.stage2.loaders import load_main
from app6.stage2.motion import aligned_point_motion
from app6.stage2b import Stage2BConfig
class R:
 def __init__(self,i,date):self.record_id=i;self.date=date
class SelectedPatchRegressions(unittest.TestCase):
 def test_jaw_mismatch_reaches_era_gate(self):
  q={"a":{"status":"available","alignment_quality":.8,"jaw_open_detected":True},"b":{"status":"available","alignment_quality":.8,"jaw_open_detected":False}}
  self.assertTrue(_pair_qc_decision(R("a","2001-01-01"),R("b","2006-01-01"),q)["applicable"])

 def test_stage2_cli_accepts_project_root(self):
  args=build_parser().parse_args([
   "--project-root","/tmp/deeputin",
   "--stage1","stage1","--calibration","calibration","--output","stage2",
  ])
  self.assertEqual(args.project_root,Path("/tmp/deeputin"))

 def test_stage2_engine_documents_raw_primary_geometry(self):
  docs=(
   Stage2Engine.run.__doc__ or "",
   compare_landmarks.__doc__ or "",
   load_main.__doc__ or "",
   aligned_point_motion.__doc__ or "",
  )
  for doc in docs:
   self.assertIn("raw object-normalized",doc)
   self.assertNotIn("ДОЛЖЕН быть chronology-aligned",doc)
   self.assertNotIn("Требует chronology-aligned landmarks",doc)

 def test_stage2_modules_do_not_claim_chronology_primary_or_fallback(self):
  from app6.stage2 import core
  core_doc=getdoc(core) or ""
  load_main_doc=getdoc(load_main) or ""
  self.assertIn("raw object-normalized",core_doc)
  self.assertNotIn("ldm*_chronology",core_doc)
  self.assertNotIn("fallback к старым данным",load_main_doc)

 def test_stage2b_project_root_is_part_of_config_contract(self):
  args=build_stage2b_parser().parse_args([
   "--project-root","/tmp/deeputin",
   "--stage2","stage2","--output","stage2b",
  ])
  cfg=Stage2BConfig(
   stage2_root=args.stage2,
   output_dir=args.output,
   project_root=args.project_root,
  )
  expected=Path("/tmp/deeputin").resolve()
  self.assertEqual(cfg.project_root,expected)
  self.assertEqual(cfg.payload()["project_root"],str(expected))

 def test_load_main_reports_corrupt_npz_with_record_context(self):
  with TemporaryDirectory() as td:
   root=Path(td);record_id="broken-photo";record=root/record_id;record.mkdir()
   with (root/"main_timeline.csv").open("w",newline="",encoding="utf-8") as stream:
    writer=csv.DictWriter(stream,fieldnames=["photo_id","date","same_date_sequence","pose_bin"])
    writer.writeheader();writer.writerow({"photo_id":record_id,"date":"2020-01-01","same_date_sequence":0,"pose_bin":"frontal"})
   (record/"validation.json").write_text(json.dumps({"status":"complete"}),encoding="utf-8")
   (record/"info.json").write_text(json.dumps({"source_relative_path":"2020_01_01.jpg"}),encoding="utf-8")
   (record/"texture.json").write_text(json.dumps({"quality":{}}),encoding="utf-8")
   (record/"reconstruction.npz").write_bytes(b"not-an-npz")
   with self.assertRaisesRegex(ValueError,"broken-photo.*reconstruction\\.npz"):
    load_main(root)

 def test_load_main_reports_empty_npz_with_record_context(self):
  with TemporaryDirectory() as td:
   root=Path(td);record_id="empty-npz";record=root/record_id;record.mkdir()
   with (root/"main_timeline.csv").open("w",newline="",encoding="utf-8") as stream:
    writer=csv.DictWriter(stream,fieldnames=["photo_id","date","same_date_sequence","pose_bin"])
    writer.writeheader();writer.writerow({"photo_id":record_id,"date":"2020-01-01","same_date_sequence":0,"pose_bin":"frontal"})
   (record/"validation.json").write_text(json.dumps({"status":"complete"}),encoding="utf-8")
   (record/"info.json").write_text(json.dumps({"source_relative_path":"2020_01_01.jpg"}),encoding="utf-8")
   (record/"texture.json").write_text(json.dumps({"quality":{}}),encoding="utf-8")
   (record/"reconstruction.npz").write_bytes(b"")
   with self.assertRaisesRegex(ValueError,"empty-npz.*reconstruction\\.npz"):
    load_main(root)

 def test_load_main_reports_missing_required_npz_key_with_record_context(self):
  with TemporaryDirectory() as td:
   root=Path(td);record_id="missing-key";record=root/record_id;record.mkdir()
   with (root/"main_timeline.csv").open("w",newline="",encoding="utf-8") as stream:
    writer=csv.DictWriter(stream,fieldnames=["photo_id","date","same_date_sequence","pose_bin"])
    writer.writeheader();writer.writerow({"photo_id":record_id,"date":"2020-01-01","same_date_sequence":0,"pose_bin":"frontal"})
   (record/"validation.json").write_text(json.dumps({"status":"complete"}),encoding="utf-8")
   (record/"info.json").write_text(json.dumps({"source_relative_path":"2020_01_01.jpg"}),encoding="utf-8")
   (record/"texture.json").write_text(json.dumps({"quality":{}}),encoding="utf-8")
   np.savez(record/"reconstruction.npz",ldm106_vertex_indices=np.arange(106),ldm134_vertex_indices=np.arange(134))
   with self.assertRaisesRegex(ValueError,"missing-key.*ldm106_object_normalized"):
    load_main(root)
if __name__=="__main__":unittest.main()
