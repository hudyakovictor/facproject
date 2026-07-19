from __future__ import annotations
import json
from pathlib import Path
import cv2
import numpy as np


def _distance_metrics(a: np.ndarray, b: np.ndarray, support: np.ndarray) -> dict:
    aa = np.asarray(a, bool) & support
    bb = np.asarray(b, bool) & support
    if int(support.sum()) < 250:
        return {"status": "NOT_COMPARABLE", "reason": "insufficient common support", "common_support_pixels": int(support.sum())}
    if not aa.any() or not bb.any():
        return {"status": "INCONCLUSIVE", "reason": "empty skeleton in common support", "common_support_pixels": int(support.sum()), "a_pixels": int(aa.sum()), "b_pixels": int(bb.sum())}
    da = cv2.distanceTransform((~aa).astype(np.uint8), cv2.DIST_L2, 5)
    db = cv2.distanceTransform((~bb).astype(np.uint8), cv2.DIST_L2, 5)
    b_to_a = da[bb]
    a_to_b = db[aa]
    med = float((np.median(b_to_a) + np.median(a_to_b)) / 2.0)
    p90 = float((np.percentile(b_to_a, 90) + np.percentile(a_to_b, 90)) / 2.0)
    # UV-pixel thresholds are deliberately conservative and labelled visual.
    if med <= 8 and p90 <= 28:
        status = "CANDIDATE_CONSISTENT"
    elif med <= 20 and p90 <= 60:
        status = "WEAKLY_COMPATIBLE"
    else:
        status = "INCONCLUSIVE_OR_DIFFERENT"
    return {
        "status": status,
        "median_symmetric_uv_distance_px": med,
        "p90_symmetric_uv_distance_px": p90,
        "a_pixels": int(aa.sum()),
        "b_pixels": int(bb.sum()),
        "common_support_pixels": int(support.sum()),
    }


def compare_pair(a_dir: str | Path, b_dir: str | Path, out_dir: str | Path, min_confidence: float = 0.40) -> dict:
    a_dir, b_dir, out = Path(a_dir), Path(b_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    a = np.load(a_dir / "surface_evidence.npz", allow_pickle=False)
    b = np.load(b_dir / "surface_evidence.npz", allow_pickle=False)
    names = [str(x) for x in a["patch_names"]]
    common = (
        a["uv_observed"].astype(bool)
        & b["uv_observed"].astype(bool)
        & (a["uv_confidence"] >= float(min_confidence))
        & (b["uv_confidence"] >= float(min_confidence))
    )
    aa = a["uv_skeleton"].astype(bool)
    bb = b["uv_skeleton"].astype(bool)
    patches: dict[str, dict] = {}
    comparable = 0
    consistent_like = 0
    for i, name in enumerate(names):
        support = common & a["patch_masks"][i].astype(bool) & b["patch_masks"][i].astype(bool)
        m = _distance_metrics(aa, bb, support)
        patches[name] = m
        if m["status"] not in {"NOT_COMPARABLE", "INCONCLUSIVE"}:
            comparable += 1
        if m["status"] in {"CANDIDATE_CONSISTENT", "WEAKLY_COMPATIBLE"}:
            consistent_like += 1
    if comparable == 0:
        pair_status = "NOT_COMPARABLE"
    elif consistent_like >= max(2, comparable // 2):
        pair_status = "SURFACE_EVIDENCE_COMPATIBLE"
    else:
        pair_status = "INCONCLUSIVE"
    canvas = np.zeros((*common.shape, 3), np.uint8)
    canvas[common] = (45, 45, 45)
    canvas[aa & common] = (0, 0, 255)
    canvas[bb & common] = (255, 255, 0)
    canvas[aa & bb & common] = (255, 255, 255)
    cv2.imwrite(str(out / "uv_wrinkle_comparison.png"), canvas)
    report = {
        "schema": "surface-identity-consistency-lab-1",
        "a": a_dir.name,
        "b": b_dir.name,
        "pair_status": pair_status,
        "comparable_patch_count": comparable,
        "compatible_patch_count": consistent_like,
        "important_limitations": [
            "This is consistency evidence, not proof of identity.",
            "Current pair distances are UV visualization metrics; final forensic distances should use mesh-geodesic units.",
            "Expression, lighting, blur and low resolution can dominate wrinkle appearance.",
        ],
        "patches": patches,
    }
    (out / "identity_consistency.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def compare_all(record_output_dirs: list[Path], out_root: str | Path) -> list[dict]:
    out_root = Path(out_root)
    reports = []
    for i in range(len(record_output_dirs)):
        for j in range(i + 1, len(record_output_dirs)):
            a, b = record_output_dirs[i], record_output_dirs[j]
            reports.append(compare_pair(a, b, out_root / f"{a.name}__{b.name}"))
    summary = {
        "schema": "surface-identity-consistency-summary-lab-1",
        "pair_count": len(reports),
        "pairs": [{"a": r["a"], "b": r["b"], "pair_status": r["pair_status"], "comparable_patch_count": r["comparable_patch_count"], "compatible_patch_count": r["compatible_patch_count"]} for r in reports],
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "identity_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return reports
