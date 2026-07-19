"""UV-geometry pair comparison for Stage 2 (wrinkle / micro-relief chronology).

This module fills the critical gap identified in the Part-2 audit:
UV skin analysis is done at Stage 1 (via SkinAnalyzer), but the results
never reach Stage 2 pair comparison. Without this, chronological wrinkle
comparison — the core of the double theory investigation — is missing.

Contract:
    row, zone_rows = uv_geometry_pair(a, b, output_dir, pair_id)

Where `a` and `b` are Stage2 Record objects whose `record_dir` contains
a `texture_forensics.json` with UV geometry zone metrics from SkinAnalyzer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from app6.stage1.utils import atomic_json

UV_COMPARISON_SCHEMA = "deeputin-stage2-uv-geometry-v1.0"

# Zones where UV wrinkle comparison is most informative.
PRIORITY_UV_ZONES = (
    "forehead_horizontal_center",
    "forehead_horizontal_left",
    "forehead_horizontal_right",
    "glabella_vertical",
    "crow_feet_left",
    "crow_feet_right",
    "nasolabial_left",
    "nasolabial_right",
    "marionette_left",
    "marionette_right",
    "perioral_upper",
    "perioral_lower",
)


def _load_uv_forensics(record_dir: str | Path) -> dict[str, Any]:
    """Load UV forensics from a Stage 1 output directory."""
    p = Path(record_dir) / "texture_forensics.json"
    if not p.is_file():
        return {"status": "missing"}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"status": "load_error", "error": str(e)}


def _extract_uv_zones(forensics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract per-zone UV geometry metrics from forensics JSON."""
    zones: dict[str, dict[str, Any]] = {}

    # Try two-space forensics (v3.3+)
    uv_geo = forensics.get("uv_geometry", {})
    if uv_geo.get("available"):
        for zone_name, zone_data in uv_geo.get("zones", {}).items():
            zones[zone_name] = zone_data
        return zones

    # Fallback: old-format forensics (pre-v3.3)
    # Try wrinkle zones from pose_analysis
    wrinkle_zones = forensics.get("wrinkle_zones", {})
    if wrinkle_zones.get("zones"):
        for zone_name, zone_data in wrinkle_zones.get("zones", {}).items():
            zones[zone_name] = zone_data
        return zones

    return zones


def _zone_delta(
    zone_a: dict[str, Any],
    zone_b: dict[str, Any],
    zone_name: str,
) -> dict[str, Any]:
    """Compute deltas between two UV geometry zones."""
    result: dict[str, Any] = {
        "zone": zone_name,
        "status": "measured",
    }

    # Ridge density delta
    rd_a = float(zone_a.get("ridge_density", zone_a.get("features", {}).get("ridge_density", 0)))
    rd_b = float(zone_b.get("ridge_density", zone_b.get("features", {}).get("ridge_density", 0)))
    result["uv_ridge_density_a"] = rd_a
    result["uv_ridge_density_b"] = rd_b
    result["uv_ridge_density_delta"] = abs(rd_a - rd_b)

    # Branch count delta (skeleton graph)
    bc_a = float(zone_a.get("n_branches", zone_a.get("features", {}).get("n_branches",
                zone_a.get("skeleton_components", 0))))
    bc_b = float(zone_b.get("n_branches", zone_b.get("features", {}).get("n_branches",
                zone_b.get("skeleton_components", 0))))
    result["uv_branch_count_a"] = bc_a
    result["uv_branch_count_b"] = bc_b
    result["uv_branch_count_delta"] = abs(bc_a - bc_b)

    # Total length delta
    tl_a = float(zone_a.get("total_length_px", zone_a.get("features", {}).get("total_length_px", 0)))
    tl_b = float(zone_b.get("total_length_px", zone_b.get("features", {}).get("total_length_px", 0)))
    result["uv_total_length_a"] = tl_a
    result["uv_total_length_b"] = tl_b
    result["uv_total_length_delta"] = abs(tl_a - tl_b)

    # Branch density (per kpx)
    bd_a = float(zone_a.get("branch_density_per_kpx", zone_a.get("features", {}).get(
        "branch_density_per_kpx", 0)))
    bd_b = float(zone_b.get("branch_density_per_kpx", zone_b.get("features", {}).get(
        "branch_density_per_kpx", 0)))
    result["uv_branch_density_a"] = bd_a
    result["uv_branch_density_b"] = bd_b
    result["uv_branch_density_delta"] = abs(bd_a - bd_b)

    # Junction count
    jn_a = float(zone_a.get("junctions", zone_a.get("features", {}).get("junctions", 0)))
    jn_b = float(zone_b.get("junctions", zone_b.get("features", {}).get("junctions", 0)))
    result["uv_junctions_a"] = jn_a
    result["uv_junctions_b"] = jn_b
    result["uv_junctions_delta"] = abs(jn_a - jn_b)

    # Mean ridge strength
    rs_a = float(zone_a.get("mean_ridge_strength", zone_a.get("features", {}).get(
        "mean_ridge_strength", 0)))
    rs_b = float(zone_b.get("mean_ridge_strength", zone_b.get("features", {}).get(
        "mean_ridge_strength", 0)))
    result["uv_ridge_strength_a"] = rs_a
    result["uv_ridge_strength_b"] = rs_b
    result["uv_ridge_strength_delta"] = abs(rs_a - rs_b)

    # Weight (policy)
    wa = float(zone_a.get("weight", 0))
    wb = float(zone_b.get("weight", 0))
    result["uv_zone_weight"] = max(wa, wb)

    return result


def uv_geometry_pair(
    a: Any,
    b: Any,
    output_dir: Path,
    pair_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compare UV geometry metrics between two records.

    Returns:
        (row_dict, zone_rows) where row_dict contains pair-level summaries
        and zone_rows contains per-zone deltas.
    """
    dir_a = getattr(a, "record_dir", None)
    dir_b = getattr(b, "record_dir", None)

    if dir_a is None or dir_b is None:
        return {"uv_geometry_status": "missing_record_dir"}, []

    forensics_a = _load_uv_forensics(dir_a)
    forensics_b = _load_uv_forensics(dir_b)

    if forensics_a.get("status") == "missing" or forensics_b.get("status") == "missing":
        return {
            "uv_geometry_status": "unavailable",
            "uv_geometry_error_a": forensics_a.get("status"),
            "uv_geometry_error_b": forensics_b.get("status"),
        }, []

    zones_a = _extract_uv_zones(forensics_a)
    zones_b = _extract_uv_zones(forensics_b)

    if not zones_a or not zones_b:
        # Try loading wrinkle data from wrinkle_zones.json (alternative source)
        zones_a = _load_wrinkle_zones(dir_a)
        zones_b = _load_wrinkle_zones(dir_b)

    if not zones_a or not zones_b:
        return {
            "uv_geometry_status": "no_zone_data",
            "uv_zone_count_a": len(zones_a),
            "uv_zone_count_b": len(zones_b),
        }, []

    # Compare common zones
    common_zones = sorted(set(zones_a.keys()) & set(zones_b.keys()))
    zone_rows: list[dict[str, Any]] = []

    for zone_name in common_zones:
        za = zones_a[zone_name]
        zb = zones_b[zone_name]
        delta = _zone_delta(za, zb, zone_name)
        delta["pair_id"] = pair_id
        zone_rows.append(delta)

    # Pair-level summary
    if not zone_rows:
        return {
            "uv_geometry_status": "no_common_zones",
            "uv_zone_count_a": len(zones_a),
            "uv_zone_count_b": len(zones_b),
        }, []

    # Aggregate deltas
    ridge_deltas = [r["uv_ridge_density_delta"] for r in zone_rows]
    branch_deltas = [r["uv_branch_count_delta"] for r in zone_rows]
    length_deltas = [r["uv_total_length_delta"] for r in zone_rows]
    strength_deltas = [r["uv_ridge_strength_delta"] for r in zone_rows]

    row = {
        "uv_geometry_status": "measured",
        "uv_geometry_schema": UV_COMPARISON_SCHEMA,
        "uv_common_zone_count": len(common_zones),
        "uv_zone_count_a": len(zones_a),
        "uv_zone_count_b": len(zones_b),
        "uv_max_ridge_density_delta": float(max(ridge_deltas)),
        "uv_mean_ridge_density_delta": float(np.mean(ridge_deltas)),
        "uv_max_branch_count_delta": float(max(branch_deltas)),
        "uv_max_total_length_delta": float(max(length_deltas)),
        "uv_max_ridge_strength_delta": float(max(strength_deltas)),
        "uv_priority_zone_count": sum(1 for r in zone_rows if r.get("zone") in PRIORITY_UV_ZONES),
    }

    # Save detailed zone comparison
    uv_dir = output_dir / "uv_comparison"
    uv_dir.mkdir(exist_ok=True)
    safe_pid = pair_id.replace("/", "_")
    atomic_json(uv_dir / f"{safe_pid}.json", {
        "schema": UV_COMPARISON_SCHEMA,
        "pair_id": pair_id,
        "zones": zone_rows,
    })

    return row, zone_rows


def _load_wrinkle_zones(record_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Fallback: load wrinkle_zones.json from Stage 1 output."""
    p = Path(record_dir) / "wrinkle_zones.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        zones_data = data.get("zones", {})
        # Convert to standard format
        result: dict[str, dict[str, Any]] = {}
        for zone_name, zone_info in zones_data.items():
            result[zone_name] = zone_info.get("features", zone_info)
        return result
    except Exception:
        return {}
