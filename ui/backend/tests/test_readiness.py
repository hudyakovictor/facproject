from dataclasses import dataclass
import tempfile,unittest
from pathlib import Path
from dpo.readiness import DIMENSIONS,Dimension,POLICIES,SnapshotStore,decide_status
class ReadinessTests(unittest.TestCase):
 def dims(self,passed=()):return {x:Dimension(x,'passed' if x in passed else 'unknown','test','') for x in DIMENSIONS}
 def test_policy_truth_table_never_averages(self):
  d=self.dims(POLICIES['utility']);self.assertEqual(decide_status('utility',d)[0],'release_ready')
  d['docs']=Dimension('docs','unknown','none','');self.assertEqual(decide_status('utility',d)[0],'implemented_unverified')
 def test_calibration_cannot_turn_green_after_unit(self):
  d=self.dims(('implementation','unit','synthetic','real_photo','docs','observability'));status,missing,_=decide_status('calibration',d);self.assertEqual(status,'calibration_required');self.assertIn('calibration',missing)
 def test_visual_only_closes_without_forensic_dimensions(self):
  d=self.dims(POLICIES['visual_only']);self.assertEqual(decide_status('visual_only',d)[0],'release_ready')
 def test_failure_precedes_progress(self):
  d=self.dims(POLICIES['utility']);d['unit']=Dimension('unit','failed','test','');self.assertEqual(decide_status('utility',d)[0],'failing')
 def test_snapshot_key_is_deterministic(self):
  @dataclass(frozen=True)
  class R:
   code_hash:str
   def to_dict(self):return {'code_hash':self.code_hash}
  with tempfile.TemporaryDirectory() as t:
   s=SnapshotStore(Path(t));a=s.save([R('b'),R('a')]);b=s.save([R('a'),R('b')]);self.assertEqual(a,b)
if __name__=='__main__':unittest.main()
