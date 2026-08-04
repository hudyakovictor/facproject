import unittest
from app6.stage2.pair_planner import plan_pairs
from app6.api.settings import SettingsPayload,_deep_merge,DEFAULT_SETTINGS
class Contracts(unittest.TestCase):
 def test_settings_rejects_uncalibrated_release(self):
  with self.assertRaises(ValueError):SettingsPayload.model_validate({**DEFAULT_SETTINGS,"threshold_mode":"calibrated"})
 def test_deep_merge_preserves_thresholds(self):
  self.assertIn("quality_min",_deep_merge(DEFAULT_SETTINGS,{"thresholds":{"confidence_min":.6}})["thresholds"])
 def test_pair_planner_is_deterministic(self):
  class R:
   def __init__(self,i):self.record_id=str(i);self.date=f"2000-01-{i+1:02d}";self.sequence=i
  a=plan_pairs([R(i) for i in range(12)]);self.assertEqual([(k,x.record_id,y.record_id) for k,x,y in a],[(k,x.record_id,y.record_id) for k,x,y in plan_pairs([R(i) for i in range(12)])])
if __name__=="__main__":unittest.main()
