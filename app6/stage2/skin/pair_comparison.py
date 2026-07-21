"""
Drop-in replacement for app6/stage2/skin/pair_comparison.py
Adds pose compatibility gate + common observed gate + full readiness.

Same function signature: def compare_packages(a,b,min_common=.35)
"""
from __future__ import annotations
import numpy as np
from pathlib import Path
from app6.stage1.skin.contracts import PairStatus, SCHEMAS
from app6.stage1.skin.pose_policy import PosePolicy
from .applicability import common_surface
from .texture_comparison import compare_texture
from .wrinkle_matching import match_wrinkle_packages
from .local_feature_matching import match_local_features
from .quality_matching import compare_sensitivity_packages

DEFAULT_ATLAS_CSV = Path(__file__).resolve().parents[2]/'atlas/pose_policy_v3_9bins.csv'

def compare_packages(a,b,min_common=.35):
    # Load pose policy if available
    try:
        policy = PosePolicy(DEFAULT_ATLAS_CSV) if DEFAULT_ATLAS_CSV.exists() else None
    except:
        policy = None

    # Try to get yaw from manifests
    try:
        yaw_a = float(a.json('quality.json').get('pose',{}).get('yaw', 0))
        yaw_b = float(b.json('quality.json').get('pose',{}).get('yaw', 0))
    except:
        yaw_a = yaw_b = 0.0

    with a.surface() as sa, a.atlas() as aa, b.surface() as sb, b.atlas() as ab:
        zones=[]
        for z in range(20):
            c = common_surface(sa,sb,aa,ab,'A',z)
            coverage = float(c.get('coverage_sym', 0))
            zone_id = f'A{z+1:02d}'
            if policy:
                compatible, combined_w, reason = policy.is_compatible(zone_id, yaw_a, yaw_b)
                gate_status, effective = policy.common_observed_gate(coverage, combined_w)
                if not compatible:
                    status = PairStatus.NOT_COMPARABLE.value
                elif gate_status == 'INSUFFICIENT_EVIDENCE' or coverage < min_common:
                    status = PairStatus.INSUFFICIENT_EVIDENCE.value
                elif gate_status == 'COARSE_ONLY':
                    status = PairStatus.COARSE_DIRECTION_MATCH.value
                else:
                    status = PairStatus.PARTIAL_MATCH.value
            else:
                combined_w = 1.0
                reason = 'no policy'
                effective = coverage
                status = PairStatus.INSUFFICIENT_EVIDENCE.value if coverage < min_common else PairStatus.PARTIAL_MATCH.value
                gate_status = status

            zones.append({
                'zone': zone_id,
                'status': status,
                'coverage_sym': coverage,
                'effective_coverage': effective,
                'pose_compatible': compatible if policy else True,
                'pose_combined_weight': combined_w,
                'pose_reason': reason,
                'pose_gate': gate_status if policy else 'no_gate',
                **{k:v for k,v in c.items() if k!='triangle_ids'},
                'common_triangle_ids': c['triangle_ids'].tolist(),
                'yaw_a': yaw_a,
                'yaw_b': yaw_b,
            })

    out = {
        'schema': SCHEMAS['pair'],
        'implementation_status': 'v4_pose_aware_common_surface',
        'production_evidence_allowed': True,
        'photo_a': a.manifest['photo_id'],
        'photo_b': b.manifest['photo_id'],
        'yaw_a': yaw_a,
        'yaw_b': yaw_b,
        'zones': zones,
        'rule': 'no common observed surface => insufficient evidence; pose incompatible => not comparable; never zero difference',
        'pose_policy': str(DEFAULT_ATLAS_CSV) if policy else 'unavailable',
    }

    for key,fn in [('quality_matching',compare_sensitivity_packages),('texture',compare_texture),('wrinkles',match_wrinkle_packages),('local_features',match_local_features)]:
        try:
            out[key] = fn(a,b)
        except Exception as e:
            out[key] = {'status':'insufficient_evidence','error':str(e), 'implementation':'v4'}
    return out
