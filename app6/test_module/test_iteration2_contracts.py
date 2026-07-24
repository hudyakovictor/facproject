"""Regression contracts for the second hardening iteration."""
from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from app6.stage2.engine import _record_qc,_pair_qc_decision
from app6.stage2.evidence import evidence_state,alternative_reasons
from app6.stage2.technical_summary import build_technical_summary
from app6.stage2b.engine import WEAK_STATES,NO_SUPPORT_STATES,UNCLASSIFIED_EVIDENCE_STATES

class Iteration2ContractTest(unittest.TestCase):
 def record(self,root:Path,rid:str):
  d=root/rid;d.mkdir();return SimpleNamespace(record_id=rid,record_dir=d)
 def test_missing_info_is_fail_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=self.record(Path(tmp),'a');q=_record_qc(r)
   self.assertEqual(q['status'],'missing_qc');self.assertIsNone(q['alignment_quality'])
 def test_invalid_qc_is_fail_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=self.record(Path(tmp),'a');(r.record_dir/'info.json').write_text('{"chronology":{"alignment_quality":1}}')
   self.assertEqual(_record_qc(r)['reason'],'mandatory_qc_field_missing_or_invalid')
 def test_valid_qc_is_loaded_without_defaults(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=self.record(Path(tmp),'a');(r.record_dir/'info.json').write_text(json.dumps({'chronology':{'alignment_quality':.8,'expression_magnitude':.2}}))
   self.assertEqual(_record_qc(r)['status'],'available')
 def test_pair_missing_qc_is_excluded(self):
  a=SimpleNamespace(record_id='a');b=SimpleNamespace(record_id='b')
  d=_pair_qc_decision(a,b,{'a':{'status':'available','alignment_quality':.9,'expression_magnitude':.1,'reason':''}})
  self.assertFalse(d['applicable']);self.assertEqual(d['skip_reason'],'missing_mandatory_qc')
 def test_pair_low_alignment_is_excluded(self):
  a=SimpleNamespace(record_id='a');b=SimpleNamespace(record_id='b');q={x:{'status':'available','alignment_quality':.9,'expression_magnitude':.1,'reason':''} for x in ('a','b')};q['b']['alignment_quality']=.4
  self.assertEqual(_pair_qc_decision(a,b,q)['skip_reason'],'alignment_quality_low')
 def test_pair_expression_is_excluded(self):
  a=SimpleNamespace(record_id='a');b=SimpleNamespace(record_id='b');q={x:{'status':'available','alignment_quality':.9,'expression_magnitude':.1,'reason':''} for x in ('a','b')};q['b']['expression_magnitude']=1.6
  self.assertEqual(_pair_qc_decision(a,b,q)['skip_reason'],'expression_too_strong')
 def test_pair_valid_qc_is_applicable(self):
  a=SimpleNamespace(record_id='a');b=SimpleNamespace(record_id='b');q={x:{'status':'available','alignment_quality':.9,'expression_magnitude':.1,'reason':''} for x in ('a','b')}
  self.assertTrue(_pair_qc_decision(a,b,q)['applicable'])
 def test_evidence_downgrades_for_calibration(self):
  self.assertEqual(evidence_state('coherent_jump_candidate',calibration_limited=True),'calibration_limited')
 def test_evidence_downgrades_for_pose_leakage(self):
  self.assertEqual(evidence_state('coherent_jump_candidate',pose_leakage_limited=True),'pose_leakage_limited')
 def test_within_noise_is_not_upgraded_by_limitations(self):
  self.assertEqual(evidence_state('within_reconstruction_noise',calibration_limited=True,pose_leakage_limited=True),'within_noise')
 def test_limitation_reasons_are_explicit(self):
  reasons=alternative_reasons({'calibration_limited':True,'pose_leakage_limited':True})
  self.assertIn('unstable_or_sparse_calibration',reasons);self.assertIn('metric_may_retain_pose_dependence',reasons)
 def test_technical_summary_counts_limitations(self):
  out=build_technical_summary([{'status':'x','evidence_state':'calibration_limited','calibration_limited':True,'pose_leakage_limited':True}],[],{})
  self.assertEqual(out['calibration_limited_pair_count'],1);self.assertEqual(out['pose_leakage_limited_pair_count'],1)
 def test_stage2b_recognizes_new_and_inapplicable_states(self):
  self.assertIn('calibration_limited',WEAK_STATES);self.assertIn('pose_leakage_limited',WEAK_STATES);self.assertIn('inapplicable_pose',NO_SUPPORT_STATES)
  self.assertEqual(UNCLASSIFIED_EVIDENCE_STATES,set())
if __name__=='__main__':unittest.main()
