"""Morphing and texture blending provider for 3D pairs."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np

class Inspector3DProvider:
    def __init__(self, app6_root: Path) -> None:
        self.app6_root = app6_root

    def get_mesh_preview(self, record_id: str) -> dict[str, Any]:
        found_npz: Path | None = None
        for path in self.app6_root.rglob(f"{record_id}/reconstruction.npz"):
            found_npz = path
            break
        if not found_npz or not found_npz.is_file():
            rng = np.random.default_rng(abs(hash(record_id)) % (2**32))
            pts = rng.normal(0.0, 0.5, (1500, 3)).tolist()
            ldm106 = rng.normal(0.0, 0.4, (106, 3)).tolist()
            return {
                "record_id": record_id,
                "status": "synthetic_fallback",
                "vertices": pts,
                "landmarks_106": ldm106,
                "message": "Real reconstruction.npz not found; showing synthetic BFM fallback."
            }

        try:
            data = np.load(found_npz)
            verts = data.get("vertices", data.get("pts", np.zeros((10, 3))))
            ldm = data.get("landmarks_106", data.get("ldm106", np.zeros((106, 3))))
            return {
                "record_id": record_id,
                "status": "loaded",
                "vertices": verts[:6000].tolist() if isinstance(verts, np.ndarray) else [],
                "landmarks_106": ldm.tolist() if isinstance(ldm, np.ndarray) else [],
            }
        except Exception as e:
            return {"record_id": record_id, "status": "error", "error": str(e)}

    def get_pair_comparison(self, record_a: str, record_b: str) -> dict[str, Any]:
        res_a = self.get_mesh_preview(record_a)
        res_b = self.get_mesh_preview(record_b)

        ldm_a = np.array(res_a.get("landmarks_106", np.zeros((106, 3))))
        ldm_b = np.array(res_b.get("landmarks_106", np.zeros((106, 3))))

        if len(ldm_a) == 0 or len(ldm_b) == 0:
            distances = [0.0] * 106
        else:
            min_len = min(len(ldm_a), len(ldm_b))
            diffs = ldm_a[:min_len] - ldm_b[:min_len]
            distances = np.sqrt(np.sum(diffs**2, axis=1)).tolist()

        return {
            "record_a": record_a,
            "record_b": record_b,
            "mesh_a": res_a.get("vertices", []),
            "mesh_b": res_b.get("vertices", []),
            "landmarks_a": ldm_a.tolist(),
            "landmarks_b": ldm_b.tolist(),
            "landmark_distances": distances,
            "max_distance": float(max(distances)) if distances else 0.0,
        }
