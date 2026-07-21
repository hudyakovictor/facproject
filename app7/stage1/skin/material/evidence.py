"""Material evidence — experimental synthetic material detection.

NOT a verdict. Aggregates texture and spectral indicators that may
correlate with synthetic materials (silicone masks, deepfakes).
Requires separate PAD calibration before any probability output.
"""

from __future__ import annotations

import numpy as np


def build(texture_rows, quality_maps, applicability):
    """Build material evidence record from texture features and quality data.

    This is experimental — no trained classifier. We compute raw indicators
    and flag them as candidates for manual review.
    """
    usable = [r for r in texture_rows if r["state"] == "usable"]
    if not usable:
        return {
            "schema": "skin-material-evidence-v1",
            "status": "insufficient_evidence",
            "production_evidence_allowed": False,
            "families": {},
            "warning": "no usable texture zones for material analysis",
        }

    v = np.stack([r["values"] for r in usable])

    # Feature indices from FEATURES tuple (see texture/features.py)
    # 0: lbp_entropy, 1: lbp_uniform_fraction
    # 7: spectral_entropy, 8: spectral_high_ratio
    # 11: local_mad, 15: lab_a_mad, 16: chroma_mad, 17: color_entropy
    lbp_entropy_vals = v[:, 0]
    spectral_entropy_vals = v[:, 7]
    local_mad_vals = v[:, 11]

    families = {
        "microtexture": {
            "state": applicability.get("micro_texture", {}).get("state", "unknown"),
            "lbp_entropy_mean": float(np.nanmean(lbp_entropy_vals)) if np.any(np.isfinite(lbp_entropy_vals)) else None,
            "lbp_entropy_std": float(np.nanstd(lbp_entropy_vals)) if np.any(np.isfinite(lbp_entropy_vals)) else None,
            "between_zone_variance": _between_zone_var(v),
        },
        "homogeneity": {
            "state": "usable" if len(usable) > 2 else "not_measurable",
            "local_mad_median": float(np.nanmedian(local_mad_vals)) if np.any(np.isfinite(local_mad_vals)) else None,
        },
        "spectral": {
            "state": "usable" if len(usable) > 2 else "not_measurable",
            "spectral_entropy_mean": float(np.nanmean(spectral_entropy_vals)) if np.any(np.isfinite(spectral_entropy_vals)) else None,
        },
        "specular": {
            "state": applicability.get("material_optics", {}).get("state", "unknown"),
            "specular_fraction": _specular_frac(quality_maps),
        },
        "processing": {
            "state": "usable",
            "jpeg_block_score": float(quality_maps.get("global_jpeg_block_score", 0)),
            "noise_level": float(quality_maps.get("global_noise_level", 0)),
        },
    }

    n_usable = sum(1 for x in families.values() if x["state"] in ("usable", "coarse_only"))
    return {
        "schema": "skin-material-evidence-v1",
        "implementation_status": "experimental_indicators_only",
        "production_evidence_allowed": False,
        "status": "mixed_uncertain" if n_usable else "insufficient_evidence",
        "evidence_sufficiency": n_usable / len(families),
        "families": families,
        "probability": None,
        "warning": "separate PAD calibration required; no verdict; indicators are raw measurements",
    }


def _between_zone_var(v):
    if len(v) < 2:
        return None
    out = []
    for j in range(v.shape[1]):
        x = v[:, j]
        x = x[np.isfinite(x)]
        if len(x) > 1:
            out.append(float(np.var(x)))
    return float(np.median(out)) if out else None


def _specular_frac(qm):
    spec = qm.get("specular_mask")
    qw = qm.get("quality_weight")
    if spec is None or qw is None:
        return None
    domain = np.asarray(qw) > 0
    if not np.any(domain):
        return None
    return float(np.mean(np.asarray(spec)[domain]))
