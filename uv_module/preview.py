from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np


def provenance_preview(analysis_bgr: np.ndarray, morph_bgr: np.ndarray, observed: np.ndarray,
                       mirror_mask: np.ndarray, inpaint_mask: np.ndarray,
                       unresolved_mask: np.ndarray) -> np.ndarray:
    """Diagnostic preview: real image with explicit provenance overlay."""
    base = morph_bgr.copy()
    overlay = base.copy()
    overlay[mirror_mask] = (0, 165, 255)       # orange: mirrored
    overlay[inpaint_mask] = (0, 0, 255)        # red: inpaint
    overlay[unresolved_mask] = (255, 0, 255)   # magenta: unresolved
    overlay[observed] = (0, 190, 0)            # green: real
    return cv2.addWeighted(base, .58, overlay, .42, 0)


def save_uv_result(result, output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    preview = provenance_preview(result.analysis_bgr, result.morph_bgr,
        result.observed_skin_mask, result.mirror_mask, result.inpaint_mask, result.unresolved_mask)
    files = {
        "analysis": "uv_analysis.png", "morph": "uv_synthetic.png",
        "preview": "uv_preview.png", "confidence": "uv_confidence.png",
        "provenance": "uv_provenance.npz",
    }
    cv2.imwrite(str(out/files["analysis"]), result.analysis_bgr)
    cv2.imwrite(str(out/files["morph"]), result.morph_bgr)
    cv2.imwrite(str(out/files["preview"]), preview)
    cv2.imwrite(str(out/files["confidence"]), np.round(result.confidence * 255).astype(np.uint8))
    np.savez_compressed(out/files["provenance"],
        observed_skin_mask=result.observed_skin_mask,
        observed_face_mask=result.observed_face_mask,
        mirror_mask=result.mirror_mask, inpaint_mask=result.inpaint_mask,
        transition_alpha=result.transition_alpha.astype(np.float16),
        transition_mask=result.transition_mask,
        trusted_real_core=result.trusted_real_core,
        synthetic_mask=result.synthetic_mask, unresolved_mask=result.unresolved_mask,
        atlas_valid_mask=result.atlas_valid_mask, confidence=result.confidence.astype(np.float16),
        source_x=result.source_x.astype(np.float32), source_y=result.source_y.astype(np.float32),
        triangle_id=result.triangle_id.astype(np.int32), barycentric=result.barycentric.astype(np.float16))
    return files
