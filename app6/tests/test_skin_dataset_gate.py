import csv,hashlib,tempfile,unittest
from pathlib import Path
from app6.stage2.skin.dataset import validate_skin_dataset
class DatasetGateTests(unittest.TestCase):
 def test_capture_event_leakage_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'a.jpg').write_bytes(b'a');(r/'b.jpg').write_bytes(b'b');p=r/'m.csv';fields=['photo_id','relative_path','input_sha256','capture_event_id','date_start','source_group','expression_bin','yaw_bin','duplicate_cluster','split']
   with p.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow(dict(zip(fields,['a','a.jpg',hashlib.sha256(b'a').hexdigest(),'e1','2000-01-01','s','neutral','frontal','c1','development'])));w.writerow(dict(zip(fields,['b','b.jpg',hashlib.sha256(b'b').hexdigest(),'e1','2000-01-01','s','neutral','frontal','c2','test'])))
   q=validate_skin_dataset(r,p,min_photos=0);self.assertFalse(q['ok']);self.assertTrue(any('leakage' in x for x in q['errors']))
if __name__=='__main__':unittest.main()
