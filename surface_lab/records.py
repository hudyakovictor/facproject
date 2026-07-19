from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

@dataclass(frozen=True)
class Stage1Record:
    root: Path
    image_bgr: np.ndarray
    skin_mask: np.ndarray
    reconstruction: dict[str, np.ndarray]


def load_record(path: str | Path) -> Stage1Record:
    root = Path(path)
    image = cv2.imread(str(root / "original.jpg"), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(root / "original.jpg")
    mz = np.load(root / "face_mask.npz", allow_pickle=False)
    skin = np.asarray(mz["mask_original"], bool)
    rz = np.load(root / "reconstruction.npz", allow_pickle=False)
    recon = {k: rz[k] for k in rz.files}
    required = {"vertices_object_normalized", "vertices_camera", "vertices_image_224", "normals_posed", "triangles", "uv_coords", "trans_params"}
    missing = required - recon.keys()
    if missing:
        raise KeyError(f"missing reconstruction keys: {sorted(missing)}")
    return Stage1Record(root, image, skin, recon)


def to_original_image(points_224: np.ndarray, trans_params: np.ndarray) -> np.ndarray:
    """Inverse of the standard 3DDFA crop transform used by Stage 1."""
    p = np.asarray(points_224, np.float32).copy()
    p[:, 1] = 223.0 - p[:, 1]
    t = np.asarray(trans_params, np.float32).reshape(-1)
    if t.size < 5:
        raise ValueError("trans_params must contain width, height, scale, tx, ty")
    w0,h0,scale,cx,cy=map(float,t[:5])
    w=max(int(w0*scale),1); h=max(int(h0*scale),1)
    left=int(w/2-112+(cx-w0/2)*scale)
    up=int(h/2-112+(h0/2-cy)*scale)
    p[:,0]=(p[:,0]+left)/w*w0
    p[:,1]=(p[:,1]+up)/h*h0
    return p
