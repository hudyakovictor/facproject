"""Official 3DDFA-V3 MobileNet checkpoint and basis, CPU-only inference.
The network and 3DMM equations match vendor/model/recon.py. No fake mesh fallback.
The lightweight YuNet detector supplies five landmarks; POS alignment follows upstream.
"""

import sys, time, threading
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageOps
from scipy.io import loadmat
from server.config import ROOT, ASSETS, CONFIG, digest, read_yaml

VERSION = "3ddfa-v3-mbnet-e153858-pos-yunet-v3-exif"
MODEL_HASH = "435f33e6fc93f3c0857538ffc5024d29bd6d09f98391d9be55f2d32b23cc2604"
# Bump whenever photo_uv changes: atlases are cached per (photo, baker).
UV_BAKER = "uv-baker-v2"
_lock = threading.RLock()
_instance = None
_basis = None


def availability():
    needed = [
        "face_model.npy",
        "net_recon_mbnet.pth",
        "similarity_Lm3D_all.mat",
        "face_detection_yunet_2023mar.onnx",
    ]
    missing = [f for f in needed if not (ASSETS / f).exists()]
    return {
        "id": "3ddfa_v3",
        "title": "3DDFA_V3",
        "available": not missing,
        "backbone": "MobileNet-V3",
        "device": "CPU",
        "version": VERSION,
        "reason": ("Нет ассетов: " + ", ".join(missing)) if missing else None,
    }


def get_model():
    global _instance
    with _lock:
        if _instance is None:
            _instance = TDDFA()
    return _instance


def basis_arrays():
    """3DMM basis from face_model.npy without loading torch or the network.

    Projection and atlas baking only need the basis, so a missing or broken
    checkpoint must not disable the photo texture.
    """
    global _basis
    with _lock:
        if _basis is None:
            _basis = np.load(ASSETS / "face_model.npy", allow_pickle=True).item()
    return _basis


def pose_rotation(angles):
    """Pose rotation that multiplies row-vector points, as in vendor 3DDFA-V3.

    Upstream ``compute_rotation`` builds ``Rz @ Ry @ Rx`` and returns
    ``rot.permute(0, 2, 1)``; ``transform`` then computes ``face_shape @ rot``.
    For numpy row vectors the same pose is ``shape @ (Rz @ Ry @ Rx).T``.
    """
    x, y, z = np.asarray(angles, dtype=np.float64).reshape(-1)[:3]
    rx = np.array(
        [[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]]
    )
    ry = np.array(
        [[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]]
    )
    rz = np.array(
        [[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]]
    )
    return (rz @ ry @ rx).T


def project_to_photo(basis, alpha, width, height, alignment):
    """Project fitted BFM vertices into EXIF-oriented source-photo UVs.

    The camera is fixed by upstream 3DDFA (focal 1015, principal point 112,
    distance 10); alpha carries pose and translation. Returns (N, 2) in [0, 1].
    Projections outside the source frame stay outside so the baker drops them
    instead of smearing edge pixels across invalid triangles.
    """
    a = np.asarray(alpha, dtype=np.float64).reshape(-1)
    if a.size < 257:
        raise ValueError("alpha должен содержать 257 коэффициентов")
    width, height = int(width), int(height)
    if width < 2 or height < 2:
        raise ValueError("Исходное фото должно быть не меньше 2×2 пикселей")
    shape = (
        basis["u"].reshape(-1) + basis["id"] @ a[:80] + basis["exp"] @ a[80:144]
    ).reshape(-1, 3)
    camera = shape @ pose_rotation(a[224:227]) + a[254:257]
    depth = 10.0 - camera[:, 2]
    px = 1015.0 * camera[:, 0] / depth + 112.0
    py = 1015.0 * camera[:, 1] / depth + 112.0
    info = alignment if isinstance(alignment, dict) else {}
    crop = info.get("crop")
    if crop:
        # align() resized the photo by `scale`, then cropped a 224×224 window.
        left, top, scale = (float(v) for v in crop)
        if not np.isfinite([left, top, scale]).all() or scale <= 0:
            raise ValueError("Некорректная геометрия кропа в метаданных фото")
        nw = max(1, int(round(width * scale)))
        nh = max(1, int(round(height * scale)))
        # px/py are the aligned 224-px frame with y pointing up; PIL crops from
        # the top-left corner of the resized photo.
        ox = (px + left) * (width / nw)
        oy = (223.0 - py + top) * (height / nh)
    elif info.get("mode") == "manual_precropped":
        # align(precropped=True) resized the whole photo to 224×224.
        ox = px * (width / 224.0)
        oy = (223.0 - py) * (height / 224.0)
    else:
        raise ValueError(
            "В метаданных нет геометрии кропа — пересоберите признаки фото"
        )
    uv = np.stack([ox / (width - 1), 1 - oy / (height - 1)], axis=-1)
    return uv.astype("<f4")


class TDDFA:
    def __init__(self):
        if not availability()["available"]:
            raise RuntimeError(availability()["reason"])
        import torch

        self.torch = torch
        torch.set_num_threads(2)
        torch.manual_seed(42)
        path = str(ROOT / "vendor/3DDFA-V3")
        if path not in sys.path:
            sys.path.insert(0, path)
        from model.networks import define_net_recon_mobilenetv3

        self.net = define_net_recon_mobilenetv3("recon_mobilenetv3_large", False, None)
        state = torch.load(
            ASSETS / "net_recon_mbnet.pth", map_location="cpu", weights_only=True
        )
        self.net.load_state_dict(state["net_recon"])
        self.net.eval()
        self.basis = basis_arrays()
        self.mean = self.basis["u"].reshape(-1, 3).astype(np.float32)
        self.tri = np.asarray(self.basis["tri"], np.int32)
        self.ldm = {
            k: np.asarray(self.basis[k], np.int32).reshape(-1)
            for k in ["ldm68", "ldm106", "ldm134"]
        }
        lm = self.mean[self.ldm["ldm68"]]
        self.origin = (lm[36:42].mean(0) + lm[42:48].mean(0)) / 2
        self.scale = float(np.linalg.norm(lm[36:42].mean(0) - lm[42:48].mean(0)))
        std = loadmat(ASSETS / "similarity_Lm3D_all.mat")["lm"]
        ix = np.array([31, 37, 40, 43, 46, 49, 55]) - 1
        self.lm3d = np.stack(
            [
                std[ix[0]],
                std[ix[[1, 2]]].mean(0),
                std[ix[[3, 4]]].mean(0),
                std[ix[5]],
                std[ix[6]],
            ]
        )[[1, 2, 0, 3, 4]]
        self.detector = cv2.FaceDetectorYN.create(
            str(ASSETS / "face_detection_yunet_2023mar.onnx"),
            "",
            (320, 320),
            0.7,
            0.3,
            5000,
        )

    def align(self, image, precropped=False):
        rgb = np.asarray(image.convert("RGB"))
        if precropped:
            return image.convert("RGB").resize((224, 224)), {
                "mode": "manual_precropped",
                "confidence": None,
            }
        h, w = rgb.shape[:2]
        factor = min(1.0, 800 / max(h, w))
        dw, dh = int(w * factor), int(h * factor)
        im = cv2.resize(rgb, (dw, dh))
        self.detector.setInputSize((dw, dh))
        _, faces = self.detector.detect(cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
        if faces is None or len(faces) == 0:
            raise ValueError(
                "Лицо не найдено. Для уже выровненного портрета включите «Готовый кроп 224×224». Профиль может требовать ручного кропа."
            )
        face = max(faces, key=lambda x: x[2] * x[3])
        points = face[4:14].reshape(5, 2).astype(float) / factor
        # Standard 3D landmarks are ordered image-left eye, image-right eye, nose, mouth-left, mouth-right.
        points = np.concatenate(
            [
                points[:2][np.argsort(points[:2, 0])],
                points[2:3],
                points[3:][np.argsort(points[3:, 0])],
            ]
        )
        points[:, 1] = h - 1 - points[:, 1]
        n = 5
        A = np.zeros((n * 2, 8))
        A[0::2, :3] = self.lm3d
        A[0::2, 3] = 1
        A[1::2, 4:7] = self.lm3d
        A[1::2, 7] = 1
        k = np.linalg.lstsq(A, points.reshape(-1, 1), rcond=None)[0]
        s = (np.linalg.norm(k[:3]) + np.linalg.norm(k[4:7])) / 2
        s = float(102.0 / s)
        tx, ty = float(k[3, 0]), float(k[7, 0])
        nw, nh = int(w * s), int(h * s)
        if nw > 12000 or nh > 12000:
            raise ValueError("Лицо слишком мало: загрузите более крупный кроп")
        left = int(nw / 2 - 112 + (tx - w / 2) * s)
        top = int(nh / 2 - 112 + (h / 2 - ty) * s)
        aligned = (
            image.convert("RGB")
            .resize((nw, nh), Image.Resampling.BICUBIC)
            .crop((left, top, left + 224, top + 224))
        )
        return aligned, {
            "mode": "yunet_pos5",
            "confidence": float(face[-1]),
            "detected_faces": len(faces),
            "bbox": (face[:4] / factor).tolist(),
            "crop": [left, top, s],
        }

    def reconstruct(self, alpha):
        a = np.asarray(alpha, np.float32).reshape(-1)
        shape = (
            self.basis["u"].reshape(-1)
            + self.basis["id"] @ a[:80]
            + self.basis["exp"] @ a[80:144]
        ).reshape(-1, 3)
        identity = (self.basis["u"].reshape(-1) + self.basis["id"] @ a[:80]).reshape(
            -1, 3
        )
        albedo = np.clip(
            (self.basis["u_alb"].reshape(-1) + self.basis["alb"] @ a[144:224]).reshape(
                -1, 3
            )
            / 255.0,
            0,
            1,
        )
        return {
            "vertices": ((shape - self.origin) / self.scale).astype(np.float32),
            "identity": ((identity - self.origin) / self.scale).astype(np.float32),
            "albedo": albedo.astype(np.float32),
        }

    def infer(self, path, precropped=False):
        start = time.perf_counter()
        with _lock:
            runtime = read_yaml(CONFIG / "runtime.yaml")
            self.torch.set_num_threads(int(runtime.get("torch_threads", 2)))
            self.detector.setScoreThreshold(
                float(runtime.get("detector_confidence", 0.7))
            )
            image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
            image.load()
            aligned, alignment = self.align(image, precropped)
            x = np.array(aligned, dtype=np.float32) / 255.0
            t = self.torch.from_numpy(x.transpose(2, 0, 1).copy()).unsqueeze(0)
            with self.torch.inference_mode():
                alpha = self.net(t).numpy()[0].copy()
            result = self.reconstruct(alpha)
        angles = {
            "yaw": float(np.degrees(alpha[225])),
            "pitch": float(np.degrees(alpha[224])),
            "roll": float(np.degrees(alpha[226])),
        }
        gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        meta = {
            "model": VERSION,
            "weights_sha256": MODEL_HASH,
            "seed": 42,
            "angles": angles,
            "alignment": alignment,
            "seconds": round(time.perf_counter() - start, 3),
            "sharpness": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
            "units": "fixed_template_IOD",
            "runtime": runtime,
            "warning": "Реконструкция — оценка модели, не физическое измерение и не доказательство изменения личности.",
        }
        result["alpha"] = alpha
        return result, meta, aligned

    def topology(self):
        return {
            "triangles": self.tri.tolist(),
            "landmarks": {k: v.tolist() for k, v in self.ldm.items()},
            "mean": ((self.mean - self.origin) / self.scale).round(6).tolist(),
            "vertex_count": len(self.mean),
            "triangle_count": len(self.tri),
            "units": "template IOD",
            "version": VERSION,
            "uv": self.basis["uv_coords"][:, :2].round(7).tolist(),
        }

    def photo_uv(self, alpha, width, height, alignment):
        """Perspective project actual fitted BFM vertices back into EXIF-oriented source photo."""
        return project_to_photo(self.basis, alpha, width, height, alignment)
