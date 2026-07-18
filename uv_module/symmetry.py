"""Symmetric completion of the UV texture for the MORPH variant (v3).

The hidden half of the face is filled with the horizontally mirrored visible
half (the BFM/3DDFA UV layout is left-right symmetric around u=0.5).

v3 upgrades vs v1/v2:
- LAB median/std color matching of the mirrored half against the observed half
  inside the bilateral overlap band BEFORE pasting (kills the luminance step
  across the seam when the two face halves are lit differently -- the typical
  case for the 4 side pose bins);
- distance-transform feather kept, TELEA for leftover holes kept;
- observed pixels remain byte-identical outside the feather band.

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


def _lab_match(source_u8: np.ndarray, target_u8: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Match source to target in LAB using median/std inside `mask`."""
    if np.count_nonzero(mask) < 64:
        return source_u8
    src = cv2.cvtColor(source_u8, cv2.COLOR_BGR2LAB).astype(np.float32)
    tgt = cv2.cvtColor(target_u8, cv2.COLOR_BGR2LAB).astype(np.float32)
    for ch in range(3):
        a = src[..., ch][mask]
        b = tgt[..., ch][mask]
        src[..., ch] = (src[..., ch] - np.median(a)) * (np.std(b) + 1e-5) / (np.std(a) + 1e-5) + np.median(b)
    return cv2.cvtColor(np.clip(src, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def symmetric_fill(
    texture: np.ndarray,          # (S,S,3) float32 0..255, valid where observed
    observed: np.ndarray,         # (S,S) bool -- texels sampled from the real photo
    atlas_valid: np.ndarray,      # (S,S) bool -- texels covered by the UV atlas
    seam_feather_px: int = 24,
    inpaint_remaining: bool = True,
    inpaint_radius: int = 4,
    background: str = "median_skin",
    color_match: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (morph_texture uint8, synthetic_mask bool)."""
    tex = np.asarray(texture, np.float32).copy()
    obs = np.asarray(observed, bool)
    valid = np.asarray(atlas_valid, bool)

    mir_tex = cv2.flip(tex, 1)
    mir_obs = cv2.flip(obs.astype(np.uint8), 1).astype(bool)

    # v3: photometric alignment of the mirrored half in the bilateral overlap
    overlap = obs & mir_obs
    if color_match:
        mir_u8 = np.clip(mir_tex, 0, 255).astype(np.uint8)
        obs_u8 = np.clip(tex, 0, 255).astype(np.uint8)
        mir_tex = _lab_match(mir_u8, obs_u8, overlap).astype(np.float32)

    out = tex.copy()
    synthetic = np.zeros_like(obs)

    # 1) hard fill: hidden texels that the mirrored side does cover
    fill = valid & ~obs & mir_obs
    out[fill] = mir_tex[fill]
    synthetic |= fill

    # 2) feather the seam only on the synthetic side of the seam; never write
    #    into the observed region.
    if seam_feather_px > 0 and obs.any() and fill.any():
        dist_in = cv2.distanceTransform(obs.astype(np.uint8), cv2.DIST_L2, 3)
        band = (~obs) & mir_obs & (dist_in < float(seam_feather_px))
        if band.any():
            w = np.clip(dist_in[band] / float(seam_feather_px), 0.0, 1.0).astype(np.float32)
            out[band] = out[band] * (1.0 - w[:, None]) + mir_tex[band] * w[:, None]

    # 3) holes not covered by either side
    holes = valid & ~obs & ~mir_obs
    if holes.any():
        if inpaint_remaining:
            u8 = np.clip(out, 0, 255).astype(np.uint8)
            known = (valid & ~holes).astype(np.uint8)
            u8[known == 0] = 0
            filled = cv2.inpaint(u8, holes.astype(np.uint8) * 255, float(inpaint_radius), cv2.INPAINT_TELEA)
            out[holes] = filled[holes].astype(np.float32)
        else:
            out[holes] = _median_skin_color(out, obs)
        synthetic |= holes

    # 4) atlas background (outside all triangles): neutral tone so mesh-edge
    #    bleeding during morph rendering stays inconspicuous.
    bg = ~valid
    if bg.any():
        if background == "median_skin":
            out[bg] = _median_skin_color(out, obs | synthetic)
        else:
            out[bg] = 0.0

    return np.clip(out, 0, 255).astype(np.uint8), synthetic
