"""Pair comparison with pose delta (yaw/pitch/roll) + common usable gates."""
from __future__ import annotations
import numpy as np
from pathlib import Path
from app6.stage1.skin.contracts import PairStatus, SCHEMAS
from app6.stage1.skin.pose_policy import PosePolicy, MIN_COMMON_USABLE_ZONES
from .applicability import common_surface
from .texture_comparison import compare_texture
from .wrinkle_matching import match_wrinkle_packages
from .local_feature_matching import match_local_features
from .quality_matching import compare_sensitivity_packages

DEFAULT_ATLAS_CSV = Path(__file__).resolve().parents[2] / 'atlas' / 'pose_policy_v3_9bins.csv'


def _pose_angles(pkg):
    try:
        q = pkg.json('quality.json')
        pose = q.get('pose') or {}
        return (
            float(pose.get('yaw', 0.0)),
            float(pose.get('pitch', 0.0)),
            float(pose.get('roll', 0.0)),
        )
    except Exception:
        return 0.0, 0.0, 0.0


def _count_usable_zones(pkg):
    try:
        q = pkg.json('quality.json')
        rows = q.get('per_zone_applicability') or []
        if rows:
            return sum(1 for r in rows if r.get('state') == 'usable')
    except Exception:
        pass
    try:
        with pkg.npz('features/texture.npz') as z:
            return int(np.sum(z['state'] == 'usable'))
    except Exception:
        return 0


def compare_packages(a, b, min_common=.35):
    if DEFAULT_ATLAS_CSV.exists():
        policy = PosePolicy(DEFAULT_ATLAS_CSV, allow_default=False)
    else:
        policy = None

    yaw_a, pitch_a, roll_a = _pose_angles(a)
    yaw_b, pitch_b, roll_b = _pose_angles(b)

    if policy is not None:
        geom_ok, delta_meta = policy.pose_delta_gate(
            yaw_a, pitch_a, roll_a, yaw_b, pitch_b, roll_b,
        )
    else:
        geom_ok, delta_meta = True, {'reason': 'no_policy', 'same_pose_geometry_ok': True}

    usable_a = _count_usable_zones(a)
    usable_b = _count_usable_zones(b)

    with a.surface() as sa, a.atlas() as aa, b.surface() as sb, b.atlas() as ab:
        zones = []
        n_ok = 0
        for z in range(20):
            c = common_surface(sa, sb, aa, ab, 'A', z)
            coverage = float(c.get('coverage_sym', 0))
            zone_id = f'A{z+1:02d}'
            if policy:
                compatible, combined_w, reason = policy.is_compatible(zone_id, yaw_a, yaw_b)
                gate_status, effective = policy.common_observed_gate(coverage, combined_w)
                if not geom_ok:
                    status = PairStatus.INSUFFICIENT_EVIDENCE.value
                    gate_status = 'POSE_DELTA_GATE'
                elif not compatible:
                    status = PairStatus.NOT_COMPARABLE.value
                elif gate_status == 'INSUFFICIENT_EVIDENCE' or coverage < min_common:
                    status = PairStatus.INSUFFICIENT_EVIDENCE.value
                elif gate_status == 'COARSE_ONLY':
                    status = PairStatus.COARSE_DIRECTION_MATCH.value
                else:
                    status = PairStatus.PARTIAL_MATCH.value
                    n_ok += 1
            else:
                combined_w = 1.0
                reason = 'no policy'
                effective = coverage
                status = PairStatus.INSUFFICIENT_EVIDENCE.value if coverage < min_common else PairStatus.PARTIAL_MATCH.value
                gate_status = status
                if status == PairStatus.PARTIAL_MATCH.value:
                    n_ok += 1

            zones.append({
                'zone': zone_id,
                'status': status,
                'coverage_sym': coverage,
                'effective_coverage': effective,
                'pose_compatible': compatible if policy else True,
                'pose_combined_weight': combined_w,
                'pose_reason': reason,
                'pose_gate': gate_status if policy else 'no_gate',
                **{k: v for k, v in c.items() if k != 'triangle_ids'},
                'common_triangle_ids': c['triangle_ids'].tolist(),
                'yaw_a': yaw_a,
                'yaw_b': yaw_b,
            })

    if not geom_ok:
        pair_status = PairStatus.INSUFFICIENT_EVIDENCE.value
        pair_reason = 'pitch_roll_yaw_delta_exceeds_same_pose_threshold'
    elif min(usable_a, usable_b) < MIN_COMMON_USABLE_ZONES:
        pair_status = PairStatus.INSUFFICIENT_EVIDENCE.value
        pair_reason = 'too_few_usable_zones_on_one_or_both_packages'
    elif n_ok < MIN_COMMON_USABLE_ZONES:
        pair_status = PairStatus.INSUFFICIENT_EVIDENCE.value
        pair_reason = 'too_few_comparable_zones_after_gates'
    else:
        pair_status = PairStatus.PARTIAL_MATCH.value
        pair_reason = 'ok_primary_candidate'

    out = {
        'schema': SCHEMAS['pair'],
        'implementation_status': 'v5_pose_delta_and_soft_policy',
        'production_evidence_allowed': pair_status == PairStatus.PARTIAL_MATCH.value and geom_ok,
        'photo_a': a.manifest['photo_id'],
        'photo_b': b.manifest['photo_id'],
        'yaw_a': yaw_a, 'pitch_a': pitch_a, 'roll_a': roll_a,
        'yaw_b': yaw_b, 'pitch_b': pitch_b, 'roll_b': roll_b,
        'pose_delta_gate': delta_meta,
        'usable_zones_a': usable_a,
        'usable_zones_b': usable_b,
        'comparable_zones': n_ok,
        'pair_status': pair_status,
        'pair_reason': pair_reason,
        'zones': zones,
        'rule': 'same-pose requires yaw/pitch/roll deltas + common usable zones; pose CSV is soft prior; never invent zero difference',
        'pose_policy': str(DEFAULT_ATLAS_CSV) if policy else 'unavailable',
    }

    for key, fn in [
        ('quality_matching', compare_sensitivity_packages),
        ('texture', compare_texture),
        ('wrinkles', match_wrinkle_packages),
        ('local_features', match_local_features),
    ]:
        try:
            if not geom_ok:
                out[key] = {'status': 'insufficient_evidence', 'reason': 'pose_delta_gate'}
            else:
                out[key] = fn(a, b)
        except Exception as e:
            out[key] = {'status': 'insufficient_evidence', 'error': str(e), 'implementation': 'v5'}
    return out
