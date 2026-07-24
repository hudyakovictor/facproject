"""Regression contracts for transactional preflight and public status projection."""
from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from app6.stage1.config import Stage1Config
from app6.stage1.engine import Stage1Engine
from app6.stage1 import evidence as legacy_evidence
from app6.stage2.engine import Stage2Config,Stage2Engine
from app6.stage2.evidence import EVIDENCE_SCHEMA
from app6.stage2b.engine import Stage2BConfig,Stage2BEngine
from app6.stage3.engine import Stage3Config,Stage3Engine,public_pair_projection

class Iteration4TransactionContractTest(unittest.TestCase):
 def test_stage2_rejects_output_inside_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp)
   with self.assertRaisesRegex(ValueError,'inside stage1_root'):Stage2Config(r/'s1',r/'cal',r/'s1'/'out')
 def test_stage2b_rejects_output_inside_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp)
   with self.assertRaisesRegex(ValueError,'inside stage2_root'):Stage2BConfig(r/'s2',r/'s2'/'out')
 def test_stage3_rejects_output_inside_source(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp)
   with self.assertRaisesRegex(ValueError,'inside analysis_root'):Stage3Config(r/'analysis',r/'analysis'/'report')
 def test_public_projection_uses_evidence_state(self):
  row=public_pair_projection({'status':'persistent_geometric_change','evidence_state':'calibration_limited','texture_image_status':'measured'})
  self.assertEqual(row['measurement_status'],'persistent_geometric_change')
  self.assertEqual(row['status'],'calibration_limited')
  self.assertNotIn('texture_image_status',row)
 def test_evidence_schema_and_legacy_shim_are_synchronized(self):
  self.assertEqual(EVIDENCE_SCHEMA,'deeputin-stage2-evidence-v1.1')
  self.assertEqual(legacy_evidence.EVIDENCE_SCHEMA,EVIDENCE_SCHEMA)
  self.assertIs(legacy_evidence.evidence_state,__import__('app6.stage2.evidence',fromlist=['evidence_state']).evidence_state)
 def test_stage1_preflight_does_not_create_output_on_missing_assets(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);inp=r/'photos';inp.mkdir();out=r/'out'
   cfg=Stage1Config(r,inp,out)
   with self.assertRaises(FileNotFoundError):Stage1Engine(cfg)
   self.assertFalse(out.exists())
 def test_stage2_failed_preflight_preserves_existing_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);out=r/'out';out.mkdir();sentinel=out/'keep.txt';sentinel.write_text('keep')
   cfg=Stage2Config(r/'missing_stage1',r/'missing_calibration',out,overwrite=True)
   with self.assertRaises(Exception):Stage2Engine(cfg).run()
   self.assertEqual(sentinel.read_text(),'keep')
 def test_stage2b_invalid_manifest_preserves_existing_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);s=r/'stage2';s.mkdir();out=r/'out';out.mkdir();sentinel=out/'keep.txt';sentinel.write_text('keep')
   (s/'analysis_validation.json').write_text(json.dumps({'status':'complete'}));(s/'analysis_manifest.json').write_text(json.dumps({'status':'invalid'}));(s/'evidence_packets.json').write_text(json.dumps({'schema':EVIDENCE_SCHEMA,'packets':[]}))
   with self.assertRaisesRegex(RuntimeError,'manifest is not complete'):Stage2BEngine(Stage2BConfig(s,out,overwrite=True)).run()
   self.assertEqual(sentinel.read_text(),'keep')
 def test_stage3_missing_manifest_preserves_existing_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);a=r/'analysis';a.mkdir();out=r/'out';out.mkdir();sentinel=out/'keep.txt';sentinel.write_text('keep')
   (a/'analysis_validation.json').write_text(json.dumps({'status':'complete'}))
   with self.assertRaises(FileNotFoundError):Stage3Engine(Stage3Config(a,out,overwrite=True)).run()
   self.assertEqual(sentinel.read_text(),'keep')
if __name__=='__main__':unittest.main()
