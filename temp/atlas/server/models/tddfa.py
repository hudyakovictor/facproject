"""Official 3DDFA-V3 MobileNet checkpoint and basis, CPU-only inference.
The network and 3DMM equations match vendor/model/recon.py. No fake mesh fallback.
RetinaFace (ResNet-50) supplies five landmarks; POS alignment follows upstream.
"""

import sys, time, threading
import numpy as np
import cv2
from PIL import Image, ImageOps
from scipy.io import loadmat
from server.config import ASSETS, CONFIG, TDDFA_ROOT, read_yaml
from server.models.face_detect import RetinaFaceDetector

VERSION = "3ddfa-v3-mbnet-e153858-pos-retinaface-r1-exif"
MODEL_HASH = "435f33e6fc93f3c0857538ffc5024d29bd6d09f98391d9be55f2d32b23cc2604"
_lock = threading.RLock()
_instance = None

POSE_BINS = (
    ("left_profile", -95.0, -50.0, -70.0),
    ("left_deep", -50.0, -40.0, -45.0),
    ("left_mid", -40.0, -25.0, -32.5),
    ("left_light", -25.0, -10.0, -17.5),
    ("frontal", -10.0, 10.0, 0.0),
    ("right_light", 10.0, 25.0, 17.5),
    ("right_mid", 25.0, 40.0, 32.5),
    ("right_deep", 40.0, 50.0, 45.0),
    ("right_profile", 50.0, 95.0, 70.0),
)


def classify_pose_bin(yaw: float):
    y = float(yaw)
    if not np.isfinite(y):
        raise ValueError("yaw must be finite")
    for name, lo, hi, canonical in POSE_BINS:
        if lo <= y < hi:
            return name, canonical
    return ("right_profile" if y >= 0 else "left_profile"), float(np.clip(y, -70.0, 70.0))


def nearest_canonical_yaw(yaw: float):
    y = float(yaw)
    if not np.isfinite(y):
        raise ValueError("yaw must be finite")
    best = min(POSE_BINS, key=lambda row: abs(y - row[3]))
    return best[0], float(best[3])


def row_rotation_matrix(pitch_deg: float, yaw_deg: float, roll_deg: float) -> np.ndarray:
    p, y, r = np.radians([pitch_deg, yaw_deg, roll_deg])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]], np.float32)
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]], np.float32)
    rz = np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1]], np.float32)
    return (rz @ ry @ rx).T.astype(np.float32)


def full_pose_correction_matrix(actual_pose_deg, target_pose_deg) -> np.ndarray:
    p_act = np.asarray(actual_pose_deg, np.float32)
    p_tgt = np.asarray(target_pose_deg, np.float32)
    r_actual = row_rotation_matrix(float(p_act[0]), float(p_act[1]), float(p_act[2]))
    r_target = row_rotation_matrix(float(p_tgt[0]), float(p_tgt[1]), float(p_tgt[2]))
    return (r_actual.T @ r_target).astype(np.float32)


def apply_pose_correction(vertices: np.ndarray, r_corr: np.ndarray) -> np.ndarray:
    return (np.asarray(vertices, np.float32) @ np.asarray(r_corr, np.float32)).astype(np.float32)


def availability():
    needed = [
        "face_model.npy",
        "net_recon_mbnet.pth",
        "similarity_Lm3D_all.mat",
        "retinaface_resnet50_2020-07-20_old_torch.pth",
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


class TDDFA:
    def __init__(self):
        if not availability()["available"]:
            raise RuntimeError(availability()["reason"])
        import torch

        self.torch = torch
        torch.set_num_threads(2)
        torch.manual_seed(42)
        path = str(TDDFA_ROOT)
        if path not in sys.path:
            sys.path.insert(0, path)
        from model.networks import define_net_recon_mobilenetv3

        self.net = define_net_recon_mobilenetv3("recon_mobilenetv3_large", False, None)
        state = torch.load(
            ASSETS / "net_recon_mbnet.pth", map_location="cpu", weights_only=True
        )
        self.net.load_state_dict(state["net_recon"])
        self.net.eval()
        self.basis = np.load(ASSETS / "face_model.npy", allow_pickle=True).item()
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
        # YuNet не держит плотные кропы (лицо больше ~70% кадра), RetinaFace держит.
        self.detector = RetinaFaceDetector(ASSETS, TDDFA_ROOT)

    def align(self, image, precropped=False):
        rgb = np.asarray(image.convert("RGB"))
        if precropped:
            return image.convert("RGB").resize((224, 224)), {
                "mode": "manual_precropped",
                "confidence": None,
            }
        h, w = rgb.shape[:2]
        # RetinaFace сам нормирует длинную сторону до 512 и отдаёт координаты в
        # пикселях оригинала, отдельный resize с фактором как для YuNet не нужен.
        _, faces = self.detector.detect(rgb)
        if faces is None or len(faces) == 0:
            raise ValueError(
                "Лицо не найдено. Для уже выровненного портрета включите «Готовый кроп 224×224». Профиль может требовать ручного кропа."
            )
        face = max(faces, key=lambda x: x[2] * x[3])
        points = face[4:14].reshape(5, 2).astype(float)
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
            "mode": "retinaface_pos5",
            "detector": "retinaface-resnet50-512",
            "confidence": float(face[-1]),
            "detected_faces": len(faces),
            "bbox": face[:4].tolist(),
            "crop": [left, top, s],
        }

    def reconstruct(self, alpha, metric_layer=False):
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
        vertices = ((shape - self.origin) / self.scale).astype(np.float32)
        identity = ((identity - self.origin) / self.scale).astype(np.float32)
        angles = {
            "pitch": float(np.degrees(a[224])),
            "yaw": float(np.degrees(a[225])),
            "roll": float(np.degrees(a[226])),
        }
        landmarks_render = {
            f"landmarks_render_{name}": vertices[idx].astype(np.float32)
            for name, idx in self.ldm.items()
        }
        result = {
            "vertices": vertices,
            "identity": identity,
            "albedo": albedo.astype(np.float32),
            **landmarks_render,
        }
        if not metric_layer:
            return result
        # Экспериментально: сеть уже отдаёт канонический меш, доворот к yaw-центру
        # бина добавляет позу обратно и ухудшает разделение (reports/calibration-check.md).
        # Патч 03 (сверен с app6/app8): коррекция не применяется вообще. Вычитание
        # измеренных pitch/yaw/roll из mesh БЕЗ позы — двойной поворот (ratio к шумовому
        # полу 4.87 против 2.15 на фронтале), а доворот к canonical_yaw бина — общая
        # изометрия внутри бина и искусственная разница между бинами. Бин и r_corr
        # остаются метаданными, чтобы потребители не упали на отсутствующих ключах.
        pose_bin, canonical_yaw = classify_pose_bin(angles["yaw"])
        soft_bin, soft_canonical_yaw = nearest_canonical_yaw(angles["yaw"])
        target_pose = [0.0, 0.0, 0.0]
        r_corr = np.eye(3, dtype=np.float32)
        identity_metric = identity.astype(np.float32)
        result.update({
            "identity_metric": identity_metric.astype(np.float32),
            "metric_r_corr": r_corr.astype(np.float32),
            "metric_target_pose": np.asarray(target_pose, np.float32),
            "metric_pose_bin_index": np.asarray(
                [next(i for i, row in enumerate(POSE_BINS) if row[0] == pose_bin)],
                np.int16,
            ),
            "metric_canonical_yaw": np.asarray([canonical_yaw], np.float32),
            "metric_soft_canonical_yaw": np.asarray([soft_canonical_yaw], np.float32),
            **{
                f"landmarks_metric_{name}": identity_metric[idx].astype(np.float32)
                for name, idx in self.ldm.items()
            },
        })
        return result

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
            result = self.reconstruct(
                alpha, metric_layer=bool(runtime.get("metric_layer", False))
            )
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
        a = np.asarray(alpha, dtype=np.float64).reshape(-1)
        x, y, z = a[224:227]
        Rx = np.array(
            [[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]]
        )
        Ry = np.array(
            [[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]]
        )
        Rz = np.array(
            [[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]]
        )
        shape = (
            self.basis["u"].reshape(-1)
            + self.basis["id"] @ a[:80]
            + self.basis["exp"] @ a[80:144]
        ).reshape(-1, 3)
        # 3DDFA-V3's Recon.compute_rotation returns (Rz @ Ry @ Rx).T
        # because its row-vector transform is `shape @ rot + trans`.
        # Omitting this transpose projects the UV texture at the opposite yaw,
        # visibly shifting the face texture sideways on the reconstructed mesh.
        camera = shape @ (Rz @ Ry @ Rx).T + a[254:257]
        depth = 10.0 - camera[:, 2]
        px = 1015.0 * camera[:, 0] / depth + 112.0
        py = 1015.0 * camera[:, 1] / depth + 112.0
        crop = alignment.get("crop")
        if not crop:
            # For an explicitly precropped input, infer() resized the full source
            # directly to 224x224; map that model frame back to the source bounds.
            ox = px * (width / 224.0)
            oy = (223.0 - py) * (height / 224.0)
        else:
            left, top, scale = crop
            nw = max(1, int(round(width * scale)))
            nh = max(1, int(round(height * scale)))
            # PIL crop is top-left; model projection uses y-up coordinates.
            ox = (px + left) / (nw / width)
            oy = (223.0 - py + top) / (nh / height)
        if not np.isfinite(ox).all() or not np.isfinite(oy).all():
            raise ValueError("3DDFA returned non-finite photo projection")
        # Keep out-of-frame projections outside [0,1]. Clamping them to the
        # image border makes the UV baker smear edge pixels across invalid triangles.
        uv = np.stack(
            [
                ox / max(1, width - 1),
                1 - oy / max(1, height - 1),
            ],
            axis=-1,
        )
        return uv.astype("<f4")
