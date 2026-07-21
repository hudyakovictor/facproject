"""
Drop-in replacement for app6/stage1/skin/pose_policy.py
Keeps original class name PosePolicy for backward compat, but implements full 9-bin logic
with compatibility checks, common observed gate, and improved weights.

Original file was 29 lines, only weights(). New file adds is_compatible(), common_observed_gate(),
and get() etc, but keeps weights() signature: weights(A, yaw) -> (weight_map, meta)

CSV schema supported: both old (zone_code,yaw_bin_center_deg,status,weight) and legacy (zone_id,yaw_bin,role,weight)
"""
from __future__ import annotations
import csv
import numpy as np
from pathlib import Path
from typing import Dict, Tuple

YAW_BINS = [-60, -40, -25, -10, 0, 10, 25, 40, 60]

def yaw_to_bin(yaw_deg: float) -> int:
    diffs = [abs(float(yaw_deg) - b) for b in YAW_BINS]
    return YAW_BINS[int(np.argmin(diffs))]

class PosePolicy:
    """
    Backward compatible name, but implements full v3 logic.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.rows: Dict[Tuple[str,int], Tuple[str,float]] = {}
        self.centers = YAW_BINS
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
                    except:
                        yaw = 0
                    status = (r.get('status') or r.get('role') or 'exclude').strip()
                    weight = float(r.get('weight', 0.0))
                    self.rows[(zone, yaw)] = (status, weight)
            if self.rows:
                self.centers = sorted({y for _, y in self.rows.keys()})
        except Exception:
            # fallback build default
            self._build_default()

    def _build_default(self):
        # frontal zones primary within +-25, support +-40, limited +-60
        frontal = {f'A{i:02d}' for i in [1,2,3,4,5,6,13,14,15,16,19,20]}
        left = {f'A{i:02d}' for i in [7,9,11,17]}   # anatomical left
        right = {f'A{i:02d}' for i in [8,10,12,18]}
        for zone in [f'A{i:02d}' for i in range(1,21)]:
            for yaw in YAW_BINS:
                if zone in frontal:
                    if abs(yaw) <= 25:
                        role,w = 'primary',1.0
                    elif abs(yaw) <= 40:
                        role,w = 'support',0.6
                    elif abs(yaw) <= 60:
                        role,w = 'limited',0.25
                    else:
                        role,w = 'exclude',0.0
                elif zone in left:
                    if 10 <= yaw <= 40:
                        role,w = 'primary',1.0
                    elif -10 <= yaw < 10:
                        role,w = 'support',0.6
                    elif -25 <= yaw < -10:
                        role,w = 'limited',0.25
                    else:
                        role,w = 'exclude',0.0
                elif zone in right:
                    if -40 <= yaw <= -10:
                        role,w = 'primary',1.0
                    elif -10 < yaw <= 10:
                        role,w = 'support',0.6
                    elif 10 < yaw <= 25:
                        role,w = 'limited',0.25
                    else:
                        role,w = 'exclude',0.0
                else:
                    role,w = 'primary',1.0
                self.rows[(zone, yaw)] = (role,w)

    def get(self, zone_id: str, yaw_deg: float) -> Tuple[str,float]:
        bin_yaw = yaw_to_bin(yaw_deg)
        return self.rows.get((zone_id, bin_yaw), ('exclude', 0.0))

    def weights(self, A, yaw):
        """
        Original signature: weights(A, yaw) -> (weight_map, meta)
        A: np.ndarray HxW with zone ids 0..19 (int) or -1 background
        yaw: float
        Returns: weight map same shape, meta dict
        """
        # select nearest center
        try:
            c = min(self.centers, key=lambda x: abs(x-float(yaw)))
        except:
            c = yaw_to_bin(yaw)
        # build LUT for 0..19
        lut = np.zeros(20, dtype=np.float32)
        per_zone = {}
        for i in range(20):
            zone_str = f'A{i+1:02d}'
            role,w = self.rows.get((zone_str, c), ('exclude',0.0))
            lut[i] = w
            per_zone[zone_str] = {'role': role, 'weight': w, 'yaw_bin': c}
        A_arr = np.asarray(A)
        if A_arr.dtype.kind in 'UO':
            # string map
            w_map = np.zeros(A_arr.shape, dtype=np.float32)
            for i in range(20):
                zone_str = f'A{i+1:02d}'
                _, weight = self.rows.get((zone_str, c), ('exclude',0.0))
                w_map[A_arr == zone_str] = weight
        else:
            # int map, -1 background
            valid = (A_arr>=0)&(A_arr<20)
            w_map = np.zeros(A_arr.shape, dtype=np.float32)
            w_map[valid] = lut[A_arr[valid].astype(int)]
        meta = {
            'yaw_input_deg': float(yaw),
            'selected_center_deg': int(c),
            'yaw_bin': int(c),
            'convention': '+yaw exposes anatomical-left; qualify against 3DDFA golden poses',
            'per_zone': per_zone,
        }
        return w_map, meta

    # --- NEW METHODS for 100% readiness ---

    def is_compatible(self, zone_id: str, yaw_a: float, yaw_b: float) -> Tuple[bool,float,str]:
        bin_a = yaw_to_bin(yaw_a)
        bin_b = yaw_to_bin(yaw_b)
        role_a,w_a = self.rows.get((zone_id, bin_a), ('exclude',0.0))
        role_b,w_b = self.rows.get((zone_id, bin_b), ('exclude',0.0))
        if role_a == 'exclude' or role_b == 'exclude':
            return False, 0.0, f'exclude: {zone_id} {bin_a}:{role_a} vs {bin_b}:{role_b}'
        if role_a == 'limited' and role_b == 'limited':
            return False, 0.0, f'both limited {zone_id}'
        combined = float(np.sqrt(max(w_a,0)*max(w_b,0)))
        if combined < 0.25:
            return False, combined, f'low combined weight {combined:.2f}'
        return True, combined, f'ok {role_a}({w_a})+{role_b}({w_b})=>{combined:.2f}'

    def common_observed_gate(self, coverage_sym: float, weight_combined: float) -> Tuple[str,float]:
        effective = float(coverage_sym * weight_combined)
        if coverage_sym < 0.35:
            return 'INSUFFICIENT_EVIDENCE', effective
        if effective < 0.20:
            return 'NOT_COMPARABLE', effective
        if effective < 0.45:
            return 'COARSE_ONLY', effective
        return 'USABLE', effective
