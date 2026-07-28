import csv,tempfile,unittest
from pathlib import Path
import numpy as np
from app6.run_preflight import audit_calibration_index,POSES,PATH_COLUMNS
from app6.stage2.chronology import apply_cumulative_drift_flags
from app6.stage2.core import ZONE_WEIGHTS
from app6.stage2.robustness import balanced_reference

class ReleaseHardeningTest(unittest.TestCase):
    def test_all_coordinate_zones_have_explicit_weights(self):
        expected={f'x_{x}_{y}' for x in ('low','center','high') for y in ('low','center','high')}
        self.assertEqual(expected,set(ZONE_WEIGHTS))
    def test_balanced_reference_ignores_replication(self):
        a={'p1':[1,2,3],'p2':[2,3,4],'p3':[3,4,5]};b={**a,'p1':a['p1']*100}
        self.assertEqual(balanced_reference(a)['p95'],balanced_reference(b)['p95'])
    def test_cumulative_drift_detects_small_repeated_excess(self):
        rows=[]
        for i in range(5):
            rows.append({'pair_id':str(i),'pair_type':'adjacent','pose_bin':'frontal','date_b':f'2020-01-0{i+1}','pair_index':i,'p95_point_z':4.0,'quality_limited':False})
        report=apply_cumulative_drift_flags(rows,point_z_floor=2.5,cusum_threshold=6.0)
        self.assertGreaterEqual(report['event_count'],1)
    def test_index_preflight_counts_all_pose_bins(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);idx=root/'all_calibration_index.csv';fields=['dataset_id','record_id','pose_bin','yaw','pitch','roll',*PATH_COLUMNS]
            with idx.open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
                for i,pose in enumerate(sorted(POSES)):
                    row={'dataset_id':'p1','record_id':f'r{i}','pose_bin':pose,'yaw':0,'pitch':0,'roll':0}
                    row.update({c:'missing' for c in PATH_COLUMNS});w.writerow(row)
            report=audit_calibration_index(idx,root,check_files=False)
            self.assertEqual(report['status'],'ready')

if __name__=='__main__':unittest.main()