"""Full texture feature extraction per atlas zone — 24 features.

Uses photometric-normalized luminance for illumination-robust measurements.
"""

from __future__ import annotations

import cv2
import numpy as np

FEATURES = (
    "lbp_entropy", "lbp_uniform_fraction",
    "glcm_contrast", "glcm_homogeneity", "glcm_energy",
    "gabor_energy", "gabor_anisotropy",
    "spectral_entropy", "spectral_high_ratio",
    "structure_coherence", "log_blob_density", "local_mad",
    "lab_L_median", "lab_a_median", "lab_b_median", "lab_a_mad", "chroma_mad", "color_entropy",
    # v4 additions
    "glcm_dissimilarity", "glcm_correlation", "glcm_asm",
    "spectral_low_ratio", "spectral_mid_ratio", "spectral_slope",
)


def _lbp(gray01: np.ndarray) -> np.ndarray:
    g = gray01
    c = g[1:-1, 1:-1]
    out = np.zeros(g.shape, dtype=np.uint8)
    code = np.zeros(c.shape, dtype=np.uint8)
    for k, (dy, dx) in enumerate(((-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1))):
        code |= ((g[1 + dy:g.shape[0] - 1 + dy, 1 + dx:g.shape[1] - 1 + dx] >= c).astype(np.uint8) << k)
    out[1:-1, 1:-1] = code
    return out


def _glcm_full(gray01, valid_mask, L=16):
    g = np.clip((gray01 * L).astype(int), 0, L - 1)
    M = np.zeros((L, L), dtype=np.float64)
    offsets = [(0, 1), (1, 0), (1, 1), (1, -1), (0, 2), (2, 0)]
    H, W = gray01.shape
    for dy, dx in offsets:
        y0a, y1a = max(0, -dy), min(H, H - dy)
        y0b, y1b = max(0, dy), min(H, H + dy)
        x0a, x1a = max(0, -dx), min(W, W - dx)
        x0b, x1b = max(0, dx), min(W, W + dx)
        if y1a <= y0a or x1a <= x0a:
            continue
        valid = valid_mask[y0a:y1a, x0a:x1a] & valid_mask[y0b:y1b, x0b:x1b]
        if not np.any(valid):
            continue
        a = g[y0a:y1a, x0a:x1a][valid]
        b = g[y0b:y1b, x0b:x1b][valid]
        for i, j in zip(a, b):
            M[i, j] += 1
            M[j, i] += 1
    if M.sum() == 0:
        return {k: np.nan for k in ("contrast", "dissimilarity", "homogeneity", "energy", "correlation", "asm")}
    P = M / M.sum()
    ii, jj = np.indices(P.shape)
    contrast = float(np.sum(P * (ii - jj) ** 2))
    dissimilarity = float(np.sum(P * np.abs(ii - jj)))
    homogeneity = float(np.sum(P / (1 + (ii - jj) ** 2)))
    asm = float(np.sum(P ** 2))
    energy = float(np.sqrt(asm))
    mu_i = float(np.sum(ii * P))
    mu_j = float(np.sum(jj * P))
    pi = P.sum(axis=1)
    pj = P.sum(axis=0)
    sigma_i = float(np.sqrt(np.sum((np.arange(L) - mu_i) ** 2 * pi)))
    sigma_j = float(np.sqrt(np.sum((np.arange(L) - mu_j) ** 2 * pj)))
    correlation = float(np.sum((ii - mu_i) * (jj - mu_j) * P) / max(sigma_i * sigma_j, 1e-9))
    return {"contrast": contrast, "dissimilarity": dissimilarity, "homogeneity": homogeneity,
            "energy": energy, "correlation": correlation, "asm": asm}


def _spectral_full(gray01, valid_mask):
    ys, xs = np.where(valid_mask)
    if len(xs) < 128:
        return {k: np.nan for k in ("entropy", "high_ratio", "low_ratio", "mid_ratio", "slope", "anisotropy")}
    x0, x1 = xs.min(), xs.max() + 1
    y0, y1 = ys.min(), ys.max() + 1
    patch = gray01[y0:y1, x0:x1]
    mask = valid_mask[y0:y1, x0:x1]
    Y, X = np.mgrid[:patch.shape[0], :patch.shape[1]]
    try:
        A = np.c_[X[mask], Y[mask], np.ones(mask.sum())]
        coef, _, _, _ = np.linalg.lstsq(A, patch[mask], rcond=None)
        detrended = (patch - (coef[0] * X + coef[1] * Y + coef[2])) * mask
    except Exception:
        detrended = (patch - patch.mean()) * mask
    window = np.outer(np.hanning(patch.shape[0]), np.hanning(patch.shape[1]))
    F = np.abs(np.fft.fftshift(np.fft.fft2(detrended * window))) ** 2
    cy, cx = np.array(F.shape) // 2
    R = np.hypot(*np.mgrid[-cy:F.shape[0] - cy, -cx:F.shape[1] - cx])
    maxR = float(R.max()) + 1e-9
    low_mask = (R < 0.1 * maxR) & (R > 1)
    mid_mask = (R >= 0.1 * maxR) & (R < 0.25 * maxR)
    high_mask = R >= 0.25 * maxR
    total = F[R > 1].sum() + 1e-12
    low_e = F[low_mask].sum() / total
    mid_e = F[mid_mask].sum() / total
    high_e = F[high_mask].sum() / total
    p = F[R > 1].flatten()
    p = p / (p.sum() + 1e-12)
    entropy = float(-np.sum(p * np.log(p + 1e-12)) / np.log(max(2, len(p))))
    # slope
    bins = 16
    r_bins = np.linspace(0, maxR, bins + 1)
    centres, prof = [], []
    for i in range(bins):
        ring = (R >= r_bins[i]) & (R < r_bins[i + 1]) & (R > 1)
        if np.any(ring):
            centres.append((r_bins[i] + r_bins[i + 1]) / 2)
            prof.append(F[ring].mean() + 1e-12)
    centres, prof = np.array(centres), np.array(prof)
    valid_c = (centres > 0) & (prof > 0)
    slope = float(np.polyfit(np.log(centres[valid_c]), np.log(prof[valid_c]), 1)[0]) if valid_c.sum() >= 3 else np.nan
    # anisotropy
    angles = np.arctan2(*np.mgrid[-cy:F.shape[0] - cy, -cx:F.shape[1] - cx][::-1])
    ang_en = [F[(angles >= -np.pi + k * 2 * np.pi / 8) & (angles < -np.pi + (k + 1) * 2 * np.pi / 8) & (R > 0.1 * maxR)].sum() for k in range(8)]
    anisotropy = float(np.std(ang_en) / (np.mean(ang_en) + 1e-12))
    return {"entropy": entropy, "high_ratio": float(high_e), "low_ratio": float(low_e),
            "mid_ratio": float(mid_e), "slope": slope, "anisotropy": anisotropy}


def extract_texture_features(bgr, w, A, S, min_support=100):
    """Extract 24 texture features per zone. Uses illumination-normalized grayscale."""
    # Use low-frequency-normalized grayscale for illumination robustness
    from ..photometric import branches as photometric_branches
    mask_full = np.asarray(w) > 0
    photo = photometric_branches(bgr, mask_full)
    gray_norm = np.asarray(photo["low_frequency_normalized"], np.float32)
    # Also keep raw for Lab color space
    gray_raw = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] /= 255.0
    lab[..., 1:] = (lab[..., 1:] - 128) / 128.0

    lbp = _lbp(gray_raw)  # LBP on raw luminance
    gabors = []
    for theta in np.linspace(0, np.pi, 8, endpoint=False):
        kern = cv2.getGaborKernel((15, 15), 3, theta, 6, 0.6, ktype=cv2.CV_32F)
        gabors.append(np.abs(cv2.filter2D(gray_norm, cv2.CV_32F, kern)))
    gabors = np.stack(gabors) if gabors else np.zeros((1,) + gray_raw.shape, dtype=np.float32)

    gx = cv2.Sobel(gray_norm, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_norm, cv2.CV_32F, 0, 1, ksize=3)
    Jx = cv2.GaussianBlur(gx * gx, (0, 0), 2)
    Jy = cv2.GaussianBlur(gy * gy, (0, 0), 2)
    Jxy = cv2.GaussianBlur(gx * gy, (0, 0), 2)
    coh = np.sqrt((Jx - Jy) ** 2 + 4 * Jxy ** 2) / (Jx + Jy + 1e-6)
    log_map = np.abs(cv2.Laplacian(cv2.GaussianBlur(gray_norm, (0, 0), 1.4), cv2.CV_32F))

    rows = []
    for level, zmap, n, prefix in [("A20", A, 20, "A"), ("S40", S, 40, "S")]:
        for i in range(n):
            mask = (zmap == i) & (w > 0)
            support = float(np.asarray(w, np.float32)[mask].sum())
            values = np.full(len(FEATURES), np.nan, dtype=np.float32)
            state = "usable" if support >= min_support and mask.sum() >= 128 else "not_measurable"
            if state == "usable":
                wm = np.asarray(w, np.float32)[mask]
                # LBP
                hist = np.bincount(lbp[mask], weights=wm, minlength=256).astype(float)
                hist /= hist.sum() + 1e-12
                bits = np.unpackbits(np.arange(256, dtype=np.uint8)[:, None], axis=1)
                uniform = np.sum(np.abs(np.diff(np.c_[bits, bits[:, 0]], axis=1)), axis=1) <= 2
                values[0] = float(-np.sum(hist * np.log(hist + 1e-12)))
                values[1] = float(hist[uniform].sum())
                # GLCM
                glcm = _glcm_full(gray_raw, mask, L=16)
                values[2] = glcm.get("contrast", np.nan)
                values[3] = glcm.get("homogeneity", np.nan)
                values[4] = glcm.get("energy", np.nan)
                # Gabor
                g_energy_per = np.array([np.average(g[mask], weights=wm) for g in gabors])
                values[5] = float(g_energy_per.mean())
                values[6] = float((g_energy_per.max() - g_energy_per.min()) / (g_energy_per.mean() + 1e-8))
                # Spectral
                spec = _spectral_full(gray_norm, mask)
                values[7] = spec.get("entropy", np.nan)
                values[8] = spec.get("high_ratio", np.nan)
                # Coherence
                values[9] = float(np.average(coh[mask], weights=wm))
                # LoG blobs
                values[10] = float(np.mean(log_map[mask] >= np.percentile(log_map[mask], 90))) if mask.sum() else 0.0
                # Local MAD
                med = np.median(gray_norm[mask])
                values[11] = float(np.median(np.abs(gray_norm[mask] - med)))
                # Lab
                try:
                    lv = lab[mask]
                    values[12] = float(np.median(lv[:, 0]))
                    values[13] = float(np.median(lv[:, 1]))
                    values[14] = float(np.median(lv[:, 2]))
                    values[15] = float(np.median(np.abs(lv[:, 1] - values[13])))
                    chroma = np.hypot(lv[:, 1], lv[:, 2])
                    values[16] = float(np.median(np.abs(chroma - np.median(chroma))))
                    ha, _ = np.histogram(lv[:, 1], bins=16, range=(-1, 1), weights=wm)
                    ha = ha / (ha.sum() + 1e-12)
                    values[17] = float(-np.sum(ha * np.log(ha + 1e-12)))
                except Exception:
                    values[12:18] = np.nan
                # v4 additions
                values[18] = glcm.get("dissimilarity", np.nan)
                values[19] = glcm.get("correlation", np.nan)
                values[20] = glcm.get("asm", np.nan)
                values[21] = spec.get("low_ratio", np.nan)
                values[22] = spec.get("mid_ratio", np.nan)
                values[23] = spec.get("slope", np.nan)
            rows.append({"zone_level": level, "zone_id": f"{prefix}{i + 1:02d}",
                         "state": state, "effective_support": support, "values": values})
    return rows
