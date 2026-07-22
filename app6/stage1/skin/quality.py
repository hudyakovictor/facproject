"""Quality maps + applicability (v5 evidence-path fixes).

Changes vs previous:
- projected_density no longer hard-clipped to 100 (was saturating to constant)
- optional percentile winsorization only for extreme outliers
- per-zone applicability helper for quality.json diagnostics
"""
from __future__ import annotations
import cv2
import numpy as np
from .contracts import Applicability, EvidenceState, ReasonCode
from ..status_logger import log_status, log_blocker, log_warning

FAMILIES = ('geometry','macro_texture','meso_texture','micro_texture','wrinkles','pigmentation','material_optics','local_feature_matching')

# Soft upper bound only for pathological spikes; high enough not to flatten normal faces.
DENSITY_P99_CAP_MULT = 50.0
DENSITY_ABS_CAP = 1.0e6

def _robust01(x, m):
    if not np.any(m):
        return np.zeros_like(x, dtype=np.float32)
    p90 = float(np.percentile(x[m], 90)) + 1e-6
    return np.clip(x / p90, 0, 1).astype(np.float32)

def _jpeg_block_energy(gray01: np.ndarray):
    g = (gray01*255).astype(np.float32)
    H,W = g.shape
    block = np.zeros_like(g, dtype=np.float32)
    for x in range(7, W-1, 8):
        block[:, x-1:x+2] = np.maximum(block[:, x-1:x+2], np.abs(g[:, x+1:x+2] - g[:, x:x+1]).mean(axis=1, keepdims=True) if x+2<=W else 0)
    for y in range(7, H-1, 8):
        block[y-1:y+2, :] = np.maximum(block[y-1:y+2, :], np.abs(g[y+1:y+2, :] - g[y:y+1, :]).mean(axis=0, keepdims=True) if y+2<=H else 0)
    block = cv2.GaussianBlur(block, (0,0), 1.0)
    return block

def _projected_scale_from_triangle_id(triangle_id: np.ndarray):
    t = triangle_id
    v = t>=0
    out = np.zeros(t.shape, np.float32)
    if np.any(v):
        ids, counts = np.unique(t[v], return_counts=True)
        q = np.zeros(int(ids.max())+1, np.float32)
        q[ids] = np.sqrt(counts.astype(np.float32))
        out[v] = q[t[v]]
    return out

def _edge_width_estimator(gray01: np.ndarray, valid: np.ndarray):
    if not np.any(valid):
        return np.array(0.0, dtype=np.float32)
    gx = cv2.Sobel(gray01, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray01, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    lap = cv2.Laplacian(gray01, cv2.CV_32F, ksize=3)
    width_map = mag / (np.abs(lap)+1e-6)
    return width_map

def _local_dynamic_range(gray01: np.ndarray, ksize=15):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (ksize, ksize))
    min_f = cv2.erode(gray01, kernel)
    max_f = cv2.dilate(gray01, kernel)
    dr = max_f - min_f
    return dr.astype(np.float32)

def _sanitize_density(scale: np.ndarray, domain: np.ndarray) -> tuple[np.ndarray, dict]:
    s = np.asarray(scale, np.float32).copy()
    d = np.asarray(domain, bool)
    s[~np.isfinite(s)] = 0.0
    s[s < 0] = 0.0
    meta = {
        'density_raw_min': float(s[d].min()) if np.any(d) else 0.0,
        'density_raw_max': float(s[d].max()) if np.any(d) else 0.0,
        'density_raw_median': float(np.median(s[d])) if np.any(d) else 0.0,
        'density_unique_raw': int(len(np.unique(np.round(s[d], 5)))) if np.any(d) else 0,
        'density_clip_mode': 'percentile_winsor_no_hard100',
    }
    if np.any(d) and meta['density_raw_max'] > 0:
        p99 = float(np.percentile(s[d], 99))
        cap = min(DENSITY_ABS_CAP, max(p99 * DENSITY_P99_CAP_MULT, p99 + 1.0))
        n_hi = int((s[d] > cap).sum())
        s = np.clip(s, 0, cap)
        meta['density_cap_used'] = float(cap)
        meta['density_pixels_winsorized'] = n_hi
        meta['density_unique_after'] = int(len(np.unique(np.round(s[d], 5))))
        meta['density_frac_near_cap'] = float((s[d] >= cap * 0.999).mean())
    else:
        meta['density_cap_used'] = 0.0
        meta['density_pixels_winsorized'] = 0
        meta['density_unique_after'] = 0
        meta['density_frac_near_cap'] = 0.0
    return s.astype(np.float32), meta

def quality_maps(bgr, domain, incidence, projection_confidence, triangle_id, projected_density_map=None):
    log_status("quality_maps", "complete")
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)/255.0
    d = np.asarray(domain, bool)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    ten = np.hypot(gx, gy)
    focus = _robust01(ten, d)
    lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
    med = cv2.medianBlur((g*255).astype(np.uint8), 3).astype(np.float32)/255.0
    hp = np.abs(g - med)
    noise_val = float(1.4826 * np.median(np.abs(hp[d] - np.median(hp[d])))) if np.any(d) else 0.08
    ns = np.full(g.shape, np.clip(1.0 - noise_val/0.12, 0, 1), np.float32)

    block = _jpeg_block_energy(g)
    bs = float(np.mean(block[d])) if np.any(d) else 0.0
    if np.any(d):
        p95_block = float(np.percentile(block[d], 95)) + 1e-6
        proc = np.clip(1.0 - block / p95_block * 0.5, 0, 1).astype(np.float32)
    else:
        proc = np.zeros_like(g, dtype=np.float32)

    halo = float(np.mean((np.abs(lap[d])>0.15) & (ten[d]>0.1))) if np.any(d) else 0.0
    local_var = cv2.GaussianBlur(g*g, (0,0), 2) - cv2.GaussianBlur(g, (0,0), 2)**2
    denoise = float(np.mean(local_var[d] < 1e-5)) if np.any(d) else 0.0
    hann = np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1])).astype(np.float32)
    F = np.abs(np.fft.rfft2((g - g.mean()) * hann))
    resize_periodicity = float(np.max(F[:,1:]) / (np.mean(F[:,1:]) + 1e-8)) if F.shape[1]>1 else 0.0

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    spec = (hsv[...,2] > 245) & (hsv[...,1] < 35) & d
    shadow = (g < 0.08) & d
    clipping = ((g < 0.015) | (g > 0.985)) & d
    exposure = np.clip(
        1.0 - np.maximum(np.abs(g - 0.5) - 0.25, 0.0) / 0.25,
        0.05, 1.0
    ).astype(np.float32)

    inc = np.asarray(incidence, np.float32)
    proj = np.asarray(projection_confidence, np.float32)

    
    # mesh_grid_fix: smooth conf inside domain so quality renders lose triangle grid
    _d = np.asarray(domain, bool)
    if np.any(_d):
        _ps = cv2.GaussianBlur(proj, (0, 0), 1.5)
        proj = np.where(_d, _ps, 0.0).astype(np.float32)
    if projected_density_map is not None:
        scale_raw = np.asarray(projected_density_map, np.float32)
    else:
        scale_raw = _projected_scale_from_triangle_id(triangle_id)
    scale, dens_meta = _sanitize_density(scale_raw, d)

    eff = (scale * focus * np.sqrt(np.clip(inc, 0, 1)) * proc * ns).astype(np.float32)
    # physical quality BEFORE pose prior
    w = (focus * exposure * proj * proc * ns * (~spec) * (~shadow) * d).astype(np.float32)

    
    # mesh_grid_fix: mild domain-normalized smooth of quality_weight (kills residual mesh faceting)
    if np.any(d):
        _wf = np.where(d, w, 0.0).astype(np.float32)
        _mf = d.astype(np.float32)
        _wb = cv2.GaussianBlur(_wf, (0, 0), 1.0)
        _mb = cv2.GaussianBlur(_mf, (0, 0), 1.0)
        _ws = np.zeros_like(w)
        _good = _mb > 1e-6
        _ws[_good] = _wb[_good] / _mb[_good]
        w = np.where(d, _ws, 0.0).astype(np.float32)
    edge_width = _edge_width_estimator(g, d)
    local_dr = _local_dynamic_range(g, ksize=15)
    large_blur = cv2.GaussianBlur(g, (0,0), 15)
    illum_gx = cv2.Sobel(large_blur, cv2.CV_32F, 1, 0, ksize=3)
    illum_gy = cv2.Sobel(large_blur, cv2.CV_32F, 0, 1, ksize=3)
    illum_grad = np.hypot(illum_gx, illum_gy).astype(np.float32)

    return {
        'focus_transfer': focus,
        'tenengrad': ten.astype(np.float32),
        'laplacian': lap.astype(np.float32),
        'edge_width_map': edge_width.astype(np.float32),
        'local_dynamic_range': local_dr,
        'illumination_gradient': illum_grad,
        'noise_survival': ns,
        'jpeg_block_map': block.astype(np.float32),
        'processing_survival': proc,
        'exposure_weight': exposure,
        'specular_mask': spec,
        'deep_shadow_mask': shadow,
        'clipping_mask': clipping,
        'incidence_weight': inc,
        'projection_confidence': proj,
        'projected_scale_px_sqrt': scale,
        'projected_density_map': scale,
        'effective_resolution': eff,
        'hair_probability_available': np.array(False),
        'external_occlusion_available': np.array(False),
        'quality_weight': w,
        'quality_weight_physical': w.copy(),
        'global_noise_level': np.array(noise_val, np.float32),
        'global_jpeg_block_score': np.array(bs, np.float32),
        'global_sharpening_halo_score': np.array(halo, np.float32),
        'global_denoise_flat_fraction': np.array(denoise, np.float32),
        'global_resize_periodicity_score': np.array(resize_periodicity, np.float32),
        'global_edge_width_median': np.array(float(np.median(edge_width[d])) if np.any(d) else 0.0, np.float32),
        'global_local_dr_median': np.array(float(np.median(local_dr[d])) if np.any(d) else 0.0, np.float32),
        'density_meta_json': np.array(str(dens_meta)),
    }

def applicability(m, d, W, H):
    log_status("applicability", "complete")
    n = int(np.asarray(d).sum())
    def _med(key):
        arr = m.get(key)
        if arr is None:
            return 0.0
        try:
            vals = arr[d] if getattr(arr, 'shape', None) == d.shape else arr
            if isinstance(vals, np.ndarray) and vals.size>0:
                return float(np.median(vals)) if np.any(d) else 0.0
            return float(vals)
        except Exception:
            return float(np.asarray(arr).mean()) if np.asarray(arr).size else 0.0

    base = {
        'pixels': n,
        'coverage': float(n / max(d.size,1)),
        'focus': _med('focus_transfer'),
        'laplacian_median': _med('laplacian'),
        'edge_width_median': float(m.get('global_edge_width_median', 0)) if 'global_edge_width_median' in m else 0.0,
        'local_dr_median': float(m.get('global_local_dr_median', 0)) if 'global_local_dr_median' in m else 0.0,
        'projection': float(np.mean(m['projection_confidence'][d])) if n else 0.0,
        'incidence': float(np.mean(m['incidence_weight'][d])) if n else 0.0,
        'specular_fraction': float(np.mean(m['specular_mask'][d])) if n else 0.0,
        'clipping_fraction': float(np.mean(m['clipping_mask'][d])) if 'clipping_mask' in m and n else 0.0,
        'effective_resolution_median': float(np.median(m['effective_resolution'][d])) if n else 0.0,
        'noise_level': float(m.get('global_noise_level', 0)),
        'jpeg_block_score': float(m.get('global_jpeg_block_score', 0)),
        'sharpening_halo_score': float(m.get('global_sharpening_halo_score', 0)),
        'denoise_flat_fraction': float(m.get('global_denoise_flat_fraction', 0)),
        'resize_periodicity_score': float(m.get('global_resize_periodicity_score', 0)),
        'effective_support': float(m['quality_weight'][d].sum()) if n else 0.0,
    }
    out = {}
    for fam in FAMILIES:
        reasons = []
        state = EvidenceState.USABLE
        if n < 100:
            state = EvidenceState.NOT_OBSERVED
            reasons.append(ReasonCode.SELF_OCCLUDED.value)
        elif base['projection'] < 0.2:
            state = EvidenceState.NOT_MEASURABLE
            reasons.append(ReasonCode.PROJECTION_UNSTABLE.value)
        elif base['incidence'] < 0.25:
            if state == EvidenceState.USABLE:
                state = EvidenceState.COARSE_ONLY
            reasons.append(ReasonCode.HIGH_INCIDENCE_ANGLE.value)
        if base['focus'] < 0.12:
            state = EvidenceState.NOT_MEASURABLE
            reasons.append(ReasonCode.EXCESSIVE_BLUR.value)
        if base['edge_width_median'] > 4.0:
            if state == EvidenceState.USABLE:
                state = EvidenceState.COARSE_ONLY
            reasons.append(ReasonCode.EXCESSIVE_BLUR.value)
        if base['noise_level'] > 0.08:
            reasons.append(ReasonCode.EXCESSIVE_NOISE.value)
            if state == EvidenceState.USABLE:
                state = EvidenceState.COARSE_ONLY
        if base['jpeg_block_score'] > 0.15:
            reasons.append(ReasonCode.JPEG_DAMAGE.value)
        if base['specular_fraction'] > 0.15:
            reasons.append(ReasonCode.SPECULAR_CONTAMINATION.value)
        if base.get('clipping_fraction',0) > 0.1:
            reasons.append(ReasonCode.DEEP_SHADOW.value)
        if fam in {'micro_texture','material_optics','local_feature_matching'} and (base['effective_resolution_median'] < 1.2 or min(W,H) < 700):
            state = EvidenceState.NOT_MEASURABLE
            reasons.append(ReasonCode.LOW_EFFECTIVE_RESOLUTION.value)
        if fam in {'meso_texture','wrinkles'} and base['effective_resolution_median'] < 0.6:
            if state == EvidenceState.USABLE:
                state = EvidenceState.COARSE_ONLY
            reasons.append(ReasonCode.LOW_EFFECTIVE_RESOLUTION.value)
        out[fam] = Applicability(fam, state, base['effective_support'], tuple(dict.fromkeys(reasons)), base).to_dict()
    return out

def per_zone_applicability(A, domain, quality_weight, pose_weight=None, min_support=50.0, min_pixels=64):
    log_status("per_zone_applicability", "complete")
    """Per-zone geometry/support/evidence snapshot for diagnostics."""
    A = np.asarray(A)
    d = np.asarray(domain, bool)
    qw = np.asarray(quality_weight, np.float32)
    pw = np.asarray(pose_weight, np.float32) if pose_weight is not None else None
    rows = []
    for i in range(20):
        geom = d & (A == i)
        gpx = int(geom.sum())
        support = float(qw[geom].sum()) if gpx else 0.0
        qw_pos = float((qw[geom] > 1e-8).mean()) if gpx else 0.0
        prior = float(np.median(pw[geom])) if (pw is not None and gpx) else None
        if gpx <= 0:
            state = 'not_observed'
        elif support >= min_support and gpx >= min_pixels and qw_pos > 0.05:
            state = 'usable'
        elif support > 0:
            state = 'coarse_only' if support >= min_support * 0.25 else 'not_measurable'
        else:
            state = 'not_measurable'
        rows.append({
            'zone': f'A{i+1:02d}',
            'geometry_pixels': gpx,
            'geometry_frac_domain': float(gpx / max(int(d.sum()), 1)),
            'effective_support': support,
            'quality_positive_frac': qw_pos,
            'pose_prior_median': prior,
            'state': state,
            'geometry_without_evidence': bool(gpx >= min_pixels and support < min_support),
        })
    return rows
