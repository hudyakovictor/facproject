"""Stage2 engine with same-pose pitch/roll protection.

🚪 CONVENTIONS v2 → ENTRY POINT skin stage2; статус: ⚠️ IN PROGRESS
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from .loader import SkinPackage
from .pair_comparison import compare_packages
from .chronology import analyze_temporal_observations
from .symmetry import texture_symmetry
from app6.stage1.skin.serialization import atomic_json
from app6.stage1.skin.pose_policy import PosePolicy


def _angles_from_info_or_quality(info, pkg):
    pose = info.get('pose') or {}
    yaw = pose.get('yaw'); pitch = pose.get('pitch'); roll = pose.get('roll')
    if yaw is None or pitch is None or roll is None:
        try:
            q = pkg.json('quality.json').get('pose') or {}
            yaw = q.get('yaw', 0.0) if yaw is None else yaw
            pitch = q.get('pitch', 0.0) if pitch is None else pitch
            roll = q.get('roll', 0.0) if roll is None else roll
        except Exception:
            yaw = 0.0 if yaw is None else yaw
            pitch = 0.0 if pitch is None else pitch
            roll = 0.0 if roll is None else roll
    return float(yaw or 0.0), float(pitch or 0.0), float(roll or 0.0)


class SkinStage2Engine:
    def __init__(self, stage1_root, output, calibration=None):
        self.root = Path(stage1_root)
        self.out = Path(output)
        self.calibration = Path(calibration) if calibration else None

    def _calibrate_pair(self, q, pose, cal):
        if not cal:
            return
        for row in q.get('texture', {}).get('zones', []):
            zs = []
            for name, delta in row.get('feature_deltas', {}).items():
                m = cal.get('models', {}).get('|'.join((pose, row['zone'], name)))
                if m:
                    zs.append(float(delta) / (math.sqrt(2) * max(m['mad'], 1e-9)))
            row['calibrated_max_z'] = max(zs) if zs else None
            row['calibration_status'] = (
                'within_repeatability' if zs and max(zs) <= 3.5
                else ('difference_candidate' if zs else 'outside_calibration_support')
            )

    # 🚪 ENTRY POINT skin Stage 2
    def run(self):
        self.out.mkdir(parents=True, exist_ok=True)
        cal = None
        if self.calibration:
            cal = json.loads(self.calibration.read_text())
            if not cal.get('frozen'):
                raise ValueError('Stage2 requires frozen calibration artifact')

        records = []
        for p in sorted(self.root.iterdir()):
            if (p / 'skin/SUCCESS').is_file() and (p / 'info.json').is_file():
                records.append((json.loads((p / 'info.json').read_text()), SkinPackage(p / 'skin')))

        symmetry = []
        for info, pkg in records:
            try:
                symmetry.append({'photo_id': info['photo_id'], **texture_symmetry(pkg)})
            except Exception as e:
                symmetry.append({'photo_id': info.get('photo_id'), 'status': 'failed', 'error': str(e)})
        atomic_json(self.out / 'skin_symmetry.json', {'schema': 'skin-symmetry-index-v1', 'photos': symmetry})

        by = {}
        for info, pkg in records:
            by.setdefault(info.get('pose', {}).get('pose_bin', 'unknown'), []).append((info, pkg))

        pairs = []
        temporal = []
        for pose, g in by.items():
            g.sort(key=lambda x: (x[0].get('date', ''), x[0].get('photo_id', '')))
            # primary: consecutive in bin BUT only if pitch/roll/yaw deltas ok
            for (ia, a), (ib, b) in zip(g, g[1:]):
                ya, pa, ra = _angles_from_info_or_quality(ia, a)
                yb, pb, rb = _angles_from_info_or_quality(ib, b)
                ok, delta = PosePolicy.pose_delta_gate(ya, pa, ra, yb, pb, rb)
                q = compare_packages(a, b)
                self._calibrate_pair(q, pose, cal)
                role = 'primary_same_pose' if ok else 'deferred_same_bin_pose_delta'
                if not ok:
                    q['pair_status'] = 'insufficient_evidence'
                    q['pair_reason'] = 'engine_pose_delta_gate'
                    q['production_evidence_allowed'] = False
                q.update({
                    'pair_id': f"{ia['photo_id']}__{ib['photo_id']}",
                    'pose_bin': pose,
                    'date_a': ia.get('date'),
                    'date_b': ib.get('date'),
                    'comparison_role': role,
                    'engine_pose_delta_gate': delta,
                })
                pairs.append(q)
                atomic_json(self.out / 'pairs' / f"{q['pair_id']}.json", q)

            for info, pkg in g:
                try:
                    with pkg.npz('features/texture.npz') as z:
                        for i, zone in enumerate(z['zone_id']):
                            if z['state'][i] != 'usable':
                                continue
                            for j, name in enumerate(z['columns']):
                                value = float(z['values'][i, j])
                                if math.isfinite(value):
                                    temporal.append({
                                        'event_id': info['photo_id'],
                                        'date_start': info.get('date'),
                                        'pose_bin': pose,
                                        'zone': str(zone),
                                        'family': str(name),
                                        'raw_value': value,
                                        'state': 'usable',
                                    })
                except Exception:
                    pass

        by_date = {}
        for info, pkg in records:
            by_date.setdefault(info.get('date'), []).append((info, pkg))
        for date, g in by_date.items():
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    pa = g[i][0].get('pose', {}).get('pose_bin')
                    pb = g[j][0].get('pose', {}).get('pose_bin')
                    if pa == pb:
                        continue
                    q = compare_packages(g[i][1], g[j][1])
                    q.update({
                        'pair_id': f"{g[i][0]['photo_id']}__{g[j][0]['photo_id']}",
                        'pose_bin': f'{pa}__{pb}',
                        'date_a': date,
                        'date_b': date,
                        'comparison_role': 'secondary_cross_pose',
                        'calibration_status': 'secondary_not_calibrated',
                    })
                    pairs.append(q)

        chronology = analyze_temporal_observations(temporal)
        atomic_json(self.out / 'skin_pairs.json', {'schema': 'skin-pairs-index-v1', 'pair_count': len(pairs), 'pairs': pairs})
        atomic_json(self.out / 'skin_chronology.json', chronology)
        manifest = {
            'schema': 'skin-stage2-run-v1',
            'stage1_packages': len(records),
            'pair_count': len(pairs),
            'calibration': str(self.calibration) if self.calibration else None,
            'calibration_sha256': cal.get('artifact_sha256') if cal else None,
            'reconstruction_calls': 0,
            'status': 'experimental_complete_v5_pose_delta',
            'production_evidence_allowed': False,
        }
        atomic_json(self.out / 'manifest.json', manifest)
        return manifest
