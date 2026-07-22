"""🔄 CALLBACK (pytest) → зоны морщин BFM35709 v3 (требует ассет texture_zones npz).
"""
import unittest
from pathlib import Path
import numpy as np
from app6.stage1.skin.atlas_registry import AtlasRegistry
from app6.stage2.skin.chronology import match_branches, analyze_records
class WrinkleZoneTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.atlas=AtlasRegistry(Path(__file__).parents[1]/'atlas/texture_zones_bfm35709_v3.npz')
 def test_layer_contract(self):
  self.assertEqual((len(self.atlas.A_codes),len(self.atlas.S_codes),len(self.atlas.W_codes)),(20,40,14));self.assertTrue(np.all(self.atlas.S_parent[self.atlas.S[self.atlas.skin]]==self.atlas.A[self.atlas.skin]))
 def test_q_cores_are_nested(self):self.assertTrue(np.all(self.atlas.cores['core5']<=self.atlas.cores['core3']));self.assertTrue(np.all(self.atlas.cores['core3']<=self.atlas.cores['core0']))
 def test_branch_matching_is_spatial_orientation_and_length_aware(self):
  a=[{'branch_id':1,'centroid_x':.20,'centroid_y':.30,'length':20,'orientation_deg':179}];b=[{'branch_id':7,'centroid_x':.21,'centroid_y':.31,'length':21,'orientation_deg':1}];m=match_branches(a,b);self.assertEqual(len(m['matches']),1);self.assertGreater(m['match_fraction'],.9)
 def test_chronology_separates_pose(self):
  z={'status':'ok','zone':'W05'};records=[{'photo_id':'a','date':'2000-01-01','pose_bin':'left_mid','zones':[z]},{'photo_id':'b','date':'2001-01-01','pose_bin':'left_mid','zones':[z]},{'photo_id':'c','date':'2001-01-01','pose_bin':'frontal','zones':[z]}];r=analyze_records(records);self.assertEqual(len(r['pairs']),1);self.assertEqual(r['pairs'][0]['pose_bin'],'left_mid')
if __name__=='__main__':unittest.main()
