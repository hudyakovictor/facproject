"""Bridge the existing app8/3DDFA_V3 reconstruction into UV quality inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from app8.geometry import to_original_image
from app8.imaging import decode_oriented_bgr

ROOT = Path(__file__).resolve().parents[1]
_PIPELINE_FINGERPRINT = None


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(part)
    return value.hexdigest()


def exif_pixel_matrix(orientation: int, width: int, height: int) -> np.ndarray:
    matrices = {
        1: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        2: [[-1, 0, width - 1], [0, 1, 0], [0, 0, 1]],
        3: [[-1, 0, width - 1], [0, -1, height - 1], [0, 0, 1]],
        4: [[1, 0, 0], [0, -1, height - 1], [0, 0, 1]],
        5: [[0, 1, 0], [1, 0, 0], [0, 0, 1]],
        6: [[0, -1, height - 1], [1, 0, 0], [0, 0, 1]],
        7: [[0, -1, height - 1], [-1, 0, width - 1], [0, 0, 1]],
        8: [[0, 1, 0], [-1, 0, width - 1], [0, 0, 1]],
    }
    return np.array(matrices.get(orientation, matrices[1]), dtype=float)


def reconstruct_for_uv(source: Path, cache: Path | None = None) -> tuple[np.ndarray, dict, dict]:
    source = Path(source).resolve()
    image = decode_oriented_bgr(source)
    with Image.open(source) as original:
        raw_width, raw_height = original.size
        orientation = int(original.getexif().get(274, 1))
    digest = sha256(source)
    source_files = [ROOT / "app8/reconstruction.py", ROOT / "app8/geometry.py", ROOT / "app8/imaging.py"]
    assets = ROOT / "3ddfa_v3/assets"
    source_files += [assets / name for name in ("face_model.npy", "net_recon.pth", "retinaface_resnet50_2020-07-20_old_torch.pth",
                                               "large_base_net.pth", "similarity_Lm3D_all.mat")]
    if any(not path.is_file() for path in source_files):
        raise FileNotFoundError("required pinned reconstruction assets are unavailable; no download is attempted")
    global _PIPELINE_FINGERPRINT
    state = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in source_files)
    if _PIPELINE_FINGERPRINT is None or _PIPELINE_FINGERPRINT[0] != state:
        _PIPELINE_FINGERPRINT = (state, {str(path.relative_to(ROOT)): sha256(path) for path in source_files})
    pipeline = _PIPELINE_FINGERPRINT[1]
    pipeline_id = hashlib.sha256(json.dumps(pipeline, sort_keys=True).encode()).hexdigest()
    path = Path(cache) / f"{digest[:24]}_{pipeline_id[:12]}.npz" if cache else None
    if path and path.is_file():
        with np.load(path, allow_pickle=False) as archive:
            recon = {key: archive[key] for key in archive.files if key != "metadata_json"}
            metadata = json.loads(str(archive["metadata_json"].item()))
        return image, recon, metadata
    import torch
    from app8.reconstruction import reconstruct_image
    torch.set_num_threads(2)
    result = reconstruct_image(source, device="cpu")
    if result is None:
        raise ValueError("3DDFA_V3 did not reconstruct this image")
    uv = np.asarray(result["uv_coords"], dtype=np.float32)
    if uv.shape[1] != 2 or uv.min() < -1e-6 or uv.max() > 1.000001:
        raise ValueError("UV coordinate units must be explicit; unexpected non-normalized layout")
    calibration = to_original_image(np.array([[0, 0], [1, 0], [0, 1]], dtype=np.float32), result["trans_params"])
    crop_to_original = np.eye(3)
    crop_to_original[:2] = np.column_stack((calibration[1] - calibration[0], calibration[2] - calibration[0], calibration[0]))
    camera = np.asarray(result["vertices_camera"], dtype=float)
    projection = np.asarray(result["vertices_2d_orig"], dtype=float)
    rays = np.column_stack((camera[:, 0] / camera[:, 2], camera[:, 1] / camera[:, 2], np.ones(len(camera))))
    crop_points = np.column_stack((projection, np.ones(len(projection)))) @ np.linalg.inv(crop_to_original).T
    intrinsic_crop = np.eye(3)
    intrinsic_crop[:2] = np.linalg.lstsq(rays, crop_points[:, :2], rcond=None)[0].T
    intrinsic_original = crop_to_original @ intrinsic_crop
    residual = float(np.max(np.abs(rays @ intrinsic_original[:2].T - projection)))
    if residual > 0.1:
        raise ValueError(f"camera/original-coordinate consistency error {residual}px")
    object_to_camera = np.linalg.lstsq(np.column_stack((result["vertices_object"], np.ones(len(camera)))), camera, rcond=None)[0].T
    recon = {"vertices": np.asarray(camera, dtype=np.float32), "vertices_3d": np.asarray(camera, dtype=np.float32),
             "vertices_object": result["vertices_object"], "vertices_2d": np.asarray(projection, dtype=np.float32),
             "triangles": result["triangles"], "uv_coords": uv, "normals_3d": result["normals_object"],
             "alpha_id": result["alpha_id"], "alpha_exp": result["alpha_exp"], "alpha_sh": result["alpha_sh"],
             "angles_deg": result["angles_deg"], "rotation_matrix": result["rotation_matrix"], "translation": result["translation"],
             "trans_params": result["trans_params"], "crop_to_original": crop_to_original,
             "original_to_crop": np.linalg.inv(crop_to_original), "intrinsic_crop": intrinsic_crop,
             "intrinsic_original": intrinsic_original, "object_to_camera": object_to_camera,
             "raw_to_oriented": exif_pixel_matrix(orientation, raw_width, raw_height),
             "ldm106_indices": result["ldm106_indices"], "ldm134_indices": result["ldm134_indices"]}
    metadata = {"source_path": str(source), "source_sha256": digest, "pipeline_id": pipeline_id, "pipeline_files_sha256": pipeline,
                "projection_space": "original", "original_coordinate_definition": "full-resolution EXIF-oriented source pixels",
                "exif_orientation": orientation, "raw_image_size": [raw_width, raw_height], "oriented_image_size": [image.shape[1], image.shape[0]],
                "camera_projection_residual_px": residual, "reconstruction_parameters": {"device": "cpu", "threads": 2, "backbone": "resnet50", "detector": "retinaface", "model_crop": 224}}
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **recon, metadata_json=json.dumps(metadata))
    return image, recon, metadata
