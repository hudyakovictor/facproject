"""Pose policy with loud CSV load, soft evidence weights, pitch/roll gates.

BREAKING behavior vs old silent fallback:
- missing/unreadable CSV raises FileNotFoundError/ValueError (no silent default)
- weights() still returns CSV prior map
- soft_evidence_weights() never hard-zeros observed visible pixels solely because CSV says exclude
"""
from __future__ import annotations
import csv
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
from ..status_logger import log_status, log_blocker, log_warning

YAW_BINS = [-60, -40, -25, -10, 0, 10, 25, 40, 60]

# Soft floor for evidence extraction when geometry is actually observed.
# CSV exclude remains a comparison prior, not a hard evidence kill.
SOFT_EXCLUDE_FLOOR = 0.35
SOFT_LIMITED_FLOOR = 0.50

# Same-pose pairing thresholds (degrees)
MAX_YAW_DELTA_PRIMARY = 12.0
MAX_PITCH_DELTA_PRIMARY = 12.0
MAX_ROLL_DELTA_PRIMARY = 12.0
MIN_COMMON_USABLE_ZONES = 4
MIN_COVERAGE_SYM = 0.35


def yaw_to_bin(yaw_deg: float) -> int:
    diffs = [abs(float(yaw_deg) - b) for b in YAW_BINS]
    return YAW_BINS[int(np.argmin(diffs))]


class PosePolicy:
    """CSV-backed pose prior with explicit soft-evidence path."""

    def __init__(self, path, *, allow_default: bool = False):
        self.path = Path(path)
        self.rows: Dict[Tuple[str, int], Tuple[str, float]] = {}
        self.centers = list(YAW_BINS)
        self.source = 'csv'
        self.allow_default = bool(allow_default)

        if not self.path.is_file():
            if self.allow_default:
                self._build_default()
                self.source = 'default_missing_csv'
                return
            raise FileNotFoundError(
                f'pose policy CSV not found: {self.path}. '
                f'Place pose_policy_v3_9bins.csv next to atlas or pass an absolute path.'
            )

        try:
            with open(self.path, encoding='utf8') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    zone = (r.get('zone_code') or r.get('zone_id') or '').strip()
                    if not zone:
                        continue
                    yaw_raw = r.get('yaw_bin_center_deg') or r.get('yaw_bin') or '0'
                    try:
                        yaw = int(float(yaw_raw))
                    except Exception as exc:
                        raise ValueError(f'invalid yaw in {self.path}: {yaw_raw}') from exc
                    status = (r.get('status') or r.get('role') or 'exclude').strip()
                    weight = float(r.get('weight', 0.0))
                    self.rows[(zone, yaw)] = (status, weight)
            if not self.rows:
                raise ValueError(f'pose policy CSV empty/unparsed: {self.path}')
            self.centers = sorted({y for _, y in self.rows.keys()})
            self.source = f'csv:{self.path.name}'
        except FileNotFoundError:
            raise
        except Exception as exc:
            if self.allow_default:
                self._build_default()
                self.source = f'default_after_error:{type(exc).__name__}'
                return
            raise ValueError(f'failed to load pose policy CSV {self.path}: {exc}') from exc

    def _build_default(self):
        # Kept only for explicit allow_default=True emergency use.
        # Side sets aligned closer to CSV v3 profile semantics.
        frontal = {f'A{i:02d}' for i in [1, 2, 3, 4, 5, 6, 8, 15, 19, 20]}
        # anatomical-left exposed by +yaw
        left = {f'A{i:02d}' for i in [9, 11, 13, 17]}
        # anatomical-right exposed by -yaw
        right = {f'A{i:02d}' for i in [7, 10, 12, 14, 16, 18]}
        for zone in [f'A{i:02d}' for i in range(1, 21)]:
            for yaw in YAW_BINS:
                if zone in frontal:
                    if abs(yaw) <= 25:
                        role, w = 'primary', 1.0
                    elif abs(yaw) <= 40:
                        role, w = 'support', 0.6
                    elif abs(yaw) <= 60:
                        role, w = 'limited', 0.25
                    else:
                        role, w = 'exclude', 0.0
                elif zone in left:
                    if yaw >= 10:
                        role, w = ('primary', 1.0) if yaw <= 40 else ('support', 0.6) if yaw <= 60 else ('exclude', 0.0)
                    elif abs(yaw) < 10:
                        role, w = 'support', 0.6
                    elif yaw >= -25:
                        role, w = 'limited', 0.25
                    else:
                        role, w = 'exclude', 0.0
                elif zone in right:
                    if yaw <= -10:
                        role, w = ('primary', 1.0) if yaw >= -40 else ('support', 0.6) if yaw >= -60 else ('exclude', 0.0)
                    elif abs(yaw) < 10:
                        role, w = 'support', 0.6
                    elif yaw <= 25:
                        role, w = 'limited', 0.25
                    else:
                        role, w = 'exclude', 0.0
                else:
                    role, w = 'primary', 1.0
                self.rows[(zone, yaw)] = (role, w)

    def get(self, zone_id: str, yaw_deg: float) -> Tuple[str, float]:
        bin_yaw = yaw_to_bin(yaw_deg)
        return self.rows.get((zone_id, bin_yaw), ('exclude', 0.0))

    def _selected_center(self, yaw: float) -> int:
        try:
            return int(min(self.centers, key=lambda x: abs(x - float(yaw))))
        except Exception:
            return int(yaw_to_bin(yaw))

    def weights(self, A, yaw):
        """CSV prior weight map (may contain zeros). Used as comparison prior."""
        c = self._selected_center(yaw)
        lut = np.zeros(20, dtype=np.float32)
        per_zone = {}
        for i in range(20):
            zone_str = f'A{i+1:02d}'
            role, w = self.rows.get((zone_str, c), ('exclude', 0.0))
            lut[i] = w
            per_zone[zone_str] = {'role': role, 'weight': float(w), 'yaw_bin': int(c)}
        A_arr = np.asarray(A)
        if A_arr.dtype.kind in 'UO':
            w_map = np.zeros(A_arr.shape, dtype=np.float32)
            for i in range(20):
                zone_str = f'A{i+1:02d}'
                _, weight = self.rows.get((zone_str, c), ('exclude', 0.0))
                w_map[A_arr == zone_str] = weight
        else:
            valid = (A_arr >= 0) & (A_arr < 20)
            w_map = np.zeros(A_arr.shape, dtype=np.float32)
            w_map[valid] = lut[A_arr[valid].astype(int)]
        meta = {
            'yaw_input_deg': float(yaw),
            'selected_center_deg': int(c),
            'yaw_bin': int(c),
            'convention': '+yaw exposes anatomical-left; qualify against 3DDFA golden poses',
            'per_zone': per_zone,
            'policy_source': self.source,
            'policy_path': str(self.path),
            'hard_exclude_kills_evidence': False,
            'soft_exclude_floor': SOFT_EXCLUDE_FLOOR,
        }
        return w_map, meta

    def soft_evidence_weights(
        self,
        A,
        yaw,
        *,
        domain: np.ndarray,
        projection_confidence: np.ndarray,
        incidence: np.ndarray,
        visibility: Optional[np.ndarray] = None,
        conf_thr: float = 0.18,
        inc_thr: float = 0.12,
        vis_thr: float = 0.15,
    ):
        """Evidence multiplier: CSV prior as soft prior, no hard kill on observed pixels.

        If CSV exclude/limited but pixel is geometrically observed with enough conf/incidence,
        keep a soft floor so features can still be extracted on visible cheek/jaw regions.
        """
        prior, meta = self.weights(A, yaw)
        d = np.asarray(domain, bool)
        conf = np.asarray(projection_confidence, np.float32)
        inc = np.asarray(incidence, np.float32)
        if visibility is None:
            vis = np.ones(d.shape, np.float32)
        else:
            vis = np.asarray(visibility, np.float32)

        observed = d & (conf >= conf_thr) & (inc >= inc_thr) & (vis >= vis_thr)
        soft = prior.copy()
        # floors by prior role
        A_arr = np.asarray(A)
        c = int(meta['selected_center_deg'])
        for i in range(20):
            zone = f'A{i+1:02d}'
            role, w = self.rows.get((zone, c), ('exclude', 0.0))
            m = observed & (A_arr == i)
            if not np.any(m):
                continue
            if role == 'exclude' or w <= 0:
                soft[m] = np.maximum(soft[m], SOFT_EXCLUDE_FLOOR)
            elif role == 'limited' or w < 0.5:
                soft[m] = np.maximum(soft[m], SOFT_LIMITED_FLOOR)
            else:
                soft[m] = np.maximum(soft[m], float(w))

        # truly unobserved stays 0
        soft = np.where(d, soft, 0.0).astype(np.float32)
        soft = np.where(observed | (prior > 0), soft, 0.0).astype(np.float32)

        meta = dict(meta)
        meta.update({
            'soft_evidence': True,
            'conf_thr': conf_thr,
            'inc_thr': inc_thr,
            'vis_thr': vis_thr,
            'observed_pixels': int(observed.sum()),
            'soft_boosted_pixels': int(((prior <= 0) & (soft > 0) & observed).sum()),
        })
        return soft, meta, observed

    def is_compatible(self, zone_id: str, yaw_a: float, yaw_b: float) -> Tuple[bool, float, str]:
        bin_a = yaw_to_bin(yaw_a)
        bin_b = yaw_to_bin(yaw_b)
        role_a, w_a = self.rows.get((zone_id, bin_a), ('exclude', 0.0))
        role_b, w_b = self.rows.get((zone_id, bin_b), ('exclude', 0.0))
        # Soft-compat: exclude on one side no longer absolute ban if both have limited weight path;
        # still mark incompatible for primary claims when either is hard exclude prior.
        if role_a == 'exclude' or role_b == 'exclude':
            # allow coarse path via low combined weight instead of hard False when both bins close
            if abs(bin_a - bin_b) <= 20:
                combined = float(np.sqrt(max(SOFT_EXCLUDE_FLOOR, 0) * max(SOFT_EXCLUDE_FLOOR, 0)))
                return True, combined, f'soft-exclude-compat {zone_id} {bin_a}:{role_a} vs {bin_b}:{role_b}'
            return False, 0.0, f'exclude: {zone_id} {bin_a}:{role_a} vs {bin_b}:{role_b}'
        if role_a == 'limited' and role_b == 'limited':
            combined = float(np.sqrt(max(w_a, SOFT_LIMITED_FLOOR) * max(w_b, SOFT_LIMITED_FLOOR)))
            return True, combined, f'both limited soft {zone_id}'
        combined = float(np.sqrt(max(w_a, 0) * max(w_b, 0)))
        if combined < 0.25:
            return False, combined, f'low combined weight {combined:.2f}'
        return True, combined, f'ok {role_a}({w_a})+{role_b}({w_b})=>{combined:.2f}'

    def common_observed_gate(self, coverage_sym: float, weight_combined: float) -> Tuple[str, float]:
        effective = float(coverage_sym * weight_combined)
        if coverage_sym < MIN_COVERAGE_SYM:
            return 'INSUFFICIENT_EVIDENCE', effective
        if effective < 0.20:
            return 'NOT_COMPARABLE', effective
        if effective < 0.45:
            return 'COARSE_ONLY', effective
        return 'USABLE', effective

    @staticmethod
    def pose_delta_gate(
        yaw_a: float, pitch_a: float, roll_a: float,
        yaw_b: float, pitch_b: float, roll_b: float,
        *,
        max_yaw: float = MAX_YAW_DELTA_PRIMARY,
        max_pitch: float = MAX_PITCH_DELTA_PRIMARY,
        max_roll: float = MAX_ROLL_DELTA_PRIMARY,
    ) -> Tuple[bool, dict]:
        dy = abs(float(yaw_a) - float(yaw_b))
        dp = abs(float(pitch_a) - float(pitch_b))
        dr = abs(float(roll_a) - float(roll_b))
        ok = (dy <= max_yaw) and (dp <= max_pitch) and (dr <= max_roll)
        return ok, {
            'yaw_delta': dy,
            'pitch_delta': dp,
            'roll_delta': dr,
            'max_yaw': max_yaw,
            'max_pitch': max_pitch,
            'max_roll': max_roll,
            'same_pose_geometry_ok': ok,
            'reason': 'ok' if ok else 'pose_delta_exceeds_threshold',
        }
