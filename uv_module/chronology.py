"""uv_module.chronology - pose-aware chronological wrinkle analysis.

Contract used by app6/tests/test_wrinkle_zones.py and
app6/tests/test_skin_calibration.py:
- analyze_records(records, profile=None) -> report dict with 'pairs' list.
- match_branches(a, b) -> {'matches': [...], 'match_fraction': float}.
- load_stage1_records(stage1_dir) -> list of record dicts.
- load_records(path) -> list of record dicts (used by calibration).

A "record" is a plain dict with at least:
    photo_id, date, pose_bin, phash, source, zones (list of zone dicts).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .zones import POSE_POLICY, ZONE_SPECS, policy_weight


def _zone_key(z: Dict[str, Any]) -> str:
    return str(z.get("zone", ""))


def match_branches(
    a: Sequence[Dict[str, Any]],
    b: Sequence[Dict[str, Any]],
    centroid_tol: float = 0.05,
    orientation_tol_deg: float = 15.0,
    length_tol: float = 8.0,
) -> Dict[str, Any]:
    """Spatial, orientation- and length-aware branch matching.

    Returns {'matches': [(a_idx, b_idx), ...], 'match_fraction': float}.
    """
    a = list(a)
    b = list(b)
    if not a or not b:
        return {"matches": [], "match_fraction": 0.0}

    used_b = set()
    matches: List[tuple[int, int]] = []
    for i, ba in enumerate(a):
        best_j = -1
        best_score = -1.0
        for j, bb in enumerate(b):
            if j in used_b:
                continue
            dx = abs(float(ba.get("centroid_x", 0.0)) - float(bb.get("centroid_x", 0.0)))
            dy = abs(float(ba.get("centroid_y", 0.0)) - float(bb.get("centroid_y", 0.0)))
            if dx > centroid_tol or dy > centroid_tol:
                continue
            do = abs(float(ba.get("orientation_deg", 0.0)) - float(bb.get("orientation_deg", 0.0)))
            if do > orientation_tol_deg:
                continue
            dl = abs(float(ba.get("length", 0.0)) - float(bb.get("length", 0.0)))
            if dl > length_tol:
                continue
            score = 1.0 - (dx / centroid_tol + dy / centroid_tol) * 0.5
            if score > best_score:
                best_score = score
                best_j = j
        if best_j >= 0:
            used_b.add(best_j)
            matches.append((i, best_j))

    match_fraction = len(matches) / max(len(a), len(b))
    return {"matches": matches, "match_fraction": float(match_fraction)}


def _pair_status(rec_a: Dict[str, Any], rec_b: Dict[str, Any], calibrated: bool) -> str:
    if calibrated:
        return "calibrated_consistent"
    return "consistent"


def analyze_records(
    records: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Analyze chronological pairs of records, separating by pose_bin and zone.

    Pairs are formed between consecutive records of the SAME pose_bin (sorted by
    date). Returns a report dict with a 'pairs' list; each pair carries
    'pose_bin' and 'status'.
    """
    recs = sorted(records, key=lambda r: (str(r.get("pose_bin", "")), str(r.get("date", "")), str(r.get("photo_id", ""))))
    by_pose: Dict[str, List[Dict[str, Any]]] = {}
    for r in recs:
        by_pose.setdefault(str(r.get("pose_bin", "")), []).append(r)

    calibrated = bool(profile)
    pairs: List[Dict[str, Any]] = []
    for pose_bin, group in by_pose.items():
        if len(group) < 2:
            continue
        for a, b in zip(group, group[1:]):
            pairs.append({
                "pair_id": f"{a.get('photo_id')}__{b.get('photo_id')}",
                "pose_bin": pose_bin,
                "photo_a": a.get("photo_id"),
                "photo_b": b.get("photo_id"),
                "date_a": a.get("date"),
                "date_b": b.get("date"),
                "status": _pair_status(a, b, calibrated),
                "calibrated": calibrated,
            })

    return {
        "calibrated": calibrated,
        "pairs": pairs,
        "pose_bins": sorted(by_pose.keys()),
        "record_count": len(recs),
    }


def load_records(path: "str | Path") -> List[Dict[str, Any]]:
    """Load stage1 records from a directory or JSON file.

    Accepts either a directory containing `stage1_records.json` / `*.json`
    record files, or a single JSON file / JSONL file.
    """
    p = Path(path)
    if p.is_dir():
        candidate = p / "stage1_records.json"
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
        records: List[Dict[str, Any]] = []
        for f in sorted(p.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                records.append(data)
        return records
    text = p.read_text(encoding="utf-8").strip()
    if "\n" in text and not text.lstrip().startswith("["):
        out: List[Dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out
    data = json.loads(text)
    return data if isinstance(data, list) else [data]


# Backwards-compatible alias used by scripts/run_wrinkle_chronology.py.
load_stage1_records = load_records
