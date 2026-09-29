"""🧠 Модуль 3D-реконструкции на базе 3DDFA-V3 / RetinaFace (app8).

Выполняет детекцию лица, прямой проход нейросети реконструктора,
расчет BFM-сетки (35 709 вершин), Z-Buffer видимости, нормалей и
8 семантических каналов сегментации (seg_visible) для маски кожи.
"""
from __future__ import annotations
import argparse, contextlib, os, sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TDDFA = ROOT / "3ddfa_v3"

_MODELS_CACHE = None


@contextmanager
def _chdir(path: Path):
    """Python 3.10-compatible replacement for contextlib.chdir (3.11+)."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def ensure_assets() -> None:
    """Гарантирует наличие весов моделей в /tmp/assets и симлинков в 3ddfa_v3/assets."""
    import urllib.request
    tmp_assets = Path("/tmp/assets")
    tmp_assets.mkdir(parents=True, exist_ok=True)
    assets_dir = TDDFA / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    asset_files = [
        "face_model.npy",
        "net_recon.pth",
        "retinaface_resnet50_2020-07-20_old_torch.pth",
        "large_base_net.pth",
        "similarity_Lm3D_all.mat",
    ]
    base_url = "https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets"
    
    for f in asset_files:
        tmp_f = tmp_assets / f
        if not tmp_f.exists() or tmp_f.stat().st_size == 0:
            url = f"{base_url}/{f}?download=true"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp, open(tmp_f, "wb") as out:
                out.write(resp.read())
        dst = assets_dir / f
        if not dst.exists() and tmp_f.exists():
            try:
                os.symlink(str(tmp_f), str(dst))
            except Exception:
                pass


def get_models(device: str = "cpu"):
    """Ленивая загрузка моделей нейросети с кэшированием в памяти."""
    global _MODELS_CACHE
    if _MODELS_CACHE is not None:
        return _MODELS_CACHE
        
    ensure_assets()
    sys.path.insert(0, str(TDDFA))
    import torch

    # Совместимость со старым torch (<1.13) в .venv: там нет kwarg weights_only,
    # и он прокидывается в pickle.Unpickler -> "'weights_only' is an invalid keyword...".
    # Убираем его глобально перед импортом 3ddfa_v3.
    try:
        import inspect as _inspect
        if "weights_only" not in _inspect.signature(torch.load).parameters:
            _orig_torch_load = torch.load

            def _torch_load_compat(*args, **kwargs):
                kwargs.pop("weights_only", None)
                return _orig_torch_load(*args, **kwargs)

            torch.load = _torch_load_compat
    except Exception:
        pass

    from model.recon import face_model
    from face_box import face_box
    
    assets_dir = TDDFA / "assets"
    args = argparse.Namespace(
        inputpath="x", savepath="y", device=device, iscrop=True,
        detector="retinaface", ldm68=False, ldm106=False,
        ldm106_2d=False, ldm134=False, seg=False,
        seg_visible=True, useTex=False, extractTex=False,
        backbone="resnet50"
    )
    with _chdir(TDDFA):
        fm = face_model(args)
        det = face_box(args).detector
        basis_path = assets_dir / "face_model.npy"
        if not basis_path.exists() and Path("/tmp/assets/face_model.npy").exists():
            basis_path = Path("/tmp/assets/face_model.npy")
        basis = np.load(basis_path, allow_pickle=True).item()
        
    _MODELS_CACHE = (fm, det, basis)
    return _MODELS_CACHE


def get_mean_face_vertices(device: str = "cpu") -> np.ndarray:
    """Возвращает среднее лицо модели BFM (identity=0, expr=0): (35709, 3).

    Математически это ``fm.compute_shape(zeros(80), zeros(64))`` — то есть
    константный член ``u`` линейного 3DMM-разложения ``V = U + Aid·alpha_id +
    Aexp·alpha_exp``. Не зависит от входных фото, вычисляется один раз и
    кэшируется вместе с остальными моделями (``get_models``/``_MODELS_CACHE``).
    Используется для Identity Decomposition: ``delta = V_id − V_mean``.
    """
    fm, _det, _basis = get_models(device)
    mean_flat = fm.u.detach().cpu().numpy().astype(np.float32)
    return mean_flat.reshape(-1, 3)


def compute_shape_from_alpha(alpha_id: np.ndarray, device: str = "cpu") -> np.ndarray:
    """Строит (35709, 3) сетку identity-формы из произвольного 80-мерного
    вектора ``alpha_id`` (экспрессия принудительно нулевая), используя тот
    же кэшированный BFM-базис, что и обычная реконструкция.

    Линейность 3DMM (``V = U + Aid·alpha_id + Aexp·alpha_exp``) делает это
    дешёвой операцией без прогона нейросети — нужна только матрица базиса.
    Используется для Timeline-морфинга (Catmull-Rom по alpha_id, M8) и
    любых других задач, где alpha_id уже посчитан отдельно.
    """
    import torch
    fm, _det, _basis = get_models(device)
    alpha_t = torch.as_tensor(np.asarray(alpha_id, dtype=np.float32), device=fm.device).unsqueeze(0)
    exp_zero = torch.zeros(1, 64, device=fm.device)
    with torch.no_grad():
        v = fm.compute_shape(alpha_t, exp_zero)[0].cpu().numpy()
    return v


def reconstruct_image(img_path: Path, device: str = "cpu") -> dict[str, Any] | None:
    """Прямой проход реконструкции одного изображения."""
    import torch
    from PIL import Image
    from .geometry import classify_pose, full_pose_correction_matrix, apply_pose_correction
    from .visibility import compute_vertex_confidence
    from .expression_qc import compute_expression_qc
    from .imaging import decode_oriented_bgr

    fm, det, basis = get_models(device)

    # Единый с app6 декод (EXIF transpose через Pillow): пиксели реконструкции,
    # UV и текстурных метрик должны совпадать.
    try:
        bgr_oriented = decode_oriented_bgr(img_path)
    except Exception as e:
        print(f"Error opening image {img_path}: {e}")
        return None
    im = Image.fromarray(bgr_oriented[:, :, ::-1])  # BGR -> RGB PIL

    trans_p, im_t = det(im)
    if im_t is None:
        return None
        
    fm.input_img = im_t
    with torch.no_grad():
        d = fm.split_alpha(fm.net_recon(im_t))
        
        # Коэффициенты
        alpha_id = d["id"].cpu().numpy()[0]
        alpha_exp = d["exp"].cpu().numpy()[0]
        alpha_alb = d["alb"].cpu().numpy()[0] if "alb" in d else np.zeros(80, np.float32)
        alpha_sh = d["sh"].cpu().numpy()[0] if "sh" in d else np.zeros(27, np.float32)
        
        # 3D Формы сетки
        # 1. Сетка формы identity (без мимики)
        v_id = fm.compute_shape(d["id"], torch.zeros(1, 64, device=fm.device))[0].cpu().numpy()
        # 2. Полная сетка формы с мимикой
        shape_posed = fm.compute_shape(d["id"], d["exp"])
        v_obj = shape_posed[0].cpu().numpy()
        
        # Углы и матрицы
        rot = fm.compute_rotation(d["angle"])
        rot_mat = rot[0].cpu().numpy()
        angles_rad = d["angle"].cpu().numpy()[0]
        angles_deg = np.rad2deg(angles_rad)
        trans = d["trans"].cpu().numpy()[0]
        
        # Z-Buffer рендеринг и видимость
        v3d = fm.to_camera(fm.transform(shape_posed, rot, d["trans"]))
        v_cam = v3d[0].cpu().numpy()
        tex = torch.ones(1, shape_posed.shape[1], 3, device=fm.device)
        _, _, _, visr = fm.renderer(v3d.clone(), fm.tri, tex, visible_vertice=True)
        
        # 2D Проекция на исходное фото
        v2d_224 = fm.to_image(v3d)[0].cpu().numpy()
        
        # Нормали поверхности
        norm = (fm.compute_norm(shape_posed) @ rot)[0].cpu().numpy()
        
    from .geometry import to_original_image
    v2d_orig = to_original_image(v2d_224[:, :2], trans_p)
    front_facing = norm[:, 2] > 0
    
    n_vert = int(v_obj.shape[0])
    rend_vis = np.zeros(n_vert, bool)
    rend_vis[visr.cpu().numpy().astype(np.int64)] = True
    visible_mask = front_facing & rend_vis

    # 8 семантических каналов 3DDFA (224x224x8) — тот же источник маски кожи, что и в
    # app6 (app6.stage1.masks.build_mask_bundle). visible_idx строится ровно как в
    # 3ddfa_v3/model/recon.py: renderer-visible минус нормали от камеры.
    semantic_channels_224 = None
    try:
        with torch.no_grad():
            vis_idx = torch.zeros(n_vert, dtype=torch.int64, device=fm.device)
            vis_idx[visr.cpu().numpy().astype(np.int64)] = 1
            vis_idx[torch.as_tensor(norm[:, 2] < 0, dtype=torch.bool, device=fm.device)] = 0
            seg = np.asarray(fm.segmentation_visible(v3d.clone(), vis_idx), np.float32)
        if seg.shape == (224, 224, 8):
            semantic_channels_224 = seg
        else:
            print(f"Warning: unexpected seg_visible shape {seg.shape}; skin mask unavailable")
    except Exception as seg_exc:
        print(f"Warning: seg_visible inference failed: {seg_exc}")
    
    # Карта надежности видимости
    vertex_conf = compute_vertex_confidence(front_facing, rend_vis)
    
    # Хронологическое выравнивание позы (Pose Bins)
    yaw = float(angles_deg[1])
    pose_bin, canonical_yaw = classify_pose(yaw)
    target_pose_deg = [0.0, canonical_yaw, 0.0]
    r_corr = full_pose_correction_matrix(angles_deg, target_pose_deg)
    v_chronology = apply_pose_correction(v_id, r_corr)
    
    # Топологические ориентиры
    ldm134_idx = np.asarray(basis["ldm134"], dtype=np.int64)
    ldm106_idx = np.asarray(basis["ldm106"], dtype=np.int64)
    uv_coords = np.asarray(basis["uv_coords"], dtype=np.float32)
    triangles = np.asarray(fm.tri.cpu().numpy(), dtype=np.int64)
    
    # Геометрический QC мимики (с учетом позы и 3D-инвариантности)
    expr_qc = compute_expression_qc(v_obj[ldm106_idx], alpha_exp, yaw_deg=yaw)
    
    return {
        "alpha_id": alpha_id,
        "alpha_exp": alpha_exp,
        "alpha_alb": alpha_alb,
        "alpha_sh": alpha_sh,
        "angles_deg": angles_deg,
        "angles_rad": angles_rad,
        "pose_bin": pose_bin,
        "canonical_yaw": canonical_yaw,
        "rotation_matrix": rot_mat,
        "translation": trans,
        "trans_params": trans_p,
        "chronology_correction_matrix": r_corr,
        "vertices_object": v_obj,
        "vertices_camera": v_cam,
        "vertices_2d_orig": v2d_orig,
        "vertices_identity_only": v_id,
        "vertices_chronology_aligned": v_chronology,
        "normals_object": norm,
        "visible_mask": visible_mask,
        "front_facing": front_facing,
        "renderer_visible": rend_vis,
        "semantic_channels_224": semantic_channels_224,
        "vertex_confidence": vertex_conf,
        "ldm134_indices": ldm134_idx,
        "ldm106_indices": ldm106_idx,
        "uv_coords": uv_coords,
        "triangles": triangles,
        "expression_qc": expr_qc,
    }
