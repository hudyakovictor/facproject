from __future__ import annotations
from dataclasses import dataclass
import cv2
import numpy as np
from .config import MorphCompletionConfig

@dataclass(frozen=True)
class CompletionResult:
    texture_bgr: np.ndarray
    mirror_mask: np.ndarray
    inpaint_mask: np.ndarray
    synthetic_mask: np.ndarray
    unresolved_mask: np.ndarray
    transition_alpha: np.ndarray
    transition_mask: np.ndarray
    trusted_real_core: np.ndarray


def _match_lab(source: np.ndarray, target: np.ndarray, sm: np.ndarray, tm: np.ndarray) -> np.ndarray:
    if sm.sum() < 128 or tm.sum() < 128:
        return source
    s = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(np.float32)
    t = cv2.cvtColor(target, cv2.COLOR_BGR2LAB).astype(np.float32)
    for c in range(3):
        sv, tv = s[..., c][sm], t[..., c][tm]
        s_med, t_med = np.median(sv), np.median(tv)
        s_mad = np.median(np.abs(sv - s_med)) + 1.0
        t_mad = np.median(np.abs(tv - t_med)) + 1.0
        s[..., c] = (s[..., c] - s_med) * np.clip(t_mad / s_mad, .65, 1.55) + t_med
    return cv2.cvtColor(np.clip(s, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def _soft_real_alpha(obs: np.ndarray, valid: np.ndarray,
                     real_px: int, hidden_px: int) -> np.ndarray:
    """Continuous real-texture weight around the observed/hidden boundary."""
    obs_u8 = obs.astype(np.uint8)
    d_real = cv2.distanceTransform(obs_u8, cv2.DIST_L2, 5)
    d_hidden = cv2.distanceTransform(1 - obs_u8, cv2.DIST_L2, 5)
    denom = float(max(1, int(real_px) + int(hidden_px)))
    t = np.clip((d_real - d_hidden + float(hidden_px)) / denom, 0.0, 1.0)
    # Smoothstep avoids visible opacity bands.
    alpha = t * t * (3.0 - 2.0 * t)
    alpha[~valid] = 0.0
    alpha[obs & (d_real >= float(max(0, real_px)))] = 1.0
    alpha[(~obs) & (d_hidden >= float(max(0, hidden_px)))] = 0.0
    return alpha.astype(np.float32)


def _extend_real_band(tex: np.ndarray, obs: np.ndarray, valid: np.ndarray,
                      steps: int) -> tuple[np.ndarray, np.ndarray]:
    """Extend real colours only far enough to support hidden-side feathering."""
    ext = tex.astype(np.float32).copy()
    known = obs.copy()
    kernel = np.ones((3, 3), np.uint8)
    for _ in range(max(0, int(steps))):
        new = cv2.dilate(known.astype(np.uint8), kernel).astype(bool) & ~known & valid
        if not new.any():
            break
        weight = cv2.boxFilter(known.astype(np.float32), -1, (3, 3), normalize=False)
        for c in range(3):
            values = cv2.boxFilter(ext[..., c] * known, -1, (3, 3), normalize=False)
            ext[..., c][new] = values[new] / np.maximum(weight[new], 1e-6)
        known |= new
    return ext, known


def complete_morph_texture(face_texture_bgr: np.ndarray, observed_face: np.ndarray,
                           atlas_valid: np.ndarray, cfg: MorphCompletionConfig) -> CompletionResult:
    tex = np.asarray(face_texture_bgr, np.uint8)
    obs = np.asarray(observed_face, bool)
    valid = np.asarray(atlas_valid, bool)
    out = np.zeros_like(tex)
    out[obs] = tex[obs]
    mirror_mask = np.zeros_like(obs)
    inpaint_mask = np.zeros_like(obs)
    mirrored = np.zeros_like(tex)
    mirrored_obs = np.zeros_like(obs)

    if cfg.enabled and cfg.method == "uv_mirror":
        mirrored = cv2.flip(tex, 1)
        mirrored_obs = cv2.flip(obs.astype(np.uint8), 1).astype(bool)
        if cfg.color_match:
            overlap = obs & mirrored_obs
            mirrored = _match_lab(mirrored, tex, mirrored_obs & valid, obs & valid) if overlap.sum() < 128 else _match_lab(mirrored, tex, overlap, overlap)
        mirror_mask = valid & ~obs & mirrored_obs
        out[mirror_mask] = mirrored[mirror_mask]

    holes = valid & ~obs & ~mirror_mask
    if holes.any() and cfg.enabled:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(holes.astype(np.uint8), 8)
        small = np.zeros_like(holes)
        for i in range(1, count):
            if int(stats[i, cv2.CC_STAT_AREA]) <= int(cfg.small_hole_max_area):
                small |= labels == i
        if small.any() and (obs | mirror_mask).any():
            inp = cv2.inpaint(out, small.astype(np.uint8) * 255, float(cfg.inpaint_radius), cv2.INPAINT_NS)
            out[small] = inp[small]
            inpaint_mask = small

    synthetic = mirror_mask | inpaint_mask
    unresolved = valid & ~obs & ~synthetic
    if cfg.background == "median" and (obs | synthetic).any():
        color = np.median(out[obs | synthetic], axis=0).astype(np.uint8)
        out[unresolved] = color
        synthetic |= unresolved
        unresolved = np.zeros_like(unresolved)
    # Build a continuous feather mask.  Real texels deep inside the observed
    # region remain exact; only a narrow visual transition band may mix.
    # Defensive defaults keep the module operational if macOS copied the new
    # completion.py over an older config.py during a partial folder replace.
    real_feather_px = int(getattr(cfg, "real_feather_px", 8))
    hidden_feather_px = int(getattr(cfg, "hidden_feather_px", 18))
    alpha = _soft_real_alpha(obs, valid, real_feather_px, hidden_feather_px)
    real_layer, real_layer_valid = _extend_real_band(
        tex, obs, valid, hidden_feather_px
    )
    synthetic_layer = mirrored.astype(np.float32)
    synthetic_layer_valid = mirrored_obs & valid
    synthetic_layer[inpaint_mask] = out[inpaint_mask]
    synthetic_layer_valid |= inpaint_mask
    transition = (
        valid
        & (alpha > 1e-4)
        & (alpha < 1.0 - 1e-4)
        & real_layer_valid
        & synthetic_layer_valid
    )
    if transition.any():
        a = alpha[..., None]
        blended = real_layer * a + synthetic_layer * (1.0 - a)
        out[transition] = np.clip(blended[transition], 0, 255).astype(np.uint8)

    trusted_core = obs & ~transition
    out[trusted_core] = tex[trusted_core]
    out[unresolved] = 0
    out[~valid] = 0
    return CompletionResult(
        out, mirror_mask, inpaint_mask, synthetic, unresolved,
        alpha, transition, trusted_core,
    )
