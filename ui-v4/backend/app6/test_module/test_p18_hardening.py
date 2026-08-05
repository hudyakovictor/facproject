from __future__ import annotations
import csv,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from app6.api.research_timeline import build_research_timeline
from app6.stage1.input_provenance import build_date_provenance
from app6.stage1.provenance_ledger import load_provenance_sidecar
from app6.stage2.chronology import apply_chronology_rate_flags
from app6.stage2.validation import validate_analysis_contract

class P18HardeningTests(unittest.TestCase):
 def test_source_claim_is_corroboration_only(self):
  p=build_date_provenance('2001-01-02',{}, {'claimed_date':'2001-01-05'})
  self.assertEqual(p['filename_date'],'2001-01-02');self.assertEqual(p['status'],'conflict');self.assertEqual(p['source_claimed_delta_days'],3);self.assertIn('source_claim',p['conflict_sources'])
 def test_sidecar_requires_web_source(self):
  with tempfile.TemporaryDirectory() as td:
   image=Path(td)/'x.jpg';Image.new('RGB',(8,8)).save(image);side=image.with_suffix('.jpg.provenance.json')
   for payload in ({'collector':'r'},{'source_url':'file:///tmp/x'},{'source_url':'https://example.test','claimed_date':'01.02.2003'}):
    side.write_text(json.dumps(payload),encoding='utf-8')
    with self.assertRaises(ValueError):load_provenance_sidecar(image)
 def test_near_duplicate_excludes_chronology(self):
  rows=[{'pair_type':'adjacent','pose_bin':'frontal','date_a':'2000-01-01','date_b':'2001-01-01','near_duplicate_pair':True,'date_provenance_limited':False,'quality_limited':False,'p95_point_z':9.,'coherent_motion_fraction':.9,'significant_point_fraction':.8,'pair_index':1}]
  apply_chronology_rate_flags(rows);self.assertEqual(rows[0]['chronology_rate_reason'],'perceptual_duplicate_dependence')
 def test_contract_rejects_ungated_conflict(self):
  row={'pair_id':'p','source_digest_a':'a','source_digest_b':'b','date_provenance_status_a':'filename_only','date_provenance_status_b':'conflict','date_provenance_limited':True,'analysis_space':'raw_object_normalized','evidence_state':'candidate','chronology_rate_status':'within_expected_rate'}
  packet={'pair_id':'p','registered_metric_channel':{}}
  with tempfile.TemporaryDirectory() as td:
   errors=validate_analysis_contract(Path(td),required_files=[],rows=[row],changes=[],evidence_packets=[packet],public_safety={'status':'pass'})
  self.assertTrue(any(x.startswith('date_conflict_not_downgraded') for x in errors));self.assertTrue(any(x.startswith('date_conflict_reached_chronology') for x in errors))
 def test_api_routes_source_claim(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'analysis_manifest.json').write_text(json.dumps({'schema_version':'x'}),encoding='utf-8')
   row={'status':'measured','pair_type':'adjacent','pose_bin':'frontal','photo_a':'A','photo_b':'B','date_a':'2000-01-01','date_b':'2001-01-01','evidence_state':'date_provenance_limited','date_provenance_status_a':'filename_only','date_provenance_status_b':'conflict','source_claimed_date_b':'2001-01-04','source_claimed_delta_days_b':'3','date_conflict_sources_b':'["source_claim"]','date_provenance_limited':'True','quality_limited':'False','primary_robust_z':'1','p95_point_z':'2'}
   with (r/'pair_metrics.csv').open('w',newline='',encoding='utf-8') as h:w=csv.DictWriter(h,fieldnames=list(row));w.writeheader();w.writerow(row)
   photo=next(x for x in build_research_timeline(r)['photos'] if x['id']=='B')
   self.assertEqual(photo['sourceClaimedDate'],'2001-01-04');self.assertEqual(photo['sourceClaimedDeltaDays'],3);self.assertEqual(photo['dateConflictSources'],['source_claim'])

if __name__=='__main__':unittest.main()
