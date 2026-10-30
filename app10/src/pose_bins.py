from __future__ import annotations
from pathlib import Path
import yaml

CFG = Path(__file__).resolve().parents[1] / "configs" / "pose_bins.yaml"


def load_bins():
    d = yaml.safe_load(CFG.read_text())
    return d["bins"]


def classify_pose(yaw: float):
    y = float(yaw)
    for b in load_bins():
        if b["lo"] <= y < b["hi"]:
            return b["name"], float(b["canonical_yaw"])
    # fallback
    if y >= 0:
        return "right_profile", 70.0
    return "left_profile", -70.0
