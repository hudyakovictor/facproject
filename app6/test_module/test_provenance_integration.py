from __future__ import annotations
import csv,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from app6.api.research_timeline import build_research_timeline
from app6.stage1.provenance_ledger import hamming_distance,load_provenance_sidecar,perceptual_dhash
from app6.stage1.engine import discover_input_photos
from app6.stage2.chronology import apply_chronology_rate_flags
from app6.stage2.evidence import packet_from_pair
from app6.stage2.integrity import compute_dataset_hash

class ProvenanceIntegrationTests(unittest.TestCase):
 def test_perceptual_hash_survives_resave(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);im=Image.new('RGB',(64,64));px=im.load()
   for y in range(64):
    for x in range(64):px[x,y]=(x*4,y*4,(x+y)*2)
   a=r/'a.png';b=r/'b.jpg';im.save(a);im.save(b,quality=75)
   self.assertLessEqual(hamming_distance(perceptual_dhash(a),perceptual_dhash(b)),4)
 def test_strict_sidecar(self):
  with tempfile.TemporaryDirectory() as td:
   image=Path(td)/'2001_01_01.jpg';Image.new('RGB',(10,10)).save(image);side=image.with_suffix(image.suffix+'.provenance.json')
   side.write_text(json.dumps({'source_url':'https://example.test/a','collector':'r1'}),encoding='utf-8')
   result=load_provenance_sidecar(image);self.assertEqual(result['status'],'provided');self.assertEqual(len(result['sidecar_digest']),64)
   side.write_text(json.dumps({'unknown':1}),encoding='utf-8')
   with self.assertRaises(ValueError):load_provenance_sidecar(image)
 def test_dataset_hash_is_canonical(self):
  fields=['source_relative_path','source_digest'];rows=[{'source_relative_path':'b','source_digest':'b'*64},{'source_relative_path':'a','source_digest':'a'*64}]
  with tempfile.TemporaryDirectory() as td:
   paths=[Path(td)/'a.csv',Path(td)/'b.csv']
   for path,data in zip(paths,(rows,list(reversed(rows))),strict=True):
    with path.open('w',newline='',encoding='utf-8') as h:w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(data)
   self.assertEqual(compute_dataset_hash(paths[0]),compute_dataset_hash(paths[1]));self.assertEqual(len(compute_dataset_hash(paths[0])),64)
 def test_date_conflict_excludes_chronology(self):
  rows=[{'pair_type':'adjacent','pose_bin':'frontal','date_a':'2000-01-01','date_b':'2001-01-01','date_provenance_limited':True,'quality_limited':False,'p95_point_z':9.,'coherent_motion_fraction':.9,'significant_point_fraction':.8,'pair_index':1}]
  apply_chronology_rate_flags(rows);self.assertEqual(rows[0]['chronology_rate_status'],'excluded');self.assertEqual(rows[0]['chronology_rate_reason'],'date_provenance_conflict')
 def test_input_preflight_rejects_invalid_authoritative_date_before_run(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   Image.new('RGB',(10,10)).save(root/'2003_15_17.jpg')
   Image.new('RGB',(10,10)).save(root/'2003_12_17(4).jpg')
   (root/'._2003_12_17.jpg').write_bytes(b'macos-sidecar')
   with self.assertRaisesRegex(ValueError,'2003_15_17.jpg'):
    discover_input_photos(root)
   (root/'2003_15_17.jpg').unlink()
   self.assertEqual([p.name for p in discover_input_photos(root)],['2003_12_17(4).jpg'])
 def test_calibration_input_allows_undated_frame_names(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);person=root/'person_01';person.mkdir()
   Image.new('RGB',(10,10)).save(person/'frame_000204.jpg')
   self.assertEqual(
    [p.relative_to(root).as_posix() for p in discover_input_photos(root,require_filename_date=False)],
    ['person_01/frame_000204.jpg'],
   )
 def test_api_propagates_conflict(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'analysis_manifest.json').write_text(json.dumps({'schema_version':'x'}),encoding='utf-8')
   row={'status':'measured','pair_type':'adjacent','pose_bin':'frontal','photo_a':'A','photo_b':'B','date_a':'2000-01-01','date_b':'2001-01-01','evidence_state':'date_provenance_limited','date_provenance_status_a':'filename_only','date_provenance_status_b':'conflict','exif_date_b':'2001-01-03','date_delta_days_b':'2','date_provenance_limited':'True','quality_limited':'False','primary_robust_z':'1','p95_point_z':'2'}
   with (r/'pair_metrics.csv').open('w',newline='',encoding='utf-8') as h:w=csv.DictWriter(h,fieldnames=list(row));w.writeheader();w.writerow(row)
   photo=next(x for x in build_research_timeline(r)['photos'] if x['id']=='B')
   self.assertTrue(photo['exifAnomaly']);self.assertTrue(photo['dateProvenanceLimited']);self.assertEqual(photo['dateDeltaDays'],2)
 def test_evidence_contains_chain_and_limitations(self):
  row={'pair_id':'p','evidence_state':'date_provenance_limited','status':'measured','pair_type':'adjacent','pose_bin':'frontal','photo_a':'A','photo_b':'B','date_a':'2000-01-01','date_b':'2001-01-01','date_provenance_limited':True,'near_duplicate_pair':True,'source_provenance_status_a':'provided','source_provenance_status_b':'not_provided','source_digest_a':'a','source_digest_b':'b','source_url_a':'https://a','source_url_b':None,'archive_url_a':None,'archive_url_b':None}
  packet=packet_from_pair(row)
  self.assertIn('filename_corroborating_date_conflict',packet['alternative_explanations']);self.assertIn('perceptual_duplicate_cluster_dependence',packet['alternative_explanations']);self.assertEqual(packet['source_files']['source_digest_a'],'a')

if __name__=='__main__':unittest.main()
