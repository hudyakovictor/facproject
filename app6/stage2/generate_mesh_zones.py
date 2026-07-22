#!/usr/bin/env python3
"""Generate anatomical mesh_zone_indices.json from a BFM reconstruction.

This script creates proper anatomical zone vertex assignments using
UV-space anatomical regions from uv_module/zones.py as the canonical
definition. It maps each UV zone box to vertex indices via their
UV coordinates, producing zones with adequate vertex counts and no
overlaps.

Usage:
    python -m app6.stage2.generate_mesh_zones [reconstruction.npz]

If no reconstruction.npz is provided, it attempts to find one in the
output directory.
🏭 CONVENTIONS v2 → генератор mesh_zone_indices.json; статус: ✅ VERIFIED
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


# Canonical UV zone definitions (must match uv_module/zones.py)
# Each zone is defined as (u_min, v_min, u_max, v_max) in UV space.
# These are derived from the BFM UV atlas layout.
ZONE_UV_BOXES = {
    "forehead":            (0.20, 0.70, 0.80, 0.95),
    "brow_ridge_L":        (0.20, 0.60, 0.45, 0.72),
    "brow_ridge_R":        (0.55, 0.60, 0.80, 0.72),
    "orbit_L":             (0.18, 0.48, 0.42, 0.62),
    "orbit_R":             (0.58, 0.48, 0.82, 0.62),
    "nose_bridge_tip":     (0.38, 0.42, 0.62, 0.58),
    "nose_wing_L":         (0.28, 0.38, 0.42, 0.50),
    "nose_wing_R":         (0.58, 0.38, 0.72, 0.50),
    "cheekbone_L":         (0.08, 0.35, 0.30, 0.60),
    "cheekbone_R":         (0.70, 0.35, 0.92, 0.60),
    "cheek_soft_L":        (0.10, 0.18, 0.32, 0.38),
    "cheek_soft_R":        (0.68, 0.18, 0.90, 0.38),
    "jaw_L":               (0.08, 0.08, 0.35, 0.22),
    "jaw_R":               (0.65, 0.08, 0.92, 0.22),
    "jaw_angle_L":         (0.05, 0.05, 0.20, 0.18),
    "jaw_angle_R":         (0.80, 0.05, 0.95, 0.18),
    "chin":                (0.30, 0.02, 0.70, 0.15),
    "temporal_L":          (0.02, 0.45, 0.18, 0.75),
    "temporal_R":          (0.82, 0.45, 0.98, 0.75),
    "ligament_orbital_L":  (0.15, 0.45, 0.28, 0.55),
    "ligament_orbital_R":  (0.72, 0.45, 0.85, 0.55),
    "ligament_zygomatic_L":(0.10, 0.32, 0.22, 0.45),
    "ligament_zygomatic_R":(0.78, 0.32, 0.90, 0.45),
}

# Priority order for vertex assignment when zones overlap.
# Higher-priority zones claim vertices first; lower-priority zones get only
# unclaimed vertices. This prevents the overlap problem where nose_wing_L
# was 100% contained within nose_bridge_tip.
ZONE_PRIORITY = [
    "orbit_L", "orbit_R",                           # eyes first (most distinct)
    "nose_wing_L", "nose_wing_R",                    # nose wings
    "nose_bridge_tip",                               # bridge/tip
    "brow_ridge_L", "brow_ridge_R",                  # brows
    "chin",                                          # chin
    "cheekbone_L", "cheekbone_R",                    # cheekbones
    "jaw_L", "jaw_R",                                # jaw
    "jaw_angle_L", "jaw_angle_R",                    # jaw angles
    "ligament_orbital_L", "ligament_orbital_R",      # orbital ligaments
    "ligament_zygomatic_L", "ligament_zygomatic_R",  # zygomatic ligaments
    "temporal_L", "temporal_R",                      # temples
    "cheek_soft_L", "cheek_soft_R",                  # soft cheeks
    "forehead",                                      # forehead (broad, last)
]


# 🏭 FACTORY → анатомические зоны вершин из UV-координат
def generate_zones(uv_coords: np.ndarray) -> dict[str, list[int]]:
    """Generate anatomical zone vertex assignments from UV coordinates.

    Args:
        uv_coords: (N, 2) array of UV coordinates in [0, 1] range.

    Returns:
        Dictionary mapping zone name to list of vertex indices.
    """
    n_vertices = uv_coords.shape[0]
    u = uv_coords[:, 0]
    v = uv_coords[:, 1]

    # Track which vertices are already assigned to avoid overlaps
    assigned = np.full(n_vertices, -1, dtype=np.int32)  # -1 = unassigned
    zones: dict[str, list[int]] = {}

    for zone_name in ZONE_PRIORITY:
        box = ZONE_UV_BOXES[zone_name]
        umin, vmin, umax, vmax = box

        # Find vertices in this UV box that haven't been assigned yet
        in_box = (
            (u >= umin) & (u <= umax) &
            (v >= vmin) & (v <= vmax) &
            (assigned == -1)
        )
        indices = np.flatnonzero(in_box).tolist()

        # Mark as assigned
        for idx in indices:
            assigned[idx] = list(ZONE_UV_BOXES.keys()).index(zone_name)

        zones[zone_name] = indices

    # Report stats
    total_assigned = int(np.sum(assigned >= 0))
    print(f"Total vertices: {n_vertices}")
    print(f"Assigned to zones: {total_assigned} ({100*total_assigned/n_vertices:.1f}%)")
    print(f"Unassigned: {n_vertices - total_assigned}")
    print()
    for name in ZONE_PRIORITY:
        count = len(zones.get(name, []))
        status = "⚠️ TOO FEW" if count < 40 else "✅"
        print(f"  {name:30s}  {count:5d} vertices  {status}")

    return zones


# 🚪 ENTRY POINT генератора зон
def main():
    if len(sys.argv) > 1:
        npz_path = Path(sys.argv[1])
    else:
        # Try to find a reconstruction.npz
        project_root = Path(__file__).resolve().parents[2]
        candidates = list(project_root.rglob("reconstruction.npz"))
        if not candidates:
            print("ERROR: No reconstruction.npz found. Provide path as argument.")
            sys.exit(1)
        npz_path = candidates[0]
        print(f"Using: {npz_path}")

    with np.load(npz_path, allow_pickle=False) as z:
        if "uv_coords" not in z:
            print("ERROR: reconstruction.npz missing uv_coords")
            sys.exit(1)
        uv_coords = z["uv_coords"][:, :2]  # Take only u, v

    zones = generate_zones(uv_coords)

    # Write output
    out_path = Path(__file__).with_name("mesh_zone_indices.json")
    out_path.write_text(json.dumps(zones, indent=2), encoding="utf-8")
    print(f"\nWritten to: {out_path}")


if __name__ == "__main__":
    main()
