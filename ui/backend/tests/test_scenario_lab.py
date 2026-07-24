import tempfile,unittest
from pathlib import Path
from dpo.scenario_lab import ScenarioLab
class ScenarioLabTests(unittest.TestCase):
 def setUp(self):self.lab=ScenarioLab(Path(__file__).resolve().parents[3]/'app6')
 def test_imports_existing_21_without_execution(self):
  s=self.lab.scenarios();self.assertEqual(len(s),21);self.assertEqual(s[0]['id'],'S01_stability_frontal_A')
 def test_balanced_1_3_7_and_nine_poses(self):
  p=self.lab.plan('S01_stability_frontal_A','all',7);self.assertEqual(p['case_count'],63);self.assertEqual({x['roles']['A'] for x in p['combinations']},{f'person_{i:02d}' for i in range(1,8)})
 def test_rejects_unbounded_input(self):
  with self.assertRaises(ValueError):self.lab.plan('../x','all',7)
  with self.assertRaises(ValueError):self.lab.plan('S01_stability_frontal_A','frontal',2)
 def test_function_matrix_and_synthetic_boundary(self):
  self.assertGreaterEqual(len(self.lab.function_matrix()),11);self.assertIn('not accuracy',self.lab.synthetic()['claim_boundary'])
 def test_fresh5_never_emits_coordinates(self):
  rows=[{'dataset_id':'person_01','pose_bin':'frontal','record_id':str(i),'yaw':i,'pitch':0,'roll':0,'x':999} for i in range(9)]
  x=self.lab.fresh5(rows,'person_01','frontal');self.assertEqual(len(x['photos']),5);self.assertFalse(x['coordinates_used']);self.assertTrue(all('x' not in r for r in x['photos']))
if __name__=='__main__':unittest.main()
