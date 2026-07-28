import unittest
import numpy as np
from app6.stage2.robustness import validate_landmarks,normalize_points,kabsch_rmse,robust_pair_distance,robust_threshold,classify_sequence,effective_sample_size

class AdvancedRobustnessTest(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(7); self.a=rng.normal(size=(106,3))
    def test_translation_and_scale_normalization(self):
        b=self.a*3.2+np.array([4,-2,8]); self.assertLess(np.max(np.abs(normalize_points(self.a)-normalize_points(b))),1e-10)
    def test_kabsch_rotation_invariant(self):
        t=.3; R=np.array([[np.cos(t),-np.sin(t),0],[np.sin(t),np.cos(t),0],[0,0,1]])
        self.assertLess(kabsch_rmse(self.a,self.a@R),1e-10)
    def test_corrupt_ids_rejected(self):
        ids=np.arange(106); ids[-1]=0
        with self.assertRaises(ValueError): validate_landmarks(self.a,ids=ids,expected_count=106)
    def test_visibility_fail_closed(self):
        v=np.zeros(106,bool); v[:10]=1
        self.assertEqual(robust_pair_distance(self.a,self.a,v,v,min_common=20)['status'],'insufficient_visibility')
    def test_trimmed_distance_resists_single_outlier(self):
        b=self.a.copy(); b[0]+=100
        r=robust_pair_distance(self.a,b,min_common=20)
        self.assertLess(r['trimmed_rmse'],r['rmse']*.1)
    def test_robust_threshold_rejects_poison(self):
        x=np.r_[np.linspace(.01,.02,30),10,20,30]
        self.assertLess(robust_threshold(x)['threshold'],.03)
    def test_sequence_separates_burst_from_regime(self):
        r=classify_sequence([.1,.9,.1,.9,.9,.1],.5,2)
        self.assertEqual(r['isolated'],1); self.assertEqual(r['regimes'],[(3,4)])
    def test_effective_sample_size_penalizes_duplicates(self):
        self.assertLess(effective_sample_size(['a']*20+['b','c']),3.1)

if __name__=='__main__': unittest.main()


class NewValidationGuardTest(unittest.TestCase):
    def test_cross_pose_rejected(self):
        from app6.stage2.robustness import ensure_same_pose
        with self.assertRaises(ValueError): ensure_same_pose('frontal','right_light')

    def test_balanced_threshold_ignores_replication(self):
        from app6.stage2.robustness import balanced_person_threshold
        base={'a':[1,2,3],'b':[2,3,4],'c':[3,4,5]}
        replicated={'a':[1,2,3]*100,'b':[2,3,4],'c':[3,4,5]}
        self.assertAlmostEqual(balanced_person_threshold(base),balanced_person_threshold(replicated))

    def test_serialized_record_mismatch_rejected(self):
        from app6.stage2.robustness import validate_serialized_record
        p=np.zeros((106,3)); q=p.copy(); q[0,0]=1
        with self.assertRaises(ValueError): validate_serialized_record(p,q,[0,0,0],[0,0,0])


class NoiseAdjustedThresholdTest(unittest.TestCase):
    def test_threshold_increases_monotonically(self):
        from app6.stage2.robustness import noise_adjusted_threshold
        self.assertGreater(noise_adjusted_threshold(.03,.006),.03)
        self.assertEqual(noise_adjusted_threshold(.03,0),.03)

    def test_negative_noise_rejected(self):
        from app6.stage2.robustness import noise_adjusted_threshold
        with self.assertRaises(ValueError): noise_adjusted_threshold(.03,-.1)