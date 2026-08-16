import unittest
from app6.stage2.engine import _pair_qc_decision
class R:
 def __init__(self,i,date):self.record_id=i;self.date=date
class SelectedPatchRegressions(unittest.TestCase):
 def test_jaw_mismatch_reaches_era_gate(self):
  q={"a":{"status":"available","alignment_quality":.8,"jaw_open_detected":True},"b":{"status":"available","alignment_quality":.8,"jaw_open_detected":False}}
  self.assertTrue(_pair_qc_decision(R("a","2001-01-01"),R("b","2006-01-01"),q)["applicable"])
if __name__=="__main__":unittest.main()
