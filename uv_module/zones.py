"""Stage-1 compatibility boundary.

Anatomical skin zones are not part of the replacement UV core. The existing
app6/stage1/assets.py imports ZONE_SPECS while writing a legacy empty wrinkle
report, so an empty immutable registry is exposed until that legacy export is
removed from Stage 1.
"""
from __future__ import annotations

ZONE_SPECS: tuple = ()
POSE_POLICY: dict = {}

def policy_weight(pose_bin: str, zone_name: str) -> float:
    return 0.0

def zone_vertex_masks(*args, **kwargs) -> dict:
    return {}
