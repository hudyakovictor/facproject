"""Symmetric completion of the UV texture for the MORPH variant (v3.2).

The hidden half of the face is filled with the horizontally mirrored visible
half (the BFM/3DDFA UV layout is left-right symmetric around u=0.5).

v3.2 upgrades vs v3 (invisible seam):
- Multi-band Laplacian-pyramid blending replaces the single distance-transform
  feather. The v3 feather produced a visible "cord" along the central nasal
  ridge on side-lit poses because the feather is wide enough to average over a
  high-frequency region. The Laplacian stack composites the low frequencies
  with a wide smooth mask and the high frequencies with a tight mask, so the
  seam is invisible at coarse scale and crisply aligned at fine scale.
- Per-strip LAB color match of the mirrored half instead of a single global
  match across the bilateral overlap. The strips run perpendicular to the seam
  (along v), so a vertical lighting gradient from forehead to jaw is corrected
  band by band instead of averaged out and re-applied uniformly.
- Residual holes (covered by neither side, typically nose shadow / inner-mouth)
  use Navier-Stokes inpainting (`cv2.INPAINT_NS`) by default instead of TELEA;
  TELEA propagates intensity along isophote direction and amplified the seam on
  profile shots, while NS propagates along the Laplacian field and gives a
  softer, skin-consistent fill.
- Observed texels remain byte-identical outside the synthetic mask; the mask
  returned to the caller is the union of (mirror-filled, inpainted) texels.

The synthetic region is returned as an explicit mask -- this texture is for
VISUAL morph comparison only and must never feed skin analytics.
"""
from __future__ import annotations

import cv2
import numpy as np


def _median_skin_color(texture: np.ndarray, observed: np.ndarray) -> np.ndarray:
    if observed.any():
        return np.median(texture[observed].reshape(-1, texture.shape[-1]), axis=0)
    return np.full((texture.shape[-1],), 128.0)


def _lab_match_strip(
    source_u8: np.ndarray,
    target_u8: np.ndarray,
    src_strip_mask: np.ndarray,
    tgt_strip_mask: np.ndarray,
) -> np.ndarray:
    """LAB mean/std match of `source_u8` against `target_u8` using only the
    texels inside `src_strip_mask` and `tgt_strip_mask`. Returns the matched
    source image (uint8 BGR) -- same shape as `source_u8`.

    If either strip has too few texels the strip is returned unchanged and the
    caller falls back to the next strip / full-image match.
    """
    if np.count_nonzero(src_strip_mask) < 32 or np.count_nonzero(tgt_strip_mask) < 32:
        return source_u8
    src = cv2.cvtColor(source_u8, cv2.COLOR_BGR2LAB).astype(np.float32)
    tgt = cv2.cvtColor(target_u8, cv2.COLOR_BGR2LAB).astype(np.float32)
    for ch in range(3):
        s = src[..., ch][src_strip_mask]
        t = tgt[..., ch][tgt_strip_mask]
        s_med = np.median(s)
        s_std = np.std(s) + 1e-5
        t_med = np.median(t)
        t_std = np.std(t) + 1e-5
        src[..., ch] = (src[..., ch] - s_med) * (t_std / s_std) + t_med
    return cv2.cvtColor(np.clip(src, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def _per_strip_lab_match(
    texture_u8: np.ndarray,
    mirrored_u8: np.ndarray,
    observed: np.ndarray,
    mirrored_observed: np.ndarray,
    strip_count: int,
) -> np.ndarray:
    """Match mirrored to observed in `strip_count` horizontal bands of v.

    Both atlas halves are matched independently per strip. A strip is the band
    of texels with mirrored_observed==True AND observed==True (the bilateral
    overlap inside that v-band); we transfer median/std of that band's observed
    pixels onto the mirrored side across the whole strip.

    If a strip has too little bilateral overlap it inherits the last good
    strip's transform; if none ever succeeds a full-image fallback is applied.
    """
    S = texture_u8.shape[0]
    out = mirrored_u8.copy()
    # v-bands across the v axis; v is the row axis of the atlas.
    bounds = np.linspace(0, S, strip_count + 1, dtype=np.int64)
    overlap = observed & mirrored_observed
    last_good = None  # (ch, med_s, std_s, med_t, std_t) list
    for k in range(strip_count):
        r0, r1 = int(bounds[k]), int(bounds[k + 1])
        strip = np.zeros((S, S), bool)
        strip[r0:r1, :] = True
        s_overlap = overlap & strip
        if np.count_nonzero(s_overlap) < 32:
            if last_good is None:
                continue
            # apply last good transform across the whole strip
            src = cv2.cvtColor(out, cv2.COLOR_BGR2LAB).astype(np.float32)
            for ch, (med_s, std_s, med_t, std_t) in enumerate(last_good):
                sl = src[r0:r1, :, ch]
                src[r0:r1, :, ch] = (sl - med_s) * (std_t / std_s) + med_t
            out = cv2.cvtColor(np.clip(src, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
            continue
        # current strip transform
        src_lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB).astype(np.float32)
        tgt_lab = cv2.cvtColor(texture_u8, cv2.COLOR_BGR2LAB).astype(np.float32)
        tgt_strip = overlap & strip  # both halves observed here
        transforms = []
        for ch in range(3):
            s = src_lab[..., ch][s_overlap]
            t = tgt_lab[..., ch][tgt_strip]
            med_s, std_s = float(np.median(s)), float(np.std(s) + 1e-5)
            med_t, std_t = float(np.median(t)), float(np.std(t) + 1e-5)
            src_lab[r0:r1, :, ch] = (
                src_lab[r0:r1, :, ch] - med_s
            ) * (std_t / std_s) + med_t
            transforms.append((med_s, std_s, med_t, std_t))
        last_good = transforms
        out = cv2.cvtColor(np.clip(src_lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    if last_good is None:
        # full-image fallback: one strip covering everything
        return _lab_match_strip(mirrored_u8, texture_u8, mirrored_observed, observed)
    return out


def _laplacian_pyramid(img_f: np.ndarray, levels: int) -> list[np.ndarray]:
    """Standard Laplacian pyramid (per-channel). img_f: (H,W,3) float32 0..255.

    Returns [L_0 (finest), ..., L_{levels-1}, top_gauss] where top_gauss is the
    final low-pass residual that must be added back to reconstruct the image.
    """
    pyr: list[np.ndarray] = []
    cur = img_f
    for _ in range(levels):
        nxt = cv2.pyrDown(cur)
        up = cv2.pyrUp(nxt, dstsize=(cur.shape[1], cur.shape[0]))
        pyr.append(cur - up)
        cur = nxt
    pyr.append(cur)
    return pyr


def _gaussian_alpha_pyramid(mask_f: np.ndarray, levels: int, sigma: float) -> list[np.ndarray]:
    """Build a smoothly varying alpha mask pyramid.

    Bottom level is the raw binary seam mask (1 where mirrored wins, 0 where
    observed wins), blurred at progressively larger sigmas. The returned list
    goes from finnest (narrow feather) to coarsest (wide feather), matching the
    Laplacian pyramid order.

    σ is in units of the full-resolution atlas: the per-level sigma is scaled by
    2**level so the coarsest band has the widest feather (this is what makes the
    seam disappear in the low frequencies).
    """
    S = mask_f.shape[0]
    alphas: list[np.ndarray] = []
    base = mask_f.astype(np.float32)
    cur = base
    for lvl in range(levels):
        # Widen sigma at coarser levels: each pyramid level halves the resolution,
        # so we scale sigma by 2**level to maintain a constant physical width.
        lvl_sigma = max(1.0, sigma * (2.0 ** lvl))
        ksize = int(2 * np.ceil(lvl_sigma * 4) + 1)
        if ksize % 2 == 0:
            ksize += 1
        a = cv2.GaussianBlur(cur, (ksize, ksize), lvl_sigma)
        alphas.append(a)
        cur = cv2.pyrDown(cur)
    return alphas


def _multiband_blend(
    observed_u8: np.ndarray,
    mirrored_u8: np.ndarray,
    observed_mask: np.ndarray,
    mirrored_mask: np.ndarray,
    atlas_valid: np.ndarray,
    levels: int,
    sigma: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Burt-Adelson multi-band blend.

    observed_u8 / mirrored_u8 : (S,S,3) BGR
    observed_mask: 1.0 where the observed side wins (real pixels)
    mirrored_mask: 1.0 where the mirrored side covers the atlas
    Both masks live on the (S,S) atlas. The blend wins for observed texels
    wherever observed_mask==1, mirrored texels wherever mirrored_mask==1 and
    observed_mask==0, and 0 (caller's background fill) elsewhere.

    Returns (blended uint8 BGR, synthetic_mask bool).
    """
    obs_f = observed_u8.astype(np.float32)
    mir_f = mirrored_u8.astype(np.float32)
    # Compositing alpha: 1 means "mirrored wins". Inside bilateral overlap the
    # mirror is replaced by observed (observed pulls alpha->0); inside the
    # hidden half fed by mirror alpha->1; outside, alpha->0 (background will be
    # filled by the caller). The pyramid smooths the transition band.
    raw_alpha = (
        mirrored_mask.astype(np.float32)
        * (1.0 - observed_mask.astype(np.float32))
    )
    raw_alpha[~atlas_valid] = 0.0
    alphas = _gaussian_alpha_pyramid(raw_alpha, levels, sigma)
    obs_pyr = _laplacian_pyramid(obs_f, levels)
    mir_pyr = _laplacian_pyramid(mir_f, levels)

    blended_pyr: list[np.ndarray] = []
    for lvl in range(levels):
        a = alphas[lvl]
        # resize a to this level's resolution if needed
        lo, lm = obs_pyr[lvl], mir_pyr[lvl]
        if a.shape[:2] != lo.shape[:2]:
            a = cv2.resize(a, (lo.shape[1], lo.shape[0]), interpolation=cv2.INTER_LINEAR)
        blended_pyr.append(lo * (1.0 - a[..., None]) + lm * a[..., None])
    # Top residual: pick from whichever source is valid; low frequencies average
    # smoothly via alpha continuity.
    top_a = alphas[-1]
    if top_a.shape[:2] != obs_pyr[-1].shape[:2]:
        top_a = cv2.resize(top_a, (obs_pyr[-1].shape[1], obs_pyr[-1].shape[0]),
                           interpolation=cv2.INTER_LINEAR)
    top = obs_pyr[-1] * (1.0 - top_a[..., None]) + mir_pyr[-1] * top_a[..., None]

    # Collapse pyramid
    out = top
    for lvl in range(levels - 1, -1, -1):
        out = cv2.pyrUp(out, dstsize=(blended_pyr[lvl].shape[1], blended_pyr[lvl].shape[0]))
        out = out + blended_pyr[lvl]
    out = np.clip(out, 0, 255).astype(np.uint8)

    # synthetic mask: anywhere the mirror won
    synthetic = (raw_alpha > 0.5) & atlas_valid
    return out, synthetic


def _inpaint_holes(
    texture_u8: np.ndarray,
    holes: np.ndarray,
    valid: np.ndarray,
    known: np.ndarray,
    radius: float,
    method: str,
) -> np.ndarray:
    """Inpaint `holes` inside `valid` using NS or TELEA."""
    if not holes.any():
        return texture_u8
    u8 = texture_u8.copy()
    # Mark holes as the inpaint mask; everything else kept.
    mask = holes.astype(np.uint8) * 255
    flag = cv2.INPAINT_NS if method == "ns" else cv2.INPAINT_TELEA
    inp = cv2.inpaint(u8, mask, float(radius), flag)
    u8[holes] = inp[holes]
    u8[~valid] = texture_u8[~valid]
    return u8


def symmetric_fill(
    texture: np.ndarray,          # (S,S,3) float32 0..255, valid where observed
    observed: np.ndarray,         # (S,S) bool -- texels sampled from the real photo
    atlas_valid: np.ndarray,      # (S,S) bool -- texels covered by the UV atlas
    seam_feather_px: int = 24,    # legacy: single feather fallback (ignored when mb_blend_levels>=2)
    inpaint_remaining: bool = True,
    inpaint_radius: int = 4,
    background: str = "median_skin",
    color_match: bool = True,
    mb_blend_levels: int = 5,
    mb_blend_sigma: float = 0.36,
    mirror_strip_count: int = 5,
    inpaint_method: str = "ns",
) -> tuple[np.ndarray, np.ndarray]:
    """Return (morph_texture uint8, synthetic_mask bool)."""
    tex = np.asarray(texture, np.float32).copy()
    obs = np.asarray(observed, bool)
    valid = np.asarray(atlas_valid, bool)

    mir_tex = cv2.flip(tex, 1)
    mir_obs = cv2.flip(obs.astype(np.uint8), 1).astype(bool)

    obs_u8 = np.clip(tex, 0, 255).astype(np.uint8)
    mir_u8 = np.clip(mir_tex, 0, 255).astype(np.uint8)

    # Per-strip LAB photometric alignment of the mirrored half against observed
    if color_match:
        mir_u8 = _per_strip_lab_match(
            obs_u8, mir_u8, obs, mir_obs, mirror_strip_count,
        )
        mir_tex = mir_u8.astype(np.float32)

    synthetic = np.zeros_like(obs)

    if mb_blend_levels >= 2:
        # ---- Burt-Adelson multi-band blend ----
        out, mb_synthetic = _multiband_blend(
            obs_u8, mir_u8, obs, mir_obs, valid,
            levels=int(mb_blend_levels), sigma=float(mb_blend_sigma),
        )
        out = out.astype(np.float32)
        synthetic |= mb_synthetic
    else:
        # ---- legacy v3 fill + feather ----
        out = tex.copy()
        fill = valid & ~obs & mir_obs
        out[fill] = mir_tex[fill]
        synthetic |= fill
        if seam_feather_px > 0 and obs.any() and fill.any():
            dist_in = cv2.distanceTransform(obs.astype(np.uint8), cv2.DIST_L2, 3)
            band = (~obs) & mir_obs & (dist_in < float(seam_feather_px))
            if band.any():
                w = np.clip(dist_in[band] / float(seam_feather_px), 0.0, 1.0).astype(np.float32)
                out[band] = out[band] * (1.0 - w[:, None]) + mir_tex[band] * w[:, None]
                synthetic |= band

    # observed beats everything: byte-identical to analysis outside synthetic
    out[obs] = tex[obs]
    synthetic[obs] = False

    # ---- residual holes not covered by either side ----
    holes = valid & ~obs & ~mir_obs
    if holes.any():
        if inpaint_remaining:
            known = (valid & ~holes)
            out_u8 = np.clip(out, 0, 255).astype(np.uint8)
            u8 = _inpaint_holes(out_u8, holes, valid, known,
                                radius=float(inpaint_radius),
                                method=inpaint_method)
            out = u8.astype(np.float32)
        else:
            out[holes] = _median_skin_color(out, obs)
        synthetic |= holes

    # ---- atlas background (outside all triangles) ----
    bg = ~valid
    if bg.any():
        if background == "median_skin":
            out[bg] = _median_skin_color(out, obs | synthetic)
        else:
            out[bg] = 0.0

    return np.clip(out, 0, 255).astype(np.uint8), synthetic
