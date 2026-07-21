#!/usr/bin/env python3
"""verify_same_person.py — Verify Stage 1 data: same person or different?

GEOMETRY: aligned landmarks + geodesic distances + alpha_id + mesh
SKIN:     atlas-localized features (same structure at same location)

Compares ONLY within each pose bin. No quality comparison.
Purpose: validate that Stage 1 data is sufficient before writing Stage 2.

Usage:
    python app7/verify_same_person.py --output ./test_output
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


# ═══════════════════════════════════════════════════════════════════════════
# Zone definitions
# ═══════════════════════════════════════════════════════════════════════════

ZONE_STABILITY = (
    "bone",   # A01 forehead_upper
    "bone",   # A02 forehead_lower
    "bone",   # A03 glabella
    "bone",   # A04 nose_bridge
    "mixed",  # A05 nose_tip
    "skin",   # A06 nose_ala_left
    "skin",   # A07 nose_ala_right
    "bone",   # A08 orbit_left
    "bone",   # A09 orbit_right
    "bone",   # A10 zygomatic_left
    "bone",   # A11 zygomatic_right
    "skin",   # A12 cheek_left
    "skin",   # A13 cheek_right
    "skin",   # A14 mouth_upper
    "skin",   # A15 mouth_lower
    "bone",   # A16 chin
    "bone",   # A17 jaw_left
    "bone",   # A18 jaw_right
    "bone",   # A19 temple_left
    "bone",   # A20 temple_right
)

BONE_IDS = sorted(i for i, s in enumerate(ZONE_STABILITY) if s == "bone")
SKIN_IDS = sorted(i for i, s in enumerate(ZONE_STABILITY) if s == "skin")

FEATURE_NAMES = (
    "lbp_entropy", "lbp_uniform_fraction",
    "glcm_contrast", "glcm_homogeneity", "glcm_energy",
    "gabor_energy", "gabor_anisotropy",
    "spectral_entropy", "spectral_high_ratio",
    "structure_coherence", "log_blob_density", "local_mad",
    "lab_L_median", "lab_a_median", "lab_b_median", "lab_a_mad",
    "chroma_mad", "color_entropy",
    "glcm_dissimilarity", "glcm_correlation", "glcm_asm",
    "spectral_low_ratio", "spectral_mid_ratio", "spectral_slope",
)

FEATURE_GROUPS = {
    "microtexture":  [0, 1, 10, 11],
    "mesotexture":   [2, 3, 4, 18, 19, 20],
    "orientation":   [5, 6, 9],
    "spectral":      [7, 8, 21, 22, 23],
    "pigmentation":  [12, 13, 14, 15, 16, 17],
}

EXPRESSION_EXCLUDED_ZONES = {5, 6, 13, 14, 11, 12}  # nose ala, mouth, cheeks


# ═══════════════════════════════════════════════════════════════════════════
# Data loading
# ═══════════════════════════════════════════════════════════════════════════

def _load_npz(path):
    if not Path(path).is_file():
        return None
    return dict(np.load(path, allow_pickle=False))

def _load_json(path):
    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# GEOMETRY comparison
# ═══════════════════════════════════════════════════════════════════════════

def compare_geometry(pdir_a: Path, pdir_b: Path) -> dict:
    """Compare geometry: landmarks → geodesic → alpha → mesh."""

    rec_a = _load_npz(pdir_a / "reconstruction.npz")
    rec_b = _load_npz(pdir_b / "reconstruction.npz")
    if rec_a is None or rec_b is None:
        return {"status": "no_reconstruction"}

    result = {}

    # ── 1. Aligned landmark comparison (per-zone) ──
    ldm_result = _compare_landmarks(rec_a, rec_b, pdir_a, pdir_b)
    result["landmarks"] = ldm_result

    # ── 2. Geodesic distance matrix comparison ──
    geo_result = _compare_geodesic(pdir_a, pdir_b, rec_a, rec_b)
    result["geodesic"] = geo_result

    # ── 3. Alpha_id comparison ──
    alpha_a = rec_a.get("alpha_id")
    alpha_b = rec_b.get("alpha_id")
    if alpha_a is not None and alpha_b is not None:
        a = np.asarray(alpha_a, np.float64).ravel()
        b = np.asarray(alpha_b, np.float64).ravel()
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        cos = float(np.dot(a, b) / (na * nb)) if na > 1e-9 and nb > 1e-9 else 0.0
        l2 = float(np.linalg.norm(a - b))
        # Per-component analysis: which identity dimensions differ most
        diff = np.abs(a - b)
        top_dims = np.argsort(diff)[-5:][::-1]
        result["alpha"] = {
            "cosine_similarity": cos,
            "l2_distance": l2,
            "top_different_dims": [int(d) for d in top_dims],
            "top_different_values": [float(diff[d]) for d in top_dims],
        }
    else:
        result["alpha"] = None

    # ── 4. Mesh comparison (vertices_identity_only) ──
    mesh_result = _compare_mesh(rec_a, rec_b, pdir_a)
    result["mesh"] = mesh_result

    # ── 5. Expression compatibility ──
    expr_a = _load_json(pdir_a / "expression.json")
    expr_b = _load_json(pdir_b / "expression.json")
    result["expression"] = {
        "a": expr_a.get("label", "?") if expr_a else "?",
        "b": expr_b.get("label", "?") if expr_b else "?",
    }

    return result


def _compare_landmarks(rec_a, rec_b, pdir_a, pdir_b) -> dict:
    """Compare aligned landmarks with zone-based weighting.

    Key: bone landmarks are weighted 1.0, skin 0.4, expression-affected 0.1.
    """
    ldm_a = rec_a.get("ldm106_bin_canonical")
    ldm_b = rec_b.get("ldm106_bin_canonical")
    if ldm_a is None or ldm_b is None:
        return {"status": "no_aligned_landmarks"}

    la = np.asarray(ldm_a, np.float64)
    lb = np.asarray(ldm_b, np.float64)
    if la.ndim == 1:
        la = la.reshape(-1, 3)
        lb = lb.reshape(-1, 3)
    la = la[:, :3]
    lb = lb[:, :3]

    # Procrustes alignment (both already canonical-yaw aligned, but refine)
    la, lb = _procrustes(la, lb)

    dist = np.linalg.norm(la - lb, axis=1)
    n = len(dist)

    # Load zone mapping
    zones = _load_json(pdir_a / "ldm106_zones.json")
    expr = _load_json(pdir_a / "expression.json")
    expr_label = expr.get("label", "neutral") if expr else "neutral"

    # Compute weights
    if zones and "landmarks" in zones:
        weights = np.ones(n, np.float64)
        for lz in zones["landmarks"]:
            li = lz["landmark_id"]
            if li >= n:
                continue
            if lz["stability"] == "bone":
                weights[li] = 1.0
            elif lz["stability"] == "mixed":
                weights[li] = 0.7
            else:
                weights[li] = 0.4
            if expr_label != "neutral" and lz.get("zone_id", -1) in EXPRESSION_EXCLUDED_ZONES:
                weights[li] *= 0.15
    else:
        weights = np.ones(n, np.float64)

    # Weighted statistics
    w_sum = weights.sum()
    weighted_mean = float(np.sum(dist * weights) / w_sum) if w_sum > 0 else float("nan")
    weighted_rms = float(np.sqrt(np.sum((dist ** 2) * weights) / w_sum)) if w_sum > 0 else float("nan")

    # Per-zone breakdown
    bone_dist, skin_dist = [], []
    per_zone = {}
    if zones and "landmarks" in zones:
        for zi in range(20):
            z_ldm = [lz["landmark_id"] for lz in zones["landmarks"]
                      if lz.get("zone_id") == zi and lz["landmark_id"] < n]
            if z_ldm:
                z_dist = dist[z_ldm]
                z_key = f"A{zi + 1:02d}"
                z_stab = ZONE_STABILITY[zi] if zi < 20 else "unknown"
                per_zone[z_key] = {
                    "mean": float(np.mean(z_dist)),
                    "rms": float(np.sqrt(np.mean(z_dist ** 2))),
                    "max": float(np.max(z_dist)),
                    "n": len(z_ldm),
                    "stability": z_stab,
                }
                if z_stab == "bone":
                    bone_dist.extend(z_dist.tolist())
                elif z_stab == "skin":
                    skin_dist.extend(z_dist.tolist())

    result = {
        "status": "ok",
        "n_landmarks": n,
        "weighted_mean": weighted_mean,
        "weighted_rms": weighted_rms,
        "unweighted_mean": float(np.mean(dist)),
        "unweighted_rms": float(np.sqrt(np.mean(dist ** 2))),
        "p95": float(np.percentile(dist, 95)),
        "max": float(np.max(dist)),
        "bone_mean": float(np.mean(bone_dist)) if bone_dist else None,
        "bone_rms": float(np.sqrt(np.mean(np.array(bone_dist) ** 2))) if bone_dist else None,
        "skin_mean": float(np.mean(skin_dist)) if skin_dist else None,
        "skin_rms": float(np.sqrt(np.mean(np.array(skin_dist) ** 2))) if skin_dist else None,
        "per_zone": per_zone,
        "expression": expr_label,
    }

    # Identify WHICH landmarks differ most (for "what exactly differs")
    top_idx = np.argsort(dist)[-10:][::-1]
    result["most_different_landmarks"] = [
        {"landmark_id": int(i), "distance": float(dist[i]),
         "zone": _landmark_zone_name(zones, int(i)),
         "weight": float(weights[i])}
        for i in top_idx
    ]

    return result


def _landmark_zone_name(zones, ldm_id):
    if not zones or "landmarks" not in zones:
        return "unknown"
    for lz in zones["landmarks"]:
        if lz["landmark_id"] == ldm_id:
            return lz.get("zone_name", "unknown")
    return "unknown"


def _compare_geodesic(pdir_a, pdir_b, rec_a, rec_b) -> dict:
    """Compare geodesic distance matrices between landmarks.

    Geodesic distances are the gold standard for bone structure comparison:
    they measure shortest path ALONG the mesh surface, not through 3D space.
    This makes them approximately pose-invariant.
    """
    geo_a = _load_npz(pdir_a / "geodesic_ldm106.npz")
    geo_b = _load_npz(pdir_b / "geodesic_ldm106.npz")

    if geo_a is None or geo_b is None:
        return {"status": "no_geodesic_data"}

    gm_a = geo_a.get("geodesic_matrix")
    gm_b = geo_b.get("geodesic_matrix")
    if gm_a is None or gm_b is None:
        return {"status": "no_geodesic_matrix"}

    gm_a = np.asarray(gm_a, np.float64)
    gm_b = np.asarray(gm_b, np.float64)

    if gm_a.shape != gm_b.shape:
        return {"status": "shape_mismatch", "a": list(gm_a.shape), "b": list(gm_b.shape)}

    n = gm_a.shape[0]
    upper = np.triu_indices(n, k=1)
    va = gm_a[upper]
    vb = gm_b[upper]

    # Relative difference: robust metric for identity
    denom = np.abs(va) + np.abs(vb) + 1e-9
    rel_diff = np.abs(va - vb) / denom

    # Correlation (should be ~1.0 for same person)
    corr = float(np.corrcoef(va, vb)[0, 1]) if len(va) > 2 else None

    # Per-zone geodesic comparison (bone zone landmarks)
    zones = _load_json(pdir_a / "ldm106_zones.json")
    bone_geo, skin_geo = [], []
    if zones and "landmarks" in zones:
        bone_ids = [lz["landmark_id"] for lz in zones["landmarks"]
                    if lz.get("stability") == "bone" and lz["landmark_id"] < n]
        skin_ids = [lz["landmark_id"] for lz in zones["landmarks"]
                    if lz.get("stability") == "skin" and lz["landmark_id"] < n]

        if bone_ids:
            ba = gm_a[np.ix_(bone_ids, bone_ids)]
            bb = gm_b[np.ix_(bone_ids, bone_ids)]
            bu = np.triu_indices(len(bone_ids), k=1)
            bva, bvb = ba[bu], bb[bu]
            bdenom = np.abs(bva) + np.abs(bvb) + 1e-9
            bone_geo = (np.abs(bva - bvb) / bdenom).tolist()

        if skin_ids:
            sa = gm_a[np.ix_(skin_ids, skin_ids)]
            sb = gm_b[np.ix_(skin_ids, skin_ids)]
            su = np.triu_indices(len(skin_ids), k=1)
            sva, svb = sa[su], sb[su]
            sdenom = np.abs(sva) + np.abs(svb) + 1e-9
            skin_geo = (np.abs(sva - svb) / sdenom).tolist()

    return {
        "status": "ok",
        "n_landmarks": n,
        "full_mean_rel_diff": float(np.mean(rel_diff)),
        "full_corr": corr,
        "bone_mean_rel_diff": float(np.mean(bone_geo)) if bone_geo else None,
        "bone_corr": float(np.corrcoef(
            np.array(bone_geo), np.array(bone_geo))[0, 1]) if len(bone_geo) > 2 else None,
        "skin_mean_rel_diff": float(np.mean(skin_geo)) if skin_geo else None,
    }


def _compare_mesh(rec_a, rec_b, pdir_a) -> dict:
    """Compare vertex-level mesh with zone breakdown."""
    mesh_a = rec_a.get("vertices_identity_only")
    mesh_b = rec_b.get("vertices_identity_only")
    if mesh_a is None:
        mesh_a = rec_a.get("vertices_object_normalized")
    if mesh_b is None:
        mesh_b = rec_b.get("vertices_object_normalized")
    if mesh_a is None or mesh_b is None:
        return {"status": "no_mesh"}

    ma = np.asarray(mesh_a, np.float64)
    mb = np.asarray(mesh_b, np.float64)

    # Re-normalize and Procrustes align
    ma, mb = _normalize_pair(ma, mb)
    ma, mb = _procrustes(ma, mb)

    dist = np.linalg.norm(ma - mb, axis=1)

    # Visibility
    vis_a = _unpack_vis(rec_a.get("full_mesh_visible_packbits"), len(ma))
    vis_b = _unpack_vis(rec_b.get("full_mesh_visible_packbits"), len(mb))
    valid = vis_a & vis_b

    # Zone assignment
    zones_a = _vertex_zones_approx(ma)

    overall = _stats(dist, valid)
    bone_s, skin_s = {}, {}
    bone_d, skin_d = [], []
    per_zone = {}
    for zi in range(20):
        zmask = (zones_a == zi) & valid
        s = _stats(dist, zmask)
        s["stability"] = ZONE_STABILITY[zi]
        per_zone[f"A{zi + 1:02d}"] = s
        if ZONE_STABILITY[zi] == "bone" and zmask.any():
            bone_d.extend(dist[zmask].tolist())
        elif ZONE_STABILITY[zi] == "skin" and zmask.any():
            skin_d.extend(dist[zmask].tolist())

    return {
        "overall": overall,
        "bone_rms": float(np.sqrt(np.mean(np.array(bone_d) ** 2))) if bone_d else None,
        "skin_rms": float(np.sqrt(np.mean(np.array(skin_d) ** 2))) if skin_d else None,
        "per_zone": per_zone,
        "n_valid": int(valid.sum()),
    }


# ═══════════════════════════════════════════════════════════════════════════
# SKIN comparison — atlas-localized unique features
# ═══════════════════════════════════════════════════════════════════════════

def compare_skin(pdir_a: Path, pdir_b: Path) -> dict:
    """Compare skin: atlas-localized texture + spatial signatures + wrinkles."""

    result = {}

    # ── 1. Atlas-localized texture features ──
    tex_a = _load_npz(pdir_a / "skin" / "features" / "texture.npz")
    tex_b = _load_npz(pdir_b / "skin" / "features" / "texture.npz")
    if tex_a and tex_b:
        result["texture"] = _compare_texture(tex_a, tex_b)

    # ── 2. Spatial signatures (same structure at same location) ──
    sig_a = _load_json(pdir_a / "skin" / "spatial_signatures.json")
    sig_b = _load_json(pdir_b / "skin" / "spatial_signatures.json")
    if sig_a and sig_b:
        result["spatial"] = _compare_spatial_signatures(sig_a, sig_b)

    # ── 3. Wrinkle pattern comparison ──
    wr_a = _load_npz(pdir_a / "skin" / "wrinkles" / "classical.npz")
    wr_b = _load_npz(pdir_b / "skin" / "wrinkles" / "classical.npz")
    ffhq_a = _load_npz(pdir_a / "skin" / "wrinkles" / "ffhq.npz")
    ffhq_b = _load_npz(pdir_b / "skin" / "wrinkles" / "ffhq.npz")
    if wr_a and wr_b:
        result["wrinkles"] = _compare_wrinkles(wr_a, wr_b, ffhq_a, ffhq_b)

    # ── 4. Local features (pores/scars) ──
    loc_a = _load_npz(pdir_a / "skin" / "features" / "local_candidates.npz")
    loc_b = _load_npz(pdir_b / "skin" / "features" / "local_candidates.npz")
    if loc_a and loc_b:
        result["local_features"] = _compare_local(loc_a, loc_b)

    return result


def _compare_texture(tex_a, tex_b) -> dict:
    """Per-zone cosine similarity of texture feature vectors."""
    def _zmap(tex):
        m = {}
        vals = tex.get("values")
        zids = tex.get("zone_id")
        states = tex.get("state")
        sups = tex.get("effective_support")
        if vals is None or zids is None:
            return m
        for i in range(len(zids)):
            zid = zids[i]
            if isinstance(zid, bytes):
                zid = zid.decode()
            else:
                zid = str(zid)
            st = states[i] if states is not None else "unknown"
            if isinstance(st, bytes):
                st = st.decode()
            sp = float(sups[i]) if sups is not None else 0.0
            if st == "usable" and sp >= 50.0:
                v = np.asarray(vals[i], np.float64).copy()
                v[~np.isfinite(v)] = 0.0
                m[zid] = v
        return m

    ma, mb = _zmap(tex_a), _zmap(tex_b)
    common = sorted(set(ma.keys()) & set(mb.keys()))
    if not common:
        return {"status": "no_common_zones"}

    per_zone = {}
    bone_cos, skin_cos = [], []

    for zid in common:
        va, vb = ma[zid], mb[zid]
        na, nb = np.linalg.norm(va), np.linalg.norm(vb)
        cos = float(np.dot(va, vb) / (na * nb)) if na > 1e-9 and nb > 1e-9 else 0.0

        # Per-feature difference
        feat_diff = {}
        for j in range(min(24, len(va))):
            if np.isfinite(va[j]) and np.isfinite(vb[j]):
                feat_diff[FEATURE_NAMES[j]] = float(va[j] - vb[j])

        per_zone[zid] = {"cosine": cos, "feature_diff": feat_diff}

        try:
            zi = int(zid[1:]) - 1 if zid.startswith("A") else -1
        except (ValueError, IndexError):
            zi = -1
        if 0 <= zi < 20:
            if ZONE_STABILITY[zi] == "bone":
                bone_cos.append(cos)
            elif ZONE_STABILITY[zi] == "skin":
                skin_cos.append(cos)

    # Per-feature-group similarity
    per_group = {}
    for gname, findices in FEATURE_GROUPS.items():
        g_cos = []
        for zid in common:
            va = ma[zid][findices]
            vb = mb[zid][findices]
            na, nb = np.linalg.norm(va), np.linalg.norm(vb)
            if na > 1e-9 and nb > 1e-9:
                g_cos.append(float(np.dot(va, vb) / (na * nb)))
        if g_cos:
            per_group[gname] = {
                "mean_cosine": float(np.mean(g_cos)),
                "min_cosine": float(np.min(g_cos)),
                "n_zones": len(g_cos),
            }

    all_cos = [per_zone[z]["cosine"] for z in common]

    # Most discriminative features (largest inter-zone variance of differences)
    feat_vars = {}
    for j in range(24):
        diffs = [per_zone[z]["feature_diff"].get(FEATURE_NAMES[j], 0)
                 for z in common if FEATURE_NAMES[j] in per_zone[z].get("feature_diff", {})]
        if len(diffs) > 2:
            feat_vars[FEATURE_NAMES[j]] = float(np.var(diffs))
    top_diff = sorted(feat_vars.items(), key=lambda x: -x[1])[:5]

    return {
        "status": "ok",
        "n_common_zones": len(common),
        "overall_cosine": float(np.mean(all_cos)),
        "bone_zone_cosine": float(np.mean(bone_cos)) if bone_cos else None,
        "skin_zone_cosine": float(np.mean(skin_cos)) if skin_cos else None,
        "per_group": per_group,
        "most_different_features": top_diff,
        "per_zone": per_zone,
    }


def _compare_spatial_signatures(sig_a, sig_b) -> dict:
    """Compare spatial signatures: same unique structure at same location.

    This is the KEY test for skin identity: same person has the same
    wrinkle density pattern, pore distribution, texture energy at the
    same anatomical location within each zone.
    """
    try:
        from app7.stage1.skin.spatial_signatures import compare_zone_signatures
        return compare_zone_signatures(sig_a, sig_b)
    except ImportError:
        pass
    # Fallback: inline implementation
    return _compare_spatial_fallback(sig_a, sig_b)


def _compare_spatial_fallback(sig_a, sig_b) -> dict:
    """Inline spatial signature comparison when module import fails."""
    results = {}
    zone_corrs = []

    for zi in range(20):
        key = f"A{zi + 1:02d}"
        sa = sig_a.get(key, {})
        sb = sig_b.get(key, {})
        if sa.get("status") not in ("usable", "coarse_only") or \
           sb.get("status") not in ("usable", "coarse_only"):
            results[key] = {"status": "not_comparable"}
            continue
        bins_a = sa.get("spatial_bins", [])
        bins_b = sb.get("spatial_bins", [])
        if len(bins_a) != len(bins_b) or not bins_a:
            results[key] = {"status": "bin_mismatch"}
            continue
        wr_a = np.array([b.get("wrinkle_density", 0) for b in bins_a])
        wr_b = np.array([b.get("wrinkle_density", 0) for b in bins_b])
        tex_a = np.array([b.get("mean_texture_energy", 0) for b in bins_a])
        tex_b = np.array([b.get("mean_texture_energy", 0) for b in bins_b])
        corrs = []
        for a, b in [(wr_a, wr_b), (tex_a, tex_b)]:
            if len(a) >= 3 and np.std(a) > 1e-9 and np.std(b) > 1e-9:
                corrs.append(float(np.corrcoef(a, b)[0, 1]))
        mc = float(np.mean(corrs)) if corrs else None
        if mc is not None:
            zone_corrs.append(mc)
        results[key] = {"status": "compared", "mean_spatial_corr": mc}

    return {"per_zone": results,
            "overall_spatial_correlation": float(np.mean(zone_corrs)) if zone_corrs else None,
            "n_compared_zones": len(zone_corrs)}


def _compare_wrinkles(wr_a, wr_b, ffhq_a=None, ffhq_b=None) -> dict:
    """Compare wrinkle patterns."""
    ra = np.asarray(wr_a.get("ridge_probability"), np.float32)
    rb = np.asarray(wr_b.get("ridge_probability"), np.float32)
    if ra.size == 0 or rb.size == 0:
        return {"status": "no_ridge_data"}
    ra, rb = ra.ravel(), rb.ravel()
    result = {}
    if len(ra) == len(rb):
        valid = np.isfinite(ra) & np.isfinite(rb) & ((ra > 0.01) | (rb > 0.01))
        if valid.sum() > 100:
            result["classical_correlation"] = float(np.corrcoef(ra[valid], rb[valid])[0, 1])
            # Bhattacharyya: wrinkle density profile similarity
            ha, _ = np.histogram(ra[valid], bins=20, range=(0, 1), density=True)
            hb, _ = np.histogram(rb[valid], bins=20, range=(0, 1), density=True)
            result["histogram_bhattacharyya"] = float(np.sum(np.sqrt(ha * hb)))

    if ffhq_a and ffhq_b:
        fa = np.asarray(ffhq_a.get("probability"), np.float32).ravel()
        fb = np.asarray(ffhq_b.get("probability"), np.float32).ravel()
        if len(fa) == len(fb) and len(fa) > 100:
            v = np.isfinite(fa) & np.isfinite(fb) & ((fa > 0.01) | (fb > 0.01))
            if v.sum() > 100:
                result["ffhq_correlation"] = float(np.corrcoef(fa[v], fb[v])[0, 1])
    return result


def _compare_local(loc_a, loc_b) -> dict:
    """Compare local features (pores/scars) spatial distribution."""
    ca, cb = loc_a.get("candidates"), loc_b.get("candidates")
    if ca is None or cb is None:
        return {"status": "no_candidates"}
    na, nb = len(ca) if ca.ndim > 0 else 0, len(cb) if cb.ndim > 0 else 0
    if na < 3 or nb < 3:
        return {"status": "too_few", "n_a": na, "n_b": nb}
    try:
        xy_a = np.column_stack([ca["x"], ca["y"]]).astype(np.float64)
        xy_b = np.column_stack([cb["x"], cb["y"]]).astype(np.float64)
        all_xy = np.vstack([xy_a, xy_b])
        xr = all_xy[:, 0].max() - all_xy[:, 0].min() + 1
        yr = all_xy[:, 1].max() - all_xy[:, 1].min() + 1
        xm, ym = all_xy[:, 0].min(), all_xy[:, 1].min()
        ha, _, _ = np.histogram2d((xy_a[:, 0] - xm) / xr, (xy_a[:, 1] - ym) / yr,
                                   bins=16, range=[[0, 1], [0, 1]])
        hb, _, _ = np.histogram2d((xy_b[:, 0] - xm) / xr, (xy_b[:, 1] - ym) / yr,
                                   bins=16, range=[[0, 1], [0, 1]])
        ha, hb = ha / (ha.sum() + 1e-9), hb / (hb.sum() + 1e-9)
        return {"n_a": na, "n_b": nb,
                "spatial_correlation": float(np.corrcoef(ha.ravel(), hb.ravel())[0, 1])}
    except Exception:
        return {"n_a": na, "n_b": nb}


# ═══════════════════════════════════════════════════════════════════════════
# Verdicts
# ═══════════════════════════════════════════════════════════════════════════

def verdict_geometry(geom: dict) -> dict:
    """Classify geometry comparison."""
    signals, details = [], []

    lm = geom.get("landmarks", {})
    if lm.get("status") == "ok":
        bone_rms = lm.get("bone_rms")
        if bone_rms is not None:
            if bone_rms < 0.015:
                signals.append(2); details.append(f"bone_ldm_rms={bone_rms:.4f} (<0.015)")
            elif bone_rms < 0.025:
                signals.append(1); details.append(f"bone_ldm_rms={bone_rms:.4f} (<0.025)")
            elif bone_rms < 0.04:
                signals.append(0); details.append(f"bone_ldm_rms={bone_rms:.4f} (~0.025-0.04)")
            elif bone_rms < 0.07:
                signals.append(-1); details.append(f"bone_ldm_rms={bone_rms:.4f} (>0.04)")
            else:
                signals.append(-2); details.append(f"bone_ldm_rms={bone_rms:.4f} (>>0.07)")

    geo = geom.get("geodesic", {})
    if geo.get("status") == "ok":
        rd = geo.get("bone_mean_rel_diff")
        corr = geo.get("full_corr")
        if rd is not None:
            if rd < 0.03:
                signals.append(2); details.append(f"geo_bone_reldiff={rd:.4f} (<0.03)")
            elif rd < 0.08:
                signals.append(1); details.append(f"geo_bone_reldiff={rd:.4f} (<0.08)")
            elif rd < 0.15:
                signals.append(0); details.append(f"geo_bone_reldiff={rd:.4f} (~0.08-0.15)")
            else:
                signals.append(-2); details.append(f"geo_bone_reldiff={rd:.4f} (>0.15)")
        if corr is not None:
            details.append(f"geo_corr={corr:.3f}")

    alpha = geom.get("alpha")
    if alpha:
        cos = alpha.get("cosine_similarity", 0)
        if cos > 0.95:
            signals.append(2); details.append(f"α_id={cos:.4f}")
        elif cos > 0.90:
            signals.append(1); details.append(f"α_id={cos:.4f}")
        elif cos > 0.80:
            signals.append(0); details.append(f"α_id={cos:.4f}")
        else:
            signals.append(-2); details.append(f"α_id={cos:.4f}")

    mesh = geom.get("mesh", {})
    bone_rms = mesh.get("bone_rms")
    if bone_rms is not None:
        details.append(f"mesh_bone_rms={bone_rms:.4f}")

    if not signals:
        return {"label": "NO_DATA", "score": 0, "details": details}
    score = float(np.mean(signals))
    if score >= 1.5: label = "SAME"
    elif score >= 0.5: label = "LIKELY_SAME"
    elif score >= -0.5: label = "BORDERLINE"
    elif score >= -1.5: label = "LIKELY_DIFFERENT"
    else: label = "DIFFERENT"
    return {"label": label, "score": score, "details": details}


def verdict_skin(skin: dict) -> dict:
    """Classify skin comparison."""
    signals, details = [], []

    tex = skin.get("texture", {})
    if tex.get("status") == "ok":
        oc = tex.get("overall_cosine", 0)
        if oc > 0.90:
            signals.append(2); details.append(f"tex_cos={oc:.3f}")
        elif oc > 0.80:
            signals.append(1); details.append(f"tex_cos={oc:.3f}")
        elif oc > 0.65:
            signals.append(0); details.append(f"tex_cos={oc:.3f}")
        else:
            signals.append(-2); details.append(f"tex_cos={oc:.3f}")

        for gn, gd in tex.get("per_group", {}).items():
            mc = gd.get("mean_cosine", 0)
            details.append(f"{gn}={mc:.3f}")
            if gn in ("microtexture", "spectral") and mc < 0.5:
                signals.append(-1)

    sp = skin.get("spatial", {})
    osc = sp.get("overall_spatial_correlation")
    if osc is not None:
        if osc > 0.7:
            signals.append(2); details.append(f"spatial_corr={osc:.3f}")
        elif osc > 0.4:
            signals.append(1); details.append(f"spatial_corr={osc:.3f}")
        elif osc > 0.1:
            signals.append(0); details.append(f"spatial_corr={osc:.3f}")
        else:
            signals.append(-1); details.append(f"spatial_corr={osc:.3f}")

    wr = skin.get("wrinkles", {})
    wc = wr.get("classical_correlation")
    if wc is not None:
        details.append(f"wrinkle_corr={wc:.3f}")

    if not signals:
        return {"label": "NO_DATA", "score": 0, "details": details}
    score = float(np.mean(signals))
    if score >= 1.0: label = "SAME"
    elif score >= 0.3: label = "LIKELY_SAME"
    elif score >= -0.3: label = "BORDERLINE"
    elif score >= -1.0: label = "LIKELY_DIFFERENT"
    else: label = "DIFFERENT"
    return {"label": label, "score": score, "details": details}


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _procrustes(a, b):
    """Procrustes alignment: center + scale + optimal rotation."""
    a = a.copy().astype(np.float64)
    b = b.copy().astype(np.float64)
    a -= a.mean(axis=0); b -= b.mean(axis=0)
    sa = np.sqrt(np.mean(np.sum(a ** 2, axis=1)))
    sb = np.sqrt(np.mean(np.sum(b ** 2, axis=1)))
    if sa > 1e-9: a /= sa
    if sb > 1e-9: b /= sb
    H = a.T @ b
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1; R = Vt.T @ U.T
    return a, b @ R.T


def _normalize_pair(a, b):
    a = a.copy().astype(np.float64); b = b.copy().astype(np.float64)
    for m in (a, b):
        m -= m.mean(axis=0)
        s = np.sqrt(np.mean(np.sum(m ** 2, axis=1)))
        if s > 1e-8: m /= s
    return a, b


def _unpack_vis(packed, n):
    if packed is None:
        return np.ones(n, bool)
    return np.unpackbits(np.asarray(packed, np.uint8), bitorder="little")[:n].astype(bool)


def _vertex_zones_approx(mesh):
    """Approximate vertex zone assignment from mesh coordinates."""
    n = len(mesh)
    zones = np.zeros(n, dtype=np.int32)
    x, y, z = mesh[:, 0], mesh[:, 1], mesh[:, 2]
    zones[(y > 0.65)] = 0;  zones[(y > 0.4) & (y <= 0.65)] = 1
    zones[(y > 0.25) & (np.abs(x) < 0.15) & (y <= 0.4)] = 2
    zones[(y > 0.0) & (np.abs(x) < 0.15) & (y <= 0.25)] = 3
    zones[(y > -0.1) & (y <= 0.1) & (np.abs(x) < 0.12) & (z > 0.2)] = 4
    zones[(y > -0.1) & (y <= 0.1) & (x < 0) & (np.abs(x) >= 0.08) & (np.abs(x) < 0.22)] = 5
    zones[(y > -0.1) & (y <= 0.1) & (x >= 0) & (np.abs(x) >= 0.08) & (np.abs(x) < 0.22)] = 6
    zones[(y > -0.05) & (y <= 0.35) & (x < 0) & (np.abs(x) >= 0.15) & (np.abs(x) < 0.45)] = 7
    zones[(y > -0.05) & (y <= 0.35) & (x >= 0) & (np.abs(x) >= 0.15) & (np.abs(x) < 0.45)] = 8
    zones[(y > -0.1) & (y <= 0.25) & (x < 0) & (np.abs(x) >= 0.25) & (np.abs(x) < 0.6)] = 9
    zones[(y > -0.1) & (y <= 0.25) & (x >= 0) & (np.abs(x) >= 0.25) & (np.abs(x) < 0.6)] = 10
    zones[(y > -0.3) & (y <= 0.15) & (x < 0) & (np.abs(x) >= 0.2)] = 11
    zones[(y > -0.3) & (y <= 0.15) & (x >= 0) & (np.abs(x) >= 0.2)] = 12
    zones[(y > -0.35) & (y <= -0.08) & (np.abs(x) < 0.25) & (y > -0.2)] = 13
    zones[(y > -0.35) & (y <= -0.08) & (np.abs(x) < 0.25) & (y <= -0.2)] = 14
    zones[(y <= -0.3) & (np.abs(x) < 0.25)] = 15
    zones[(y > -0.55) & (y <= -0.1) & (x < 0) & (np.abs(x) >= 0.2)] = 16
    zones[(y > -0.55) & (y <= -0.1) & (x >= 0) & (np.abs(x) >= 0.2)] = 17
    zones[(y > 0.15) & (y <= 0.55) & (x < 0) & (np.abs(x) >= 0.45)] = 18
    zones[(y > 0.15) & (y <= 0.55) & (x >= 0) & (np.abs(x) >= 0.45)] = 19
    return zones


def _stats(dist, mask):
    if not mask.any():
        return {"mean": None, "rms": None, "median": None, "p95": None, "n": 0}
    d = dist[mask]
    return {"mean": float(np.mean(d)), "rms": float(np.sqrt(np.mean(d ** 2))),
            "median": float(np.median(d)), "p95": float(np.percentile(d, 95)), "n": int(mask.sum())}


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Verify Stage 1: same person or different?")
    ap.add_argument("--output", required=True, help="Stage 1 output directory")
    ap.add_argument("--save-json", default=None, help="Save results JSON")
    args = ap.parse_args()

    output_dir = Path(args.output).resolve()
    if not output_dir.is_dir():
        print(f"ERROR: {output_dir} not found", file=sys.stderr)
        sys.exit(1)

    # Load index
    import csv
    idx_path = output_dir / "main_index.csv"
    if not idx_path.is_file():
        print("ERROR: main_index.csv not found. Run Stage 1 first.", file=sys.stderr)
        sys.exit(1)
    with open(idx_path, encoding="utf-8") as f:
        index = list(csv.DictReader(f))

    by_bin = defaultdict(list)
    for row in index:
        by_bin[row.get("pose_bin", "?")].append(row)

    print("=" * 80)
    print("STAGE 1 VERIFICATION: same person or different?")
    print("  GEOMETRY: aligned landmarks + geodesic + alpha_id + mesh")
    print("  SKIN:     atlas-localized texture + spatial signatures + wrinkles")
    print("=" * 80)
    bins_str = ", ".join(f"{k}({len(v)})" for k, v in sorted(by_bin.items()))
    print(f"Photos: {len(index)}  Bins: {bins_str}\n")

    # Load all photo data
    pdata = {}
    for row in index:
        pid = row["photo_id"]
        pdir = output_dir / pid
        rec = _load_npz(pdir / "reconstruction.npz")
        info = _load_json(pdir / "info.json")
        if rec is None or info is None:
            continue
        pdata[pid] = {"dir": pdir, "rec": rec, "info": info}

    # Per-bin comparison
    all_results = {}
    g_geom, g_skin = [], []

    for bname, rows in sorted(by_bin.items()):
        pids = [r["photo_id"] for r in rows if r["photo_id"] in pdata]
        if len(pids) < 2:
            print(f"[{bname}] {len(pids)} photo(s), need ≥2\n")
            continue

        print(f"{'═' * 70}")
        print(f"  {bname} — {len(pids)} photos, {len(pids)*(len(pids)-1)//2} pairs")
        print(f"{'═' * 70}")

        bin_pairs = []
        for i in range(len(pids)):
            for j in range(i + 1, len(pids)):
                pa, pb = pids[i], pids[j]
                da, db = pdata[pa], pdata[pb]

                geom = compare_geometry(da["dir"], db["dir"])
                skin = compare_skin(da["dir"], db["dir"])
                gv = verdict_geometry(geom)
                sv = verdict_skin(skin)

                g_geom.append(gv["score"])
                g_skin.append(sv["score"])

                # Key metrics
                lm = geom.get("landmarks", {})
                bone_rms = lm.get("bone_rms")
                geo_rd = geom.get("geodesic", {}).get("bone_mean_rel_diff")
                alpha_cos = geom.get("alpha", {}).get("cosine_similarity")
                tex_cos = skin.get("texture", {}).get("overall_cosine") if skin.get("texture") else None
                sp_corr = skin.get("spatial", {}).get("overall_spatial_correlation") if skin.get("spatial") else None

                print(f"  {pa} vs {pb}")
                print(f"    GEOM: {gv['label']:20s} | bone_ldm={bone_rms:.4f if bone_rms else 'N/A'}  "
                      f"geo_reldiff={geo_rd:.4f if geo_rd else 'N/A'}  α_id={alpha_cos:.3f if alpha_cos else 'N/A'}")
                print(f"    SKIN: {sv['label']:20s} | tex={tex_cos:.3f if tex_cos else 'N/A'}  "
                      f"spatial={sp_corr:.3f if sp_corr else 'N/A'}")

                # Per-zone bone landmark detail
                pz = lm.get("per_zone", {})
                bone_zones = {k: v for k, v in pz.items() if v.get("stability") == "bone"}
                if bone_zones:
                    bz_str = "  ".join(f"{k}={v['rms']:.4f}" for k, v in sorted(bone_zones.items()) if v.get("rms"))
                    print(f"    Bone zones: {bz_str}")

                # Most different landmarks
                top_ldm = lm.get("most_different_landmarks", [])[:3]
                if top_ldm:
                    ldm_str = "  ".join(f"L{l['landmark_id']}({l['zone']})={l['distance']:.4f}" for l in top_ldm)
                    print(f"    Top different: {ldm_str}")

                # Spatial signature per zone
                sp = skin.get("spatial", {})
                sp_zones = sp.get("per_zone", {})
                if sp_zones:
                    comp_zones = [(k, v) for k, v in sp_zones.items() if v.get("status") == "compared"]
                    if comp_zones:
                        sp_str = "  ".join(f"{k}={v.get('mean_spatial_corr', 0):.2f}" for k, v in comp_zones[:8])
                        print(f"    Spatial: {sp_str}")

                print()

                bin_pairs.append({
                    "a": pa, "b": pb,
                    "geometry_verdict": gv, "skin_verdict": sv,
                    "key": {
                        "bone_ldm_rms": bone_rms, "geo_bone_reldiff": geo_rd,
                        "alpha_cos": alpha_cos, "tex_cos": tex_cos, "spatial_corr": sp_corr,
                    },
                })

        all_results[bname] = bin_pairs

    # Global summary
    print("\n" + "=" * 80)
    print("GLOBAL SUMMARY")
    print("=" * 80)
    if g_geom:
        gm = float(np.mean(g_geom))
        print(f"  Geometry: mean={gm:+.2f}  →  {'ALL SAME' if gm > 1.0 else 'MIXED' if gm > -1.0 else 'DIFFERENT'}")
    if g_skin:
        sm = float(np.mean(g_skin))
        print(f"  Skin:     mean={sm:+.2f}  →  {'ALL SAME' if sm > 0.5 else 'MIXED' if sm > -0.3 else 'DIFFERENT'}")

    # Save JSON
    out = {"global": {"geometry_mean": float(np.mean(g_geom)) if g_geom else None,
                       "skin_mean": float(np.mean(g_skin)) if g_skin else None},
           "per_bin": {}}
    for bn, pairs in all_results.items():
        out["per_bin"][bn] = [{"a": p["a"], "b": p["b"],
                               "geometry_verdict": p["geometry_verdict"],
                               "skin_verdict": p["skin_verdict"],
                               "key_metrics": p["key"]} for p in pairs]
    jp = args.save_json or str(output_dir / "verify_results.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else float(o) if isinstance(o, np.floating) else int(o))
    print(f"\nSaved: {jp}")


if __name__ == "__main__":
    main()
