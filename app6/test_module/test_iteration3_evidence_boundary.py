"""Regression contracts for public evidence and visualization separation."""
from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from app6.stage2.evidence import is_reportable_change,packet_from_pair
from app6.stage2.metric_registry import evidence_metric_channel,build_metric_catalog
from app6.stage2.validation import validate_analysis_contract
from app6.stage3.engine import public_pair_projection

class Iteration3EvidenceBoundaryTest(unittest.TestCase):
 def test_limited_candidate_is_not_reportable(self):
  self.assertFalse(is_reportable_change({'pair_type':'adjacent','evidence_state':'calibration_limited'}))
  self.assertFalse(is_reportable_change({'pair_type':'adjacent','evidence_state':'pose_leakage_limited'}))
  self.assertFalse(is_reportable_change({'pair_type':'adjacent','evidence_state':'quality_limited'}))
 def test_reportable_requires_adjacent_pair(self):
  self.assertTrue(is_reportable_change({'pair_type':'adjacent','evidence_state':'persistent_geometric_change'}))
  self.assertFalse(is_reportable_change({'pair_type':'baseline','evidence_state':'persistent_geometric_change'}))
 def test_evidence_metric_channel_excludes_texture(self):
  channel=evidence_metric_channel({'ldm134_rmse':.1,'texture_image_status':'measured','texture_image_max_lbp_chi2':2.0})
  self.assertIn('ldm134_rmse',channel)
  self.assertFalse(any(k.startswith(('texture_','uv_')) for k in channel))
 def test_packet_places_texture_in_visualization_only(self):
  packet=packet_from_pair({'pair_id':'p','pair_type':'adjacent','pose_bin':'frontal','photo_a':'a','photo_b':'b','status':'within_reconstruction_noise','evidence_state':'within_noise','texture_image_status':'measured','texture_pair_status':'texture_ready'})
  self.assertEqual(packet['visualization_only']['texture_image_status'],'measured')
  self.assertNotIn('texture_image_status',packet['measurements'])
  self.assertNotIn('texture_image_status',packet['registered_metric_channel'])
 def test_catalog_marks_texture_visualization_only(self):
  catalog=build_metric_catalog([{'texture_image_status':'measured','ldm134_rmse':.1}])
  roles={x['name']:x['evidence_role'] for x in catalog['metrics']}
  self.assertEqual(roles['texture_image_status'],'visualization_only')
  self.assertEqual(roles['ldm134_rmse'],'forensic_measurement')
 def test_public_projection_removes_visualization_metrics(self):
  row=public_pair_projection({'pair_id':'p','texture_image_status':'measured','uv_common_zone_count':3,'quality_texture_score_a':.8})
  self.assertNotIn('texture_image_status',row);self.assertNotIn('uv_common_zone_count',row)
  self.assertEqual(row['quality_texture_score_a'],.8)
 def test_semantic_validation_rejects_nonreportable_change(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);(out/'x').write_text('x')
   rows=[{'pair_id':'p'}];packets=[{'pair_id':'p','registered_metric_channel':{}}]
   errors=validate_analysis_contract(out,required_files=['x'],rows=rows,changes=[{'pair_id':'p','pair_type':'adjacent','evidence_state':'quality_limited'}],evidence_packets=packets,public_safety={'status':'pass'})
   self.assertTrue(any(x.startswith('nonreportable_change_points:') for x in errors))
 def test_semantic_validation_rejects_visual_metric_leak(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);(out/'x').write_text('x')
   errors=validate_analysis_contract(out,required_files=['x'],rows=[{'pair_id':'p'}],changes=[],evidence_packets=[{'pair_id':'p','registered_metric_channel':{'texture_image_status':'measured'}}],public_safety={'status':'pass'})
   self.assertTrue(any(x.startswith('visualization_metric_leaked_into_evidence:') for x in errors))
 def test_semantic_validation_accepts_clean_contract(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);(out/'x').write_text('x')
   errors=validate_analysis_contract(out,required_files=['x'],rows=[{'pair_id':'p'}],changes=[],evidence_packets=[{'pair_id':'p','registered_metric_channel':{'ldm134_rmse':.1}}],public_safety={'status':'pass'})
   self.assertEqual(errors,[])
if __name__=='__main__':unittest.main()
