"""Regression tests for geometry vs evidence evidence-path fixes."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app6.stage1.skin.pose_policy import PosePolicy, SOFT_EXCLUDE_FLOOR
from app6.stage1.skin.quality import per_zone_applicability, _sanitize_density
from app6.stage1.skin.previews import save_previews


class GeometryVsEvidenceTests(unittest.TestCase):
    def _write_csv(self, path: Path):
        # minimal: A10 exclude at +60, primary at -60
        lines = ['zone_code,yaw_bin_center_deg,status,weight,convention']
        for z in range(1, 21):
            zone = f'A{z:02d}'
            for yaw in [-60, -40, -25, -10, 0, 10, 25, 40, 60]:
                if zone in {'A10', 'A14', 'A18'} and yaw == 60:
                    st, w = 'exclude', 0.0
                elif zone in {'A10', 'A14', 'A18'} and yaw == -60:
                    st, w = 'primary', 1.0
                else:
                    st, w = 'primary', 1.0
                lines.append(f'{zone},{yaw},{st},{w},test')
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def test_missing_csv_raises(self):
        with self.assertRaises(FileNotFoundError):
            PosePolicy('/tmp/does_not_exist_pose_policy.csv', allow_default=False)

    def test_soft_evidence_boosts_exclude_when_observed(self):
        with tempfile.TemporaryDirectory() as td:
            csv = Path(td) / 'pose_policy_v3_9bins.csv'
            self._write_csv(csv)
            pol = PosePolicy(csv, allow_default=False)
            H = W = 64
            A = np.full((H, W), -1, np.int8)
            A[:, :] = 9  # A10
            domain = np.ones((H, W), bool)
            conf = np.full((H, W), 0.5, np.float32)
            inc = np.full((H, W), 0.5, np.float32)
            prior, _ = pol.weights(A, 60.0)
            self.assertTrue(float(prior.mean()) == 0.0)
            soft, meta, observed = pol.soft_evidence_weights(
                A, 60.0, domain=domain, projection_confidence=conf, incidence=inc,
            )
            self.assertTrue(bool(observed.all()))
            self.assertGreaterEqual(float(soft.mean()), SOFT_EXCLUDE_FLOOR - 1e-6)
            self.assertGreater(int(meta['soft_boosted_pixels']), 0)

    def test_density_not_hard_clipped_to_100(self):
        d = np.ones((32, 32), bool)
        s = np.full((32, 32), 250.0, np.float32)
        out, meta = _sanitize_density(s, d)
        self.assertNotEqual(meta.get('density_clip_mode'), 'hard100')
        # values may be winsorized but must not collapse to exactly constant 100 by design
        self.assertFalse(float(np.median(out[d])) == 100.0 and meta['density_raw_max'] > 100)

    def test_per_zone_geometry_without_evidence_flag(self):
        A = np.zeros((40, 40), np.int8)
        A[:, :] = 9
        domain = np.ones((40, 40), bool)
        qw = np.zeros((40, 40), np.float32)
        rows = per_zone_applicability(A, domain, qw)
        a10 = next(r for r in rows if r['zone'] == 'A10')
        self.assertTrue(a10['geometry_without_evidence'])
        self.assertEqual(a10['state'], 'not_measurable')

    def test_preview_writes_usable_overlay(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bgr = np.zeros((32, 32, 3), np.uint8)
            A = np.zeros((32, 32), np.int8)
            mask = np.ones((32, 32), bool)
            q = np.zeros((32, 32), np.float32)
            q[:16, :] = 0.8
            save_previews(root, bgr, A, mask, q, usable_mask=(q > 0))
            self.assertTrue((root / 'atlas_A20_overlay.png').is_file())
            self.assertTrue((root / 'atlas_A20_overlay_usable.png').is_file())
            self.assertTrue((root / 'atlas_geometry_vs_usable.png').is_file())
            self.assertTrue((root / 'quality_weight.png').is_file())

    def test_pose_delta_gate(self):
        ok, meta = PosePolicy.pose_delta_gate(0, 0, 0, 5, 5, 5)
        self.assertTrue(ok)
        bad, meta2 = PosePolicy.pose_delta_gate(0, 0, 0, 0, 30, 0)
        self.assertFalse(bad)
        self.assertEqual(meta2['reason'], 'pose_delta_exceeds_threshold')


if __name__ == '__main__':
    unittest.main()
