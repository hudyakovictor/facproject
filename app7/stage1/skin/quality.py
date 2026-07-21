"""Quality maps + applicability — illumination-robust, density-capped."""

from __future__ import annotations

import cv2
import numpy as np

from .contracts import Applicability, EvidenceState, FAMILIES, ReasonCode

DENSITY_P99_CAP_MULT = 50.0
DENSITY_ABS_CAP = 1.0e6


def _robust01(x: np.ndarray, m: np.ndarray) -> np.ndarray:
    if not np.any(m):
        return np.zeros_like(x, dtype=np.float32)
    p90 = float(np.percentile(x[m], 90)) + 1e-6
    return np.clip(x / p90, 0, 1).astype(np.float32)


def _jpeg_block_energy(gray01: np.ndarray) -> np.ndarray:
    g = (gray01 * 255).astype(np.float32)
    H, W = g.shape
    block = np.zeros_like(g, dtype=np.float32)
    for x in range(7, W - 1, 8):
        block[:, x - 1:x + 2] = np.maximum(
            block[:, x - 1:x + 2],
            np.abs(g[:, x + 1:x + 2] - g[:, x:x + 1]).mean(axis=1, keepdims=True) if x + 2 <= W else 0)
    for y in range(7, H - 1, 8):
        block[y - 1:y + 2, :] = np.maximum(
            block[y - 1:y + 2, :],
            np.abs(g[y + 1:y + 2, :] - g[y:y + 1, :]).mean(axis=0, keepdims=True) if y + 2 <= H else 0)
    return cv2.GaussianBlur(block, (0, 0), 1.0)


def _sanitize_density(scale: np.ndarray, domain: np.ndarray) -> tuple[np.ndarray, dict]:
    s = np.asarray(scale, np.float32).copy()
    d = np.asarray(domain, bool)
    s[~np.isfinite(s)] = 0.0
    s[s < 0] = 0.0
    meta = {}
    if np.any(d):
        p99 = float(np.percentile(s[d], 99))
        cap = min(DENSITY_ABS_CAP, max(p99 * DENSITY_P99_CAP_MULT, p99 + 1.0))
        s = np.clip(s, 0, cap)
        meta = {"density_cap_used": float(cap), "density_pixels_winsorized": int((s[d] >= cap * 0.999).sum())}
    return s.astype(np.float32), meta


def quality_maps(bgr, domain, incidence, projection_confidence, triangle_id, projected_density_map=None):
    """Compute per-pixel quality weight and effective resolution maps."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    d = np.asarray(domain, bool)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    ten = np.hypot(gx, gy)
    focus = _robust01(ten, d)

    med = cv2.medianBlur((g * 255).astype(np.uint8), 3).astype(np.float32) / 255.0
    hp = np.abs(g - med)
    noise_val = float(1.4826 * np.median(np.abs(hp[d] - np.median(hp[d])))) if np.any(d) else 0.08
    ns = np.full(g.shape, np.clip(1.0 - noise_val / 0.12, 0, 1), np.float32)

    block = _jpeg_block_energy(g)
    if np.any(d):
        p95_block = float(np.percentile(block[d], 95)) + 1e-6
        proc = np.clip(1.0 - block / p95_block * 0.5, 0, 1).astype(np.float32)
    else:
        proc = np.zeros_like(g, dtype=np.float32)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    spec = (hsv[..., 2] > 245) & (hsv[..., 1] < 35) & d
    shadow = (g < 0.08) & d
    exposure = np.clip(1.0 - np.maximum(np.abs(g - 0.5) - 0.25, 0.0) / 0.25, 0.05, 1.0).astype(np.float32)

    inc = np.asarray(incidence, np.float32)
    proj = np.asarray(projection_confidence, np.float32)

    # Smooth confidence to remove mesh grid
    if np.any(d):
        ps = cv2.GaussianBlur(proj, (0, 0), 1.5)
        proj = np.where(d, ps, 0.0).astype(np.float32)

    scale_raw = np.asarray(projected_density_map, np.float32) if projected_density_map is not None else np.zeros_like(g, np.float32)
    scale, dens_meta = _sanitize_density(scale_raw, d)

    eff = (scale * focus * np.sqrt(np.clip(inc, 0, 1)) * proc * ns).astype(np.float32)
    w = (focus * exposure * proj * proc * ns * (~spec) * (~shadow) * d).astype(np.float32)

    # Mild smooth of quality_weight to remove residual mesh faceting
    if np.any(d):
        wf = np.where(d, w, 0.0).astype(np.float32)
        mf = d.astype(np.float32)
        wb = cv2.GaussianBlur(wf, (0, 0), 1.0)
        mb = cv2.GaussianBlur(mf, (0, 0), 1.0)
        ws = np.zeros_like(w)
        good = mb > 1e-6
        ws[good] = wb[good] / mb[good]
        w = np.where(d, ws, 0.0).astype(np.float32)

    return {
        "focus_transfer": focus,
        "noise_survival": ns,
        "processing_survival": proc,
        "exposure_weight": exposure,
        "specular_mask": spec,
        "deep_shadow_mask": shadow,
        "incidence_weight": inc,
        "projection_confidence": proj,
        "projected_density_map": scale,
        "effective_resolution": eff,
        "quality_weight": w,
        "quality_weight_physical": w.copy(),
        "global_noise_level": np.array(noise_val, np.float32),
        "global_jpeg_block_score": np.array(float(np.mean(block[d])) if np.any(d) else 0.0, np.float32),
        "density_meta": dens_meta,
    }


def applicability(m, d, W, H):
    """Compute per-family applicability from quality maps."""
    n = int(np.asarray(d).sum())
    if n == 0:
        return {fam: Applicability(fam, EvidenceState.NOT_OBSERVED, 0.0, (), {}).to_dict() for fam in FAMILIES}

    def _med(key):
        arr = m.get(key)
        if arr is None:
            return 0.0
        try:
            vals = arr[d]
            return float(np.median(vals)) if vals.size > 0 else 0.0
        except Exception:
            return 0.0

    base = {
        "pixels": n,
        "focus": _med("focus_transfer"),
        "projection": float(np.mean(m["projection_confidence"][d])),
        "incidence": float(np.mean(m["incidence_weight"][d])),
        "specular_fraction": float(np.mean(m["specular_mask"][d])),
        "effective_resolution_median": float(np.median(m["effective_resolution"][d])),
        "noise_level": float(m.get("global_noise_level", 0)),
        "effective_support": float(m["quality_weight"][d].sum()),
    }

    out = {}
    for fam in FAMILIES:
        reasons = []
        state = EvidenceState.USABLE
        if n < 100:
            state = EvidenceState.NOT_OBSERVED
            reasons.append(ReasonCode.SELF_OCCLUDED.value)
        elif base["projection"] < 0.2:
            state = EvidenceState.NOT_MEASURABLE
            reasons.append(ReasonCode.PROJECTION_UNSTABLE.value)
        elif base["incidence"] < 0.25:
            if state == EvidenceState.USABLE:
                state = EvidenceState.COARSE_ONLY
            reasons.append(ReasonCode.HIGH_INCIDENCE_ANGLE.value)
        if base["focus"] < 0.12:
            state = EvidenceState.NOT_MEASURABLE
            reasons.append(ReasonCode.EXCESSIVE_BLUR.value)
        if base["noise_level"] > 0.08:
            reasons.append(ReasonCode.EXCESSIVE_NOISE.value)
            if state == EvidenceState.USABLE:
                state = EvidenceState.COARSE_ONLY
        if fam in {"micro_texture", "material_optics", "local_feature_matching"} and (base["effective_resolution_median"] < 1.2 or min(W, H) < 700):
            state = EvidenceState.NOT_MEASURABLE
            reasons.append(ReasonCode.LOW_EFFECTIVE_RESOLUTION.value)
        if fam in {"meso_texture", "wrinkles"} and base["effective_resolution_median"] < 0.6:
            if state == EvidenceState.USABLE:
                state = EvidenceState.COARSE_ONLY
            reasons.append(ReasonCode.LOW_EFFECTIVE_RESOLUTION.value)
        out[fam] = Applicability(fam, state, base["effective_support"], tuple(dict.fromkeys(reasons)), base).to_dict()
    return out


def per_zone_applicability(A, domain, quality_weight, pose_weight=None, min_support=50.0, min_pixels=64):
    """Per-zone geometry/support/evidence snapshot."""
    A = np.asarray(A)
    d = np.asarray(domain, bool)
    qw = np.asarray(quality_weight, np.float32)
    pw = np.asarray(pose_weight, np.float32) if pose_weight is not None else None
    rows = []
    for i in range(20):
        geom = d & (A == i)
        gpx = int(geom.sum())
        support = float(qw[geom].sum()) if gpx else 0.0
        if gpx <= 0:
            state = "not_observed"
        elif support >= min_support and gpx >= min_pixels:
            state = "usable"
        elif support > 0:
            state = "coarse_only" if support >= min_support * 0.25 else "not_measurable"
        else:
            state = "not_measurable"
        rows.append({
            "zone": f"A{i + 1:02d}",
            "geometry_pixels": gpx,
            "effective_support": support,
            "state": state,
            "geometry_without_evidence": bool(gpx >= min_pixels and support < min_support),
        })
    return rows
