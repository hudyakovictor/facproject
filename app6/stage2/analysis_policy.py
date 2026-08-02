"""Validated geometry policy for the production longitudinal analysis.

Values are frozen from DCRD + SGT-Chrono + 300-simulation selection.  Pose-bin
boundaries remain unchanged; this module only governs comparisons inside a bin.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Final
import numpy as np

ANALYSIS_COORDINATE_SPACE: Final[str] = "raw_object_normalized"
MAX_YAW_GAP_DEG: Final[float] = 6.0
MAX_PITCH_GAP_DEG: Final[float] = 2.0
MAX_ROLL_GAP_DEG: Final[float] = 5.0
MIN_ALIGNMENT_QUALITY: Final[float] = 0.5
FDR_LEVEL: Final[float] = 0.05

@dataclass(frozen=True)
class PoseGap:
    pitch: float
    yaw: float
    roll: float
    accepted: bool
    reason: str


def pose_gap(angles_a, angles_b) -> PoseGap:
    """Fail-closed axis-specific residual-pose gate for an in-bin pair."""
    a=np.asarray(angles_a,dtype=float).reshape(-1)
    b=np.asarray(angles_b,dtype=float).reshape(-1)
    if a.size != 3 or b.size != 3 or not (np.isfinite(a).all() and np.isfinite(b).all()):
        return PoseGap(float("nan"),float("nan"),float("nan"),False,"nonfinite_pose")
    pitch,yaw,roll=map(float,np.abs(a-b))
    if yaw > MAX_YAW_GAP_DEG: return PoseGap(pitch,yaw,roll,False,"yaw_gap")
    if pitch > MAX_PITCH_GAP_DEG: return PoseGap(pitch,yaw,roll,False,"pitch_gap")
    if roll > MAX_ROLL_GAP_DEG: return PoseGap(pitch,yaw,roll,False,"roll_gap")
    return PoseGap(pitch,yaw,roll,True,"")
