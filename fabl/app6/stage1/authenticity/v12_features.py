"""v1.2 NEW metric extractor for test panel (top-40 + required bases)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

_RECIPE_PATHS = [
    Path(__file__).resolve().parent / "v12_test_recipe.json",
]


def _load_recipe() -> dict[str, Any]:
    for p in _RECIPE_PATHS:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("v12_test_recipe.json not found")


def _entropy(v: np.ndarray, bins: int = 32, rng=None) -> float:
    h = np.histogram(v, bins=bins, range=rng)[0].astype(np.float64)
    p = h / (h.sum() + 1e-9)
    p = p[p > 0]
    return float(-(p * np.log(p)).sum() / np.log(bins))


def _std(v: np.ndarray) -> float:
    return float(np.std(v) + 1e-9)


def _pct(v: np.ndarray, q: float) -> float:
    return float(np.percentile(v, q))


def extract_v12_bases(rgb: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    """Atomic bases required by top-40 derived metrics."""
    x = rgb.astype(np.float64)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    m = mask.astype(bool)
    if int(m.sum()) < 1500:
        raise ValueError("mask too small")

    L = 0.299 * r + 0.587 * g + 0.114 * b
    v = L[m]
    p1, p99 = np.percentile(v, [1, 99])
    N = np.clip((L - p1) / (p99 - p1 + 1e-6), 0, 1)
    ys, xs = np.where(m)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
    h, w = m.shape
    cy, cx = (y0 + y1) / 2.0, (x0 + x1) / 2.0
    yy, xx = np.mgrid[:h, :w]
    cheek = m & (yy > y0 + 0.45 * (y1 - y0)) & (yy < y0 + 0.82 * (y1 - y0)) & (np.abs(xx - cx) > 0.12 * (x1 - x0))
    forehead = m & (yy < y0 + 0.28 * (y1 - y0)) & (np.abs(xx - cx) < 0.35 * (x1 - x0))

    def roi(arr, rm):
        return arr[rm] if rm.any() and int(rm.sum()) > 200 else arr[m]

    out: dict[str, float] = {}
    s = r + g + b + 1e-6
    rn, gn, bn = r / s, g / s, b / s
    redness = r - 0.5 * (g + b)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float64)
    a_ch = lab[..., 1]
    out["redness_ent"] = _entropy(redness[m])
    out["bn_ent"] = _entropy(bn[m])
    out["rn_ent"] = _entropy(rn[m])
    out["lab_b_ent"] = _entropy(lab[..., 2][m])
    out["a_N_corr"] = float(np.corrcoef(a_ch[m], N[m])[0, 1])
    out["color_cov_rg"] = float(np.cov((rn - gn)[m], N[m])[0, 1])
    out["fore_red_std"] = _std(roi(redness, forehead))
    out["cheek_rn_ent"] = _entropy(roi(rn, cheek))

    mott_r = []
    for iy in range(6):
        for ix in range(6):
            ya = y0 + (y1 - y0) * iy // 6
            yb = y0 + (y1 - y0) * (iy + 1) // 6
            xa = x0 + (x1 - x0) * ix // 6
            xb = x0 + (x1 - x0) * (ix + 1) // 6
            pm = m[ya:yb, xa:xb]
            if int(pm.sum()) < 80:
                continue
            mott_r.append(float(np.std(redness[ya:yb, xa:xb][pm])))
    mott_r = np.asarray(mott_r or [0.0])
    out["mottle_red_med"] = float(np.median(mott_r))

    mx = np.maximum(np.maximum(r, g), b)
    spec = (mx - L) / 255.0
    out["spec_cheek_over_fore"] = _pct(roi(spec, cheek), 95) / (_pct(roi(spec, forehead), 95) + 1e-9)

    gx = cv2.Sobel(N, cv2.CV_64F, 1, 0, 3)
    gy = cv2.Sobel(N, cv2.CV_64F, 0, 1, 3)
    gm = np.hypot(gx, gy)
    gmv = gm[m]
    out["grad_p99_med"] = _pct(gmv, 99) / (_pct(gmv, 50) + 1e-9)
    out["grad_p95_med"] = _pct(gmv, 95) / (_pct(gmv, 50) + 1e-9)
    out["fore_grad_p99_med"] = _pct(roi(gm, forehead), 99) / (_pct(roi(gm, forehead), 50) + 1e-9)
    code = ((gx > 0).astype(np.uint8) + 2 * (gy > 0).astype(np.uint8))
    out["gradsign_ent"] = _entropy(code[m], bins=4, rng=(0, 3))

    d1 = cv2.GaussianBlur(N, (0, 0), 0.8) - cv2.GaussianBlur(N, (0, 0), 1.6)
    vv = d1[m]
    sd = _std(vv)
    out["dog1_kurt"] = float(np.mean(((vv - vv.mean()) / sd) ** 4) - 3)

    pore = cv2.GaussianBlur(N, (0, 0), 0.6) - cv2.GaussianBlur(N, (0, 0), 1.3)
    thr_p = np.percentile(np.abs(pore[m]), 85)
    pores = ((np.abs(pore) > thr_p) & m).astype(np.uint8)
    nlab, _, st, _ = cv2.connectedComponentsWithStats(pores, 8)
    out["pore_cc_dens"] = float(max(nlab - 1, 0)) / (m.sum() / 1000.0)
    pe = []
    for iy in range(5):
        for ix in range(5):
            ya = y0 + (y1 - y0) * iy // 5
            yb = y0 + (y1 - y0) * (iy + 1) // 5
            xa = x0 + (x1 - x0) * ix // 5
            xb = x0 + (x1 - x0) * (ix + 1) // 5
            pm = m[ya:yb, xa:xb]
            if int(pm.sum()) < 80:
                continue
            pe.append(float(np.mean(np.abs(pore[ya:yb, xa:xb][pm]))))
    pe = np.asarray(pe or [0.0])
    out["pore_patch_cv"] = float(pe.std() / (abs(pe.mean()) + 1e-9))
    out["pore_patch_min_max"] = float(pe.min() / (pe.max() + 1e-9))

    rr = np.sqrt(((yy - cy) / (0.5 * (y1 - y0) + 1e-9)) ** 2 + ((xx - cx) / (0.5 * (x1 - x0) + 1e-9)) ** 2)
    bins = np.linspace(0, 1.0, 9)
    prof = []
    for i in range(len(bins) - 1):
        sel = m & (rr >= bins[i]) & (rr < bins[i + 1])
        prof.append(float(np.mean(N[sel])) if int(sel.sum()) > 50 else np.nan)
    p2 = np.array([x for x in prof if np.isfinite(x)], float)
    if len(p2) >= 4:
        out["radial_shade_slope"] = float(np.polyfit(np.arange(len(p2)), p2, 1)[0])
        out["radial_shade_curve"] = float(np.polyfit(np.arange(len(p2)), p2, 2)[0]) if len(p2) >= 3 else 0.0
    else:
        out["radial_shade_slope"] = 0.0
        out["radial_shade_curve"] = 0.0

    lap = cv2.Laplacian(N, cv2.CV_64F)
    out["lap_kurt"] = float(np.mean(((lap[m] - lap[m].mean()) / _std(lap[m])) ** 4) - 3)

    bad = [k for k, val in out.items() if not np.isfinite(val)]
    if bad:
        raise ValueError(f"nonfinite bases: {bad[:8]}")
    return out


def derive_v12_metrics(bases: dict[str, float], recipe: dict[str, Any] | None = None) -> dict[str, float]:
    recipe = recipe or _load_recipe()
    out = dict(bases)

    # stack means used by top40
    stacks = recipe.get("stack_axis_members", {})
    for pref, members in stacks.items():
        vals = [bases[m] for m in members if m in bases]
        if vals:
            out[f"{pref}_stack_mean"] = float(np.mean(vals))
            out[f"{pref}_stack_std"] = float(np.std(vals))
            out[f"{pref}_stack_max"] = float(np.max(vals))
            out[f"{pref}_stack_min"] = float(np.min(vals))
            out[f"{pref}_stack_range"] = out[f"{pref}_stack_max"] - out[f"{pref}_stack_min"]

    # top40 derived ops
    for item in recipe.get("top40", []):
        name = item["metric"]
        if name in out:
            continue
        if name.startswith("drv_"):
            parts = name.split("__")
            if len(parts) < 3:
                continue
            op, a, b = parts[0].replace("drv_", ""), parts[1], parts[2]
            if a not in out or b not in out:
                # try stack alias ery_stack_mean already in out
                continue
            av, bv = float(out[a]), float(out[b])
            if op == "ratio":
                out[name] = av / (abs(bv) + 1e-9)
            elif op == "diff":
                out[name] = av - bv
            elif op == "absdiff":
                out[name] = abs(av - bv)
            elif op == "prod":
                out[name] = av * bv
    return out


def extract_v12_panel(rgb: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    recipe = _load_recipe()
    bases = extract_v12_bases(rgb, mask)
    allm = derive_v12_metrics(bases, recipe)
    # return bases + selected top40 only
    keep = set(recipe.get("base_features_required", [])) | {x["metric"] for x in recipe.get("top40", [])}
    return {k: float(allm[k]) for k in keep if k in allm}
