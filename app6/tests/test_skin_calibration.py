import tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from uv_module.calibration import calibrate
from uv_module.chronology import analyze_records


def branch(i,dx=0.0):
    return {'branch_id':i,'centroid_x':.20+i*.02+dx,'centroid_y':.30+i*.01,'length':20+i,'orientation_deg':2+i}

def zone(offset=0.0):
    return {'status':'ok','zone':'forehead_horizontal_center','quality_score':.82,'observed_fraction':.84,
            'noise_sigma':.025,'source_span_x':70,'source_span_y':42,'ridge_density':.031+offset,
            'total_length':63+offset*20,'branch_count':3,'median_length':21,'detector_consensus':.42,
            'branches':[branch(i,offset*.01) for i in range(3)]}

def records():
    out=[]
    poses=['frontal','left_mid','right_mid']
    for pidx,pose in enumerate(poses):
        for i in range(30):
            # deterministic distinct pHashes avoid duplicate-cluster leakage
            ph=f'{(0x9e3779b97f4a7c15*(1+i+pidx*31)) & ((1<<64)-1):016x}'
            out.append({'photo_id':f'{pose}-{i}','date':'2000-01-01','pose_bin':pose,'phash':ph,
                        'source':f'{pose}/{i}.jpg','zones':[zone((i%5-2)*.0002)]})
    return out

class SkinCalibrationTests(unittest.TestCase):
    def test_calibration_builds_held_out_profile(self):
        with tempfile.TemporaryDirectory() as td, patch('uv_module.calibration.load_records',return_value=records()):
            profile,report=calibrate(Path(td)/'stage1',Path(td)/'out',.01)
            self.assertEqual(profile['photo_count'],90)
            self.assertGreaterEqual(report['reliable_model_count'],3)
            self.assertTrue(report['acceptance']['test_pass'])
            self.assertTrue((Path(td)/'out/calibration_profile.json').is_file())
            self.assertTrue((Path(td)/'out/calibration_split.csv').is_file())

    def test_profile_is_applied_to_main_chronology(self):
        recs=records()[:2]
        with tempfile.TemporaryDirectory() as td, patch('uv_module.calibration.load_records',return_value=records()):
            profile,_=calibrate(Path(td)/'stage1',Path(td)/'out',.01)
            report=analyze_records(recs,profile)
            self.assertTrue(report['calibrated'])
            self.assertEqual(report['pairs'][0]['status'],'calibrated_consistent')

if __name__=='__main__': unittest.main()
