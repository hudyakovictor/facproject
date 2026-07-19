import unittest
import numpy as np
from uv_module.zones import ZONE_SPECS, POSE_POLICY, zone_vertex_masks, policy_weight
from uv_module.chronology import match_branches, analyze_records


class WrinkleZoneTests(unittest.TestCase):
    def test_every_pose_has_explicit_policy_for_every_zone(self):
        names={s.name for s in ZONE_SPECS}
        self.assertEqual(len(names),13)
        for pose,row in POSE_POLICY.items():
            self.assertEqual(set(row),names,pose)
            self.assertTrue(all(0 <= v <= 1 for v in row.values()))

    def test_frontal_and_profiles_target_different_regions(self):
        self.assertGreater(policy_weight('frontal','glabella_vertical'),0)
        self.assertEqual(policy_weight('left_profile','glabella_vertical'),0)
        self.assertGreater(policy_weight('left_profile','crow_feet_left'),0)
        self.assertEqual(policy_weight('left_profile','crow_feet_right'),0)

    def test_branch_matching_is_spatial_orientation_and_length_aware(self):
        a=[{'branch_id':1,'centroid_x':.20,'centroid_y':.30,'length':20,'orientation_deg':2}]
        b=[{'branch_id':7,'centroid_x':.21,'centroid_y':.31,'length':21,'orientation_deg':4}]
        m=match_branches(a,b)
        self.assertEqual(len(m['matches']),1)
        self.assertGreater(m['match_fraction'],.9)

    def test_chronology_separates_pose_and_zone(self):
        z={'status':'ok','zone':'crow_feet_left','quality_score':.8,'ridge_density':.03,'total_length':50,'branches':[]}
        records=[{'photo_id':'a','date':'2000-01-01','pose_bin':'left_mid','zones':[z]},
                 {'photo_id':'b','date':'2001-01-01','pose_bin':'left_mid','zones':[dict(z,ridge_density=.031)]},
                 {'photo_id':'c','date':'2001-01-01','pose_bin':'frontal','zones':[z]}]
        r=analyze_records(records)
        self.assertEqual(len(r['pairs']),1)
        self.assertEqual(r['pairs'][0]['pose_bin'],'left_mid')

if __name__=='__main__': unittest.main()
