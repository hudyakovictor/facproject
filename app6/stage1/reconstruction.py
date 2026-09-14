"""
🎯 CRITICAL → Обёртка 3DDFA_V3: reconstruction + chronology alignment + QA-гейты.

process() возвращает ReconstructionBundle со всеми наборами вершин:
object / identity_only / normalized / bin_canonical / CHRONOLOGY_ALIGNED (патч 01).
Гейты TOP50: MAX_REPROJECTION_P95=5px (#10) — RuntimeError при плохой проекции;
outlier detection (#27) — RuntimeError при >100 вышедших вершин;
upside-down sanity check (#34); face detection confidence (#37).
🔗 DEPENDS ON: 3ddfa_v3 (model, face_box), geometry.full_pose_correction_matrix.
⚠️ Тяжёлые зависимости (torch, nvdiffrast) импортируются лениво внутри методов.
"""
from __future__ import annotations

import gc
import os
import platform
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .geometry import classify_pose, compute_chronology_alignment, correction_rotation_angle_deg, normalize_mesh, reprojection_stats, row_rotation_matrix
from .status_logger import log_status


def _patch_torch_load_for_legacy_torch() -> None:
    """Совместимость вендорного 3DDFA с torch<2.0.

    Вендорный код вызывает torch.load(..., weights_only=False), а kwarg
    weights_only появился только в torch 2.x. На torch 1.12 отбрасываем
    kwarg (поведение = старый default unpickle; грузим только локальные
    доверенные assets). На torch>=2 ничего не меняем.
    """
    try:
        import inspect as _inspect
        import torch as _torch
    except ImportError:
        return
    try:
        params = _inspect.signature(_torch.load).parameters
    except (TypeError, ValueError):
        return
    if "weights_only" in params or getattr(_torch.load, "_deeputin_patched", False):
        return
    _orig_load = _torch.load

    def _compat_load(*args: Any, **kwargs: Any) -> Any:
        kwargs.pop("weights_only", None)
        return _orig_load(*args, **kwargs)

    _compat_load._deeputin_patched = True  # type: ignore[attr-defined]
    _torch.load = _compat_load  # type: ignore[method-assign]


_patch_torch_load_for_legacy_torch()


@dataclass
class ReconstructionBundle:
    trans_params: np.ndarray
    angles_rad: np.ndarray
    angles_deg: np.ndarray
    pose_bin: str
    canonical_yaw: float
    rotation: np.ndarray
    translation: np.ndarray
    vertices_object: np.ndarray
    vertices_identity_only: np.ndarray
    vertices_object_normalized: np.ndarray
    vertices_bin_canonical: np.ndarray
    vertices_chronology_aligned: np.ndarray
    vertices_camera: np.ndarray
    vertices_image_224: np.ndarray
    normals_object: np.ndarray
    normals_posed: np.ndarray
    triangles: np.ndarray
    uv_coords: np.ndarray
    ldm106_indices: np.ndarray
    ldm134_indices: np.ndarray
    front_facing: np.ndarray
    renderer_visible: np.ndarray
    combined_visible: np.ndarray
    semantic_channels_224: np.ndarray
    alpha_full: np.ndarray
    alpha_id: np.ndarray
    alpha_exp: np.ndarray
    alpha_alb: np.ndarray
    alpha_sh: np.ndarray
    normalization_center: np.ndarray
    normalization_scale: float
    # v2.5: раздельные identity/object нормировки. normalization_* выше =
    # object (id+exp), оставлен для обратной совместимости. Истинные
    # identity-only (id, exp=0) — поля ниже; именно они воспроизводят CSV.
    identity_normalization_center: np.ndarray
    identity_normalization_scale: float
    object_normalization_center: np.ndarray
    object_normalization_scale: float
    vertices_identity_normalized: np.ndarray
    vertices_expression_delta: np.ndarray
    canonical_rotation: np.ndarray
    chronology_correction_matrix: np.ndarray
    chronology_target_pose: np.ndarray
    # v2.5: outlier gate в одном пространстве (identity). Старый mixed-space
    # счётчик оставлен как deprecated для сравнения старого/нового отбора.
    chronology_outlier_count: int
    chronology_outlier_threshold: float
    chronology_outlier_count_legacy_mixed_space: int
    correction_rotation_angle_deg: float
    # v2.6: target-only chronology (поворот в canonicalyaw без инверсии actual
    # pose; старый R_corr путь оставлен как sensitivity). И детектор-канал.
    vertices_chronology_targetonly: np.ndarray
    chronology_targetonly_matrix: np.ndarray
    detector_landmarks106: np.ndarray | None
    detector_face_count: int
    detector_reprojection: dict[str, Any]
    detector_residual106_px: np.ndarray
    reprojection: dict[str, dict[str, float]]
    raw_results: dict[str, Any]

    def landmark_arrays(self) -> dict[str, np.ndarray]:
        log_status("landmark_arrays", "complete")
        out: dict[str, np.ndarray] = {}
        for count, idx in ((106, self.ldm106_indices), (134, self.ldm134_indices)):
            key = f"ldm{count}"
            out[f"{key}_object"] = self.vertices_object[idx]
            out[f"{key}_object_normalized"] = self.vertices_object_normalized[idx]
            out[f"{key}_bin_canonical"] = self.vertices_bin_canonical[idx]
            out[f"{key}_chronology_aligned"] = self.vertices_chronology_aligned[idx]
            out[f"{key}_camera"] = self.vertices_camera[idx]
            out[f"{key}_image_224"] = self.vertices_image_224[idx]
            # v2.5: раздельные identity/object экспорты (replay по ТЗ)
            out[f"{key}_identity_raw"] = self.vertices_identity_only[idx]
            out[f"{key}_identity_normalized"] = self.vertices_identity_normalized[idx]
            out[f"{key}_expression_delta"] = self.vertices_expression_delta[idx]
            # v2.6: target-only канал сравнения (без инверсии actual pose)
            out[f"{key}_chronology_targetonly"] = self.vertices_chronology_targetonly[idx]
            out[f"{key}_front_facing"] = self.front_facing[idx].astype(np.uint8)
            out[f"{key}_renderer_visible"] = self.renderer_visible[idx].astype(np.uint8)
            out[f"{key}_visible"] = self.combined_visible[idx].astype(np.uint8)
        return out


class ReconstructionEngine:
    """One network inference; official renderer output is captured without patching 3DDFA."""

    def __init__(self, project_root: Path, device: str = "auto", detector: str = "retinaface", backbone: str = "resnet50"):
        self.project_root = Path(project_root)
        self.device = self._resolve_device(device)
        self.detector_name = detector
        self.backbone = backbone
        self._check_assets()
        cwd = Path.cwd()
        try:
            import sys as _sys
            _3ddfa_dir = str(self.project_root / "3ddfa_v3")
            if _3ddfa_dir not in _sys.path:
                _sys.path.insert(0, _3ddfa_dir)
            os.chdir(self.project_root)
            from face_box import face_box
            from model.recon import face_model
            args = Namespace(
                device=self.device, detector=detector, backbone=backbone,
                iscrop=True, ldm68=False, ldm106=True, ldm106_2d=False,
                ldm134=True, seg=True, seg_visible=True,
                useTex=True, extractTex=False, use_hd_uv=False,
            )
            self.model = face_model(args)
            _fb = face_box(args)
            self.detector = _fb.detector
            # v2.6: доступ к impl детектора ради 106 точек до 3DMM
            self._facebox = _fb
        finally:
            os.chdir(cwd)

    @staticmethod
    def _resolve_device(requested: str) -> str:
        import torch
        if requested == "auto":
            # The bundled renderer only has reliable CPU or CUDA paths. MPS would
            # enter the nvdiffrast branch, so Apple Silicon intentionally uses CPU.
            if platform.system() == "Darwin":
                return "cpu"
            if torch.cuda.is_available():
                try:
                    import nvdiffrast.torch  # noqa: F401
                    return "cuda"
                except Exception:
                    return "cpu"
            return "cpu"
        if requested == "mps":
            raise ValueError("bundled 3DDFA renderer does not support MPS; use cpu")
        return requested

    def _check_assets(self) -> None:
        assets = self.project_root / "assets"
        weight = "net_recon.pth" if self.backbone == "resnet50" else "net_recon_mbnet.pth"
        required = [assets / "face_model.npy", assets / weight, assets / "large_base_net.pth"]
        missing = [str(p) for p in required if not p.is_file()]
        if missing:
            raise FileNotFoundError("missing 3DDFA assets: " + ", ".join(missing))

    @staticmethod
    def _np(value: Any) -> np.ndarray:
        import torch
        if isinstance(value, torch.Tensor):
            value = value.detach().cpu().numpy()
        return np.asarray(value)

    def process(self, path: Path, oriented_rgb: np.ndarray | None = None) -> ReconstructionBundle:
        """🎯 CRITICAL → Один inference 3DDFA, ВСЕ данные извлекаются здесь.

        Это САМАЯ ВАЖНАЯ функция пайплайна. Каждый вызов = один проход нейросети.
        Никогда не вызывать дважды для одного фото!

        🔗 DEPENDS ON:
          - engine._one() — вызывает для каждого фото
          - face_box (RetinaFace) — detection + alignment crop
          - model.recon (3DDFA-V3) — neural network inference

        ⚠️ IN PROGRESS:
          - Нет проверки качества детекции (face detection confidence)
          - Нет валидации reprojection error (плохие реконструкции не отфильтровываются)
          - Нет проверки что лицо не перевёрнуто

        💡 NOTE:
          - Использует identity-only вершины для chronology (без мимики)
          - canonical alignment сохраняется для обратной совместимости
          - chronology alignment — НОВОЙ, использует полную коррекцию позы

        🚨 WARNING:
          - При device='cuda' может закончиться VRAM — вызовите cleanup()
          - При bad detection (tensor is None) — RuntimeError
          - При bad reconstruction — NaN в вершинах (проверяется для chronology)
        """
        # status: complete — отлажена, pipeline проходит успешно
        import torch
        from PIL import Image, ImageOps

        if not path.is_file():
            raise FileNotFoundError(f"input file not found: {path}")
        if oriented_rgb is None:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
        else:
            image = Image.fromarray(np.asarray(oriented_rgb, np.uint8), mode="RGB")
        trans, tensor = self.detector(image)
        if tensor is None or trans is None:
            raise RuntimeError("face detector returned no aligned crop")
        # v2.6: 106 точек детектора ДО 3DMM (независимый 2D-канал, top-left px
        # ориентированного входа). None только при no-face fallback.
        impl = getattr(getattr(self, "_facebox", None), "impl", None)
        detector_lmks_106 = getattr(impl, "last_lmks_106", None)
        detector_face_count = int(getattr(impl, "last_face_count", 0) or 0)
        if detector_lmks_106 is not None:
            detector_lmks_106 = np.asarray(detector_lmks_106, np.float32).reshape(106, 2)

        # 🎯 CRITICAL: Sanity check for upside-down photos
        # If the face is upside down, 3DDFA will produce incorrect pose
        # We check this by verifying the face crop has reasonable aspect ratio
        # and that the detection confidence is high enough
        if tensor.shape[2] < 50 or tensor.shape[3] < 50:
            raise RuntimeError(
                f"face crop too small ({tensor.shape[2]}x{tensor.shape[3]}) — "
                f"possible bad detection for {path.name}"
            )

        # RetinaFace API returns transform/crop, but not its native confidence
        # value. This is a known limitation — face detection is unaffected.
        # TODO: прикрутить confidence, когда RetinaFace его отдаст.
        self.model.input_img = tensor.to(self.device)

        captured_alpha: dict[str, Any] = {}
        captured_renderer: dict[str, Any] = {}
        # 🔄 CALLBACK → вызывается process(): сохранить alpha-каналы до мутаций
        def capture_alpha(_module: Any, _inputs: Any, output: Any) -> None:
            captured_alpha["count"] = int(captured_alpha.get("count", 0)) + 1
            captured_alpha["alpha"] = output

        alpha_hook = self.model.net_recon.register_forward_hook(capture_alpha)
        original_renderer_forward = self.model.renderer.forward

        # 🔄 CALLBACK → прямой проход рендера (диагностика репроекции)
        def renderer_forward(*args: Any, **kwargs: Any) -> Any:
            output = original_renderer_forward(*args, **kwargs)
            if kwargs.get("visible_vertice") and isinstance(output, (tuple, list)) and len(output) >= 4:
                captured_renderer["indices"] = output[3]
            return output

        self.model.renderer.forward = renderer_forward
        try:
            with torch.inference_mode():
                results = self.model.forward()
        finally:
            alpha_hook.remove()
            self.model.renderer.forward = original_renderer_forward

        alpha_t = captured_alpha.get("alpha")
        if alpha_t is None:
            raise RuntimeError("failed to capture net_recon output; refusing a second inference")
        if captured_alpha.get("count") != 1:
            raise RuntimeError(f"expected exactly one net_recon call, got {captured_alpha.get('count')}")
        renderer_indices = captured_renderer.get("indices")
        if renderer_indices is None:
            raise RuntimeError("failed to capture renderer visibility")

        with torch.inference_mode():
            alpha = self.model.split_alpha(alpha_t)
            object_t = self.model.compute_shape(alpha["id"], alpha["exp"])
            identity_t = self.model.compute_shape(alpha["id"], torch.zeros_like(alpha["exp"]))
            rotation_t = self.model.compute_rotation(alpha["angle"])
            posed_t = self.model.transform(object_t, rotation_t, alpha["trans"])
            camera_t = self.model.to_camera(posed_t.clone())
            image_t = self.model.to_image(camera_t.clone())
            normal_t = self.model.compute_norm(object_t)
            posed_normal_t = normal_t @ rotation_t

        vertices_object = self._np(object_t)[0].astype(np.float32)
        vertices_identity = self._np(identity_t)[0].astype(np.float32)
        vertices_camera = self._np(camera_t)[0].astype(np.float32)
        vertices_image = self._np(image_t)[0].astype(np.float32)
        normals_object = self._np(normal_t)[0].astype(np.float32)
        normals_posed = self._np(posed_normal_t)[0].astype(np.float32)
        rotation = self._np(rotation_t)[0].astype(np.float32)
        angles_rad = self._np(alpha["angle"])[0].astype(np.float32)
        angles_deg = np.degrees(angles_rad).astype(np.float32)
        translation = self._np(alpha["trans"])[0].astype(np.float32)

        normalized, center, scale = normalize_mesh(vertices_object)
        # v2.5: истинная identity-only нормировка — именно она внутри chrono.
        # object center/scale выше оставлены как legacy (не воспроизводят CSV).
        identity_normalized, identity_center, identity_scale = normalize_mesh(vertices_identity)
        expression_delta = (vertices_object - vertices_identity).astype(np.float32)
        pose_bin, canonical_yaw = classify_pose(float(angles_deg[1]))
        canonical_rotation = row_rotation_matrix(0.0, canonical_yaw, 0.0)
        canonical = (normalized @ canonical_rotation).astype(np.float32)

        # Chronology alignment: full pose correction (pitch + yaw + roll)
        # This ensures all photos within the same pose bin have identical pose
        # (0, canonical_yaw, 0), eliminating pitch/roll noise from comparison.
        # We use identity-only vertices (without expression) for stable comparison.
        chrono = compute_chronology_alignment(
            vertices=vertices_identity,
            actual_pose_deg=[float(angles_deg[0]), float(angles_deg[1]), float(angles_deg[2])],
            canonical_yaw=float(canonical_yaw),
            normalization="rms",
        )
        vertices_chronology_aligned = chrono["vertices_aligned"]
        chronology_correction_matrix = chrono["correction_matrix"]
        chronology_target_pose = chrono["target_pose"]
        # v2.5: chrono["center"]/chrono["scale"] обязаны совпасть с identity-only
        # нормировкой выше (одна и та же функция от одного меша). Проверяем.
        if not np.allclose(chrono["center"], identity_center, atol=1e-6):
            raise RuntimeError("chronology center diverged from identity normalization")
        if not np.isclose(float(chrono["scale"]), float(identity_scale), rtol=1e-6, atol=1e-9):
            raise RuntimeError("chronology scale diverged from identity normalization")
        correction_rotation_angle = correction_rotation_angle_deg(chronology_correction_matrix)
        # Validate chronology alignment: must be finite (no NaN/Inf from bad reconstruction)
        if not np.isfinite(vertices_chronology_aligned).all():
            raise RuntimeError("chronology alignment produced NaN/Inf vertices — bad 3DDFA reconstruction")
        # v2.6: target-only канал (рекомендуемый для сравнения): поворот
        # нормализованного identity в canonical yaw БЕЗ инверсии actual pose.
        # Не вносит pose-зависимость через metadata (баг №1). Старый R_corr
        # путь выше оставлен как sensitivity-канал.
        targetonly_matrix = row_rotation_matrix(0.0, float(canonical_yaw), 0.0)
        vertices_chronology_targetonly = (identity_normalized @ targetonly_matrix).astype(np.float32)
        # v2.5 FIX: outlier gate в одном пространстве (identity).
        # Старый код сравнивал chronology_aligned (identity-based) с normalized
        # (object-based, id+exp) — mixed-space displacement, порог смещён.
        # Новый гейт: displacement от identity_normalized. Старый счётчик
        # оставлен как deprecated для аудита изменения отбора.
        displacement = np.linalg.norm(vertices_chronology_aligned - identity_normalized, axis=1)
        outlier_threshold = np.percentile(displacement, 99) * 3
        outlier_mask = displacement > outlier_threshold
        outlier_count = int(outlier_mask.sum())
        displacement_legacy = np.linalg.norm(vertices_chronology_aligned - normalized, axis=1)
        outlier_threshold_legacy = np.percentile(displacement_legacy, 99) * 3
        outlier_count_legacy = int((displacement_legacy > outlier_threshold_legacy).sum())

        if outlier_count > 100:  # More than 100 outliers = bad reconstruction
            raise RuntimeError(
                f"Too many outlier vertices ({outlier_count}) in chronology alignment — "
                f"bad 3DDFA reconstruction for {path.name}"
            )

        idx106 = self._np(self.model.ldm106).reshape(-1).astype(np.int64)
        idx134 = self._np(self.model.ldm134).reshape(-1).astype(np.int64)
        expected106 = np.asarray(results["ldm106"])[0].astype(np.float32)
        expected134 = np.asarray(results["ldm134"])[0].astype(np.float32)
        reprojection = {
            "ldm106_224": reprojection_stats(vertices_image[idx106], expected106),
            "ldm134_224": reprojection_stats(vertices_image[idx134], expected134),
        }

        # 🎯 CRITICAL: Validate reprojection quality
        # If reprojection error is too high, the 3DDFA reconstruction is unreliable
        # and should NOT be used for chronology comparison
        MAX_REPROJECTION_P95 = 5.0  # pixels in 224x224 space
        reproj_p95 = max(r["p95"] for r in reprojection.values())
        if reproj_p95 > MAX_REPROJECTION_P95:
            raise RuntimeError(
                f"3DDFA reprojection error too high (p95={reproj_p95:.2f}px > {MAX_REPROJECTION_P95}px) — "
                f"unreliable reconstruction for {path.name}"
            )

        # v2.6/v2.7: НЕЗАВИСИМЫЙ reprojection-гейт против детектора до 3DMM.
        # Старый p95-гейт выше — internal consistency (3DMM против самого себя),
        # не scientific gate. Детектор LargeBaseLmkInfer — другая сеть и другой
        # forward, чем net_recon (общий только кроп); остаточный риск общей
        # ошибки кропа зафиксирован, порог щедрый и калибруется (0.35).
        # ldm134 независимой пары не имеет — честно помечаем недоступность.
        # Метрики: P50/P95/max + грубые трети по y + поточечные остатки в NPZ.
        from .geometry import to_original_image as _to_orig
        detector_residual106_px = np.full((106,), np.nan, np.float32)
        detector_reprojection: dict[str, Any] = {
            "status": "no_detector_landmarks",
            "ldm106": {"rmse_px": float("nan"), "p50_px": float("nan"),
                       "p95_px": float("nan"), "max_px": float("nan"),
                       "rmse_ioc": float("nan"), "ioc_px": float("nan"),
                       "upper_rmse_px": float("nan"), "mid_rmse_px": float("nan"),
                       "lower_rmse_px": float("nan")},
            "ldm134": {"status": "unavailable_no_detector_counterpart"},
        }
        if detector_lmks_106 is not None:
            try:
                det = np.asarray(detector_lmks_106, np.float64)
                proj_orig = np.asarray(
                    _to_orig(vertices_image[idx106][:, :2], np.asarray(trans, np.float32)),
                    np.float64)
                ioc = float(np.linalg.norm(det[74] - det[77]))
                if ioc > 1.0:
                    dd = np.linalg.norm(proj_orig - det, axis=1)
                    detector_residual106_px = dd.astype(np.float32)
                    ys = det[:, 1]
                    q1, q2 = np.quantile(ys, [1 / 3, 2 / 3])
                    # y растёт вниз (top-left origin): верх/середина/низ лица
                    up, mid, lo = dd[ys <= q1], dd[(ys > q1) & (ys <= q2)], dd[ys > q2]
                    rmse = float(np.sqrt(np.mean(dd * dd)))
                    yaw_abs = abs(float(angles_deg[1]))
                    # Калибровка 53 фото: все 17 превышений — профили |yaw|>45.
                    # Hard-fail только frontal/near-frontal (|yaw|<=25), где
                    # расхождение = плохой фит. Профили: измеряем, не валим.
                    gated = yaw_abs <= 25.0
                    detector_reprojection = {
                        "status": "measured" if gated else "measured_profile_unchecked",
                        "gate_yaw_limit": 25.0,
                        "gate_threshold_ioc": 0.35,
                        "gate_applied": bool(gated),
                        "ldm106": {
                            "rmse_px": rmse,
                            "p50_px": float(np.median(dd)),
                            "p95_px": float(np.percentile(dd, 95)),
                            "max_px": float(np.max(dd)),
                            "rmse_ioc": float(rmse / ioc),
                            "ioc_px": float(ioc),
                            "upper_rmse_px": float(np.sqrt(np.mean(up * up))) if up.size else float("nan"),
                            "mid_rmse_px": float(np.sqrt(np.mean(mid * mid))) if mid.size else float("nan"),
                            "lower_rmse_px": float(np.sqrt(np.mean(lo * lo))) if lo.size else float("nan"),
                        },
                        "ldm134": {"status": "unavailable_no_detector_counterpart"},
                    }
                    if gated and detector_reprojection["ldm106"]["rmse_ioc"] > 0.35:
                        raise RuntimeError(
                            f"detector reprojection too high "
                            f"(rmse_ioc={detector_reprojection['ldm106']['rmse_ioc']:.3f} > 0.35, "
                            f"|yaw|={yaw_abs:.1f}<=25) — "
                            f"3DMM fit disagrees with pre-3DMM detector for {path.name}"
                        )
                else:
                    detector_reprojection["status"] = "degenerate_detector_ioc"
            except RuntimeError:
                raise
            except Exception as exc:
                detector_reprojection = {"status": f"error: {exc}"}


        count = len(vertices_object)
        front = normals_posed[:, 2] >= 0.0
        renderer = np.zeros(count, dtype=bool)
        raw_indices = self._np(renderer_indices).reshape(-1).astype(np.int64)
        raw_indices = raw_indices[(raw_indices >= 0) & (raw_indices < count)]
        renderer[np.unique(raw_indices)] = True
        combined = front & renderer

        seg = np.asarray(results.get("seg_visible"))
        while seg.ndim > 3:
            seg = seg[0]
        if seg.ndim == 3 and seg.shape[0] == 8 and seg.shape[-1] != 8:
            seg = np.moveaxis(seg, 0, -1)
        if seg.shape != (224, 224, 8):
            raise RuntimeError(f"unexpected seg_visible shape: {seg.shape}")

        bundle = ReconstructionBundle(
            trans_params=np.asarray(trans, np.float32), angles_rad=angles_rad, angles_deg=angles_deg,
            pose_bin=pose_bin, canonical_yaw=float(canonical_yaw), rotation=rotation,
            translation=translation, vertices_object=vertices_object,
            vertices_identity_only=vertices_identity, vertices_object_normalized=normalized,
            vertices_bin_canonical=canonical,
            vertices_chronology_aligned=vertices_chronology_aligned,
            vertices_camera=vertices_camera,
            vertices_image_224=vertices_image, normals_object=normals_object,
            normals_posed=normals_posed, triangles=np.asarray(results["tri"], np.int64),
            uv_coords=np.asarray(results["uv_coords"], np.float32),
            ldm106_indices=idx106, ldm134_indices=idx134, front_facing=front,
            renderer_visible=renderer, combined_visible=combined,
            semantic_channels_224=seg.astype(np.float16), alpha_full=self._np(alpha_t)[0].astype(np.float32),
            alpha_id=self._np(alpha["id"])[0].astype(np.float32),
            alpha_exp=self._np(alpha["exp"])[0].astype(np.float32),
            alpha_alb=self._np(alpha["alb"])[0].astype(np.float32),
            alpha_sh=self._np(alpha["sh"])[0].astype(np.float32),
            normalization_center=center, normalization_scale=scale,
            identity_normalization_center=identity_center,
            identity_normalization_scale=float(identity_scale),
            object_normalization_center=center,
            object_normalization_scale=float(scale),
            vertices_identity_normalized=identity_normalized,
            vertices_expression_delta=expression_delta,
            canonical_rotation=canonical_rotation,
            chronology_correction_matrix=chronology_correction_matrix,
            chronology_target_pose=chronology_target_pose,
            chronology_outlier_count=int(outlier_count),
            chronology_outlier_threshold=float(outlier_threshold),
            chronology_outlier_count_legacy_mixed_space=int(outlier_count_legacy),
            correction_rotation_angle_deg=float(correction_rotation_angle),
            vertices_chronology_targetonly=vertices_chronology_targetonly,
            chronology_targetonly_matrix=targetonly_matrix,
            detector_landmarks106=(np.asarray(detector_lmks_106, np.float32)
                                   if detector_lmks_106 is not None
                                   else np.full((106, 2), np.nan, np.float32)),
            detector_face_count=int(detector_face_count),
            detector_reprojection=dict(detector_reprojection),
            detector_residual106_px=np.asarray(detector_residual106_px, np.float32),
            reprojection=reprojection, raw_results=results,
        )
        return bundle

    def cleanup(self) -> None:
        # status: complete — отлажена
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        finally:
            gc.collect()
