from __future__ import annotations
import unittest
from datetime import date, timedelta
import numpy as np

from app6.stage1.input_provenance import build_date_provenance
from app6.stage2.analysis_policy import pose_gap
from app6.stage2.irreversible_return import detect_irreversible_return
from app6.stage2.landmark_policy import normalized_weights, stable_subset
from app6.stage2.multiple_testing import DEFAULT_FDR_LEVEL, apply_pair_fdr
from app6.stage2.same_day_gate import check_same_day_conflict


class Round5PatchTests(unittest.TestCase):
    def test_pose_gate_is_axis_specific(self):
        # Без pose_bin действует fallback yaw_limit=6.0°, отсюда pitch_limit≈3.39°
        # и roll_limit≈4.38° (чувствительность 1.77/1.37). Каждая ось отдельна.
        self.assertTrue(pose_gap([0, 0, 0], [1.9, 5.9, 3.0]).accepted)
        self.assertEqual(pose_gap([0, 0, 0], [4.0, 0, 0]).reason, "pitch_gap")
        self.assertEqual(pose_gap([0, 0, 0], [0, 6.1, 0]).reason, "yaw_gap")
        self.assertEqual(pose_gap([0, 0, 0], [0, 0, 5.0]).reason, "roll_gap")

    def test_utility_nan_is_safe_and_subset_size_exact(self):
        x=np.tile(np.linspace(0.1, 2.0, 134), (9, 1))
        x[0, :34]=np.nan
        ids=stable_subset(x, 91)
        self.assertEqual(len(ids), 91)
        self.assertEqual(len(set(ids.tolist())), 91)
        self.assertTrue(np.isfinite(normalized_weights(x, 0)).all())

    def test_filename_date_remains_authoritative(self):
        p=build_date_provenance("2001-01-02", {"exif_camera_processing":{"DateTimeOriginal":"2001:01:03 12:00:00"}})
        self.assertEqual(p["authority"], "filename")
        self.assertEqual(p["status"], "conflict")
        self.assertEqual(p["delta_days"], 1)

    def test_null_timeline_does_not_trigger_return(self):
        base=np.array([1.0, 0.0, 0.0])
        timeline=[]
        for i in range(6):
            d=date(2000,1,1)+timedelta(days=500*i)
            timeline.append({"date":d.isoformat(),"photo_id":str(i),"shape":(base+np.array([0, 1e-4*i, 0])).tolist()})
        self.assertEqual(detect_irreversible_return(timeline, min_years=2), [])

    def test_a_b_a_return_is_detected(self):
        a=[1.0,0.0,0.0]; b=[0.0,1.0,0.0]
        timeline=[{"date":"2000-01-01","photo_id":"A1","shape":a},
                  {"date":"2004-01-01","photo_id":"B","shape":b},
                  {"date":"2010-01-01","photo_id":"A2","shape":a}]
        self.assertEqual(len(detect_irreversible_return(timeline)), 1)

    def test_same_day_baseline_is_contamination_hardened(self):
        rows=[]
        for i,v in enumerate([1,1.1,.9,1.05,.95,1.02,1.08,.97,6,7]):
            rows.append({"pair_id":str(i),"date_a":"2020-01-01","date_b":"2020-01-01",
                         "photo_a":f"a{i}","photo_b":f"b{i}","pose_bin":"frontal","ldm134_rmse":v})
        hits=check_same_day_conflict(rows)
        self.assertGreaterEqual(len(hits), 2)
        # Без capture_event — одно событие на дату, квантильная политика
        # недоступна (MIN_BASELINE_EVENTS=3), включается sigma-fallback v1.
        self.assertTrue(all(h["baseline_policy"] == "lower80_sigma_fallback_v1" for h in hits))
        self.assertEqual({h["baseline_event_count"] for h in hits}, {1})
        self.assertTrue(all(h["confidence"] == "reduced" for h in hits))

    def test_same_day_event_quantile_policy(self):
        # Несколько событий одного дня → базовый уровень по представителю события.
        rows=[]
        i=0
        for ev, vals in {"ev1":[1,1.1,.9,1.05,.95], "ev2":[.98,1.02,1.0,.99,1.01],
                         "ev3":[1.0,1.05,.96,1.03,.97]}.items():
            for v in vals:
                rows.append({"pair_id":str(i),"date_a":"2020-01-01","date_b":"2020-01-01",
                             "capture_event":ev,"photo_a":f"a{i}","photo_b":f"b{i}",
                             "pose_bin":"frontal","ldm134_rmse":v})
                i+=1
        rows.append({"pair_id":str(i),"date_a":"2020-01-01","date_b":"2020-01-01",
                     "capture_event":"ev1","photo_a":"aX","photo_b":"bX",
                     "pose_bin":"frontal","ldm134_rmse":6.0})
        hits=check_same_day_conflict(rows)
        self.assertTrue(all(h["baseline_policy"] == "event_quantile_v2" for h in hits))
        self.assertEqual({h["baseline_event_count"] for h in hits}, {3})
        self.assertTrue(all(h["confidence"] == "full" for h in hits))

    def test_fdr_default_and_order_statistic_input(self):
        rows=[{"p95_point_z":4.0,"calibrated_point_count":120}]
        report=apply_pair_fdr(rows)
        self.assertEqual(report["q_threshold"], DEFAULT_FDR_LEVEL)
        self.assertEqual(DEFAULT_FDR_LEVEL, 0.05)
        self.assertIn("mt_p_approx", rows[0])


if __name__ == "__main__":
    unittest.main()
