"""Pose policy — CSV-backed zone visibility weights with soft-evidence path.

CSV specifies a prior; soft_evidence_weights never hard-kills observed pixels.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

YAW_BINS = [-60, -40, -25, -10, 0, 10, 25, 40, 60]
SOFT_EXCLUDE_FLOOR = 0.35
SOFT_LIMITED_FLOOR = 0.50
MAX_YAW_DELTA = 12.0
MAX_PITCH_DELTA = 12.0
MAX_ROLL_DELTA = 12.0
MIN_COMMON_USABLE_ZONES = 4
MIN_COVERAGE_SYM = 0.35


def yaw_to_bin(yaw_deg: float) -> int:
    diffs = [abs(float(yaw_deg) - b) for b in YAW_BINS]
    return YAW_BINS[int(np.argmin(diffs))]


class PosePolicy:
    """CSV-backed pose prior with explicit soft-evidence path."""

    def __init__(self, path: Path, *, allow_default: bool = False):
        self.path = Path(path)
        self.rows: dict[Tuple[str, int], Tuple[str, float]] = {}
        self.centers = list(YAW_BINS)
        self.source = "csv"

        if not self.path.is_file():
            if allow_default:
                self._build_default()
                self.source = "default_missing_csv"
                return
            raise FileNotFoundError(f"pose policy CSV not found: {self.path}")

        with open(self.path, encoding="utf8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                zone = (r.get("zone_code") or r.get("zone_id") or "").strip()
                if not zone:
                    continue
                yaw_raw = r.get("yaw_bin_center_deg") or r.get("yaw_bin") or "0"
                yaw = int(float(yaw_raw))
                status = (r.get("status") or r.get("role") or "exclude").strip()
                weight = float(r.get("weight", 0.0))
                self.rows[(zone, yaw)] = (status, weight)
        if not self.rows:
            raise ValueError(f"pose policy CSV empty/unparsed: {self.path}")
        self.centers = sorted({y for _, y in self.rows.keys()})
        self.source = f"csv:{self.path.name}"

    def _build_default(self) -> None:
        frontal = {f"A{i:02d}" for i in [1, 2, 3, 4, 5, 6, 8, 15, 19, 20]}
        left = {f"A{i:02d}" for i in [9, 11, 13, 17]}
        right = {f"A{i:02d}" for i in [7, 10, 12, 14, 16, 18]}
        for zone in [f"A{i:02d}" for i in range(1, 21)]:
            for yaw in YAW_BINS:
                if zone in frontal:
                    if abs(yaw) <= 25: role, w = "primary", 1.0
                    elif abs(yaw) <= 40: role, w = "support", 0.6
                    elif abs(yaw) <= 60: role, w = "limited", 0.25
                    else: role, w = "exclude", 0.0
                elif zone in left:
                    if yaw >= 10: role, w = ("primary", 1.0) if yaw <= 40 else ("support", 0.6) if yaw <= 60 else ("exclude", 0.0)
                    elif abs(yaw) < 10: role, w = "support", 0.6
                    elif yaw >= -25: role, w = "limited", 0.25
                    else: role, w = "exclude", 0.0
                elif zone in right:
                    if yaw <= -10: role, w = ("primary", 1.0) if yaw >= -40 else ("support", 0.6) if yaw >= -60 else ("exclude", 0.0)
                    elif abs(yaw) < 10: role, w = "support", 0.6
                    elif yaw <= 25: role, w = "limited", 0.25
                    else: role, w = "exclude", 0.0
                else: role, w = "primary", 1.0
                self.rows[(zone, yaw)] = (role, w)

    def _selected_center(self, yaw: float) -> int:
        return int(min(self.centers, key=lambda x: abs(x - float(yaw))))

    def weights(self, A: np.ndarray, yaw: float) -> Tuple[np.ndarray, dict]:
        """CSV prior weight map (may contain zeros for excluded zones)."""
        c = self._selected_center(yaw)
        lut = np.zeros(20, dtype=np.float32)
        per_zone = {}
        for i in range(20):
            zone_str = f"A{i + 1:02d}"
            role, w = self.rows.get((zone_str, c), ("exclude", 0.0))
            lut[i] = w
            per_zone[zone_str] = {"role": role, "weight": float(w), "yaw_bin": int(c)}
        A_arr = np.asarray(A)
        valid = (A_arr >= 0) & (A_arr < 20)
        w_map = np.zeros(A_arr.shape, dtype=np.float32)
        w_map[valid] = lut[A_arr[valid].astype(int)]
        meta = {
            "yaw_input_deg": float(yaw),
            "selected_center_deg": int(c),
            "per_zone": per_zone,
            "policy_source": self.source,
            "hard_exclude_kills_evidence": False,
            "soft_exclude_floor": SOFT_EXCLUDE_FLOOR,
        }
        return w_map, meta

    def soft_evidence_weights(
        self, A: np.ndarray, yaw: float, *,
        domain: np.ndarray, projection_confidence: np.ndarray,
        incidence: np.ndarray, visibility: Optional[np.ndarray] = None,
        conf_thr: float = 0.18, inc_thr: float = 0.12, vis_thr: float = 0.15,
    ) -> Tuple[np.ndarray, dict, np.ndarray]:
        """Evidence multiplier: CSV prior as soft prior, observed pixels get a floor."""
        prior, meta = self.weights(A, yaw)
        d = np.asarray(domain, bool)
        conf = np.asarray(projection_confidence, np.float32)
        inc = np.asarray(incidence, np.float32)
        vis = np.asarray(visibility, np.float32) if visibility is not None else np.ones(d.shape, np.float32)
        observed = d & (conf >= conf_thr) & (inc >= inc_thr) & (vis >= vis_thr)
        soft = prior.copy()
        A_arr = np.asarray(A)
        c = int(meta["selected_center_deg"])
        for i in range(20):
            zone = f"A{i + 1:02d}"
            role, w = self.rows.get((zone, c), ("exclude", 0.0))
            m = observed & (A_arr == i)
            if not np.any(m):
                continue
            if role == "exclude" or w <= 0:
                soft[m] = np.maximum(soft[m], SOFT_EXCLUDE_FLOOR)
            elif role == "limited" or w < 0.5:
                soft[m] = np.maximum(soft[m], SOFT_LIMITED_FLOOR)
            else:
                soft[m] = np.maximum(soft[m], float(w))
        soft = np.where(d, soft, 0.0).astype(np.float32)
        soft = np.where(observed | (prior > 0), soft, 0.0).astype(np.float32)
        meta = dict(meta)
        meta.update({
            "soft_evidence": True,
            "observed_pixels": int(observed.sum()),
            "soft_boosted_pixels": int(((prior <= 0) & (soft > 0) & observed).sum()),
        })
        return soft, meta, observed

    @staticmethod
    def pose_delta_gate(
        yaw_a: float, pitch_a: float, roll_a: float,
        yaw_b: float, pitch_b: float, roll_b: float, *,
        max_yaw: float = MAX_YAW_DELTA,
        max_pitch: float = MAX_PITCH_DELTA,
        max_roll: float = MAX_ROLL_DELTA,
    ) -> Tuple[bool, dict]:
        dy = abs(float(yaw_a) - float(yaw_b))
        dp = abs(float(pitch_a) - float(pitch_b))
        dr = abs(float(roll_a) - float(roll_b))
        ok = (dy <= max_yaw) and (dp <= max_pitch) and (dr <= max_roll)
        return ok, {
            "yaw_delta": dy, "pitch_delta": dp, "roll_delta": dr,
            "same_pose_geometry_ok": ok,
            "reason": "ok" if ok else "pose_delta_exceeds_threshold",
        }
