"""🎨 Модуль генерации визуальных и текстурных ассетов (app8):

1. Сохранение оригинала (`original.jpg`), кропа лица (`face_crop.jpg`) и превью (`thumb.jpg`);
2. Генерация канонической развертки текстуры (`uv_texture.png`) через `uv_module`;
3. Экспорт текстурированной 3D-модели (`mesh.obj` + `mesh.mtl`) для 3D-инспектора / Three.js;
4. Текстурный анализ кожи (`texture.json`) — ТОТ ЖЕ контракт измерения, что и в app6:
   маска кожи из семантических каналов 3DDFA (`app6.stage1.masks`), кроп и запись
   `face_mask.png` (`app6.stage1.assets.save_face_mask`), метрики схемы `texture-v1`
   (`app6.stage1.authenticity.build_texture_package`). При недоступной сегментации —
   fallback на маску по проекции видимой сетки (отметка в `source.mask_origin`).
"""
from __future__ import annotations
import json, shutil
from pathlib import Path
from typing import Any
import cv2
import numpy as np


def save_image_previews(source_img_path: Path,
                        bgr: np.ndarray,
                        bbox: list[int] | None,
                        out_dir: Path,
                        save_original: bool = True) -> dict[str, str]:
    """Сохраняет оригинал, кроп лица и превью."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    
    # 1. Оригинал
    if save_original:
        orig_name = f"original{source_img_path.suffix.lower()}"
        shutil.copy2(source_img_path, out_dir / orig_name)
        files["original"] = orig_name
        
    h, w = bgr.shape[:2]
    if bbox is not None and len(bbox) == 4:
        x, y, bw, bh = bbox
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w, x + bw), min(h, y + bh)
        face_crop = bgr[y1:y2, x1:x2]
    else:
        face_crop = bgr
        
    # 2. Face crop
    if face_crop.size > 0:
        crop_resized = cv2.resize(face_crop, (424, 500), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out_dir / "face_crop.jpg"), crop_resized, [cv2.IMWRITE_JPEG_QUALITY, 95])
        files["face_crop"] = "face_crop.jpg"
        
        # 3. Thumbnail (128x128)
        thumb = cv2.resize(face_crop, (128, 128), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(out_dir / "thumb.jpg"), thumb, [cv2.IMWRITE_JPEG_QUALITY, 90])
        files["thumbnail"] = "thumb.jpg"
        
    return files


def save_uv_texture_and_3d_mesh(bgr: np.ndarray,
                                recon_data: dict[str, Any],
                                out_dir: Path,
                                uv_size: int = 512,
                                save_mesh: bool = True) -> dict[str, str]:
    """Генерирует UV-развертку текстуры через uv_module и экспортирует mesh.obj + mesh.mtl."""
    from uv_module import HDUVConfig, HDUVTextureGenerator
    
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    
    v_cam = recon_data["vertices_camera"]
    v_obj = recon_data["vertices_object"]
    v_2d = recon_data["vertices_2d_orig"]
    triangles = recon_data["triangles"]
    uv_coords = recon_data["uv_coords"]
    normals = recon_data["normals_object"]
    alpha_sh = recon_data.get("alpha_sh", np.zeros(27, np.float32))
    
    recon_dict = {
        "vertices": v_cam,
        "vertices_3d": v_cam,
        "vertices_2d": v_2d,
        "triangles": triangles,
        "uv_coords": uv_coords,
        "normals_3d": recon_data.get("normals_posed", normals),
        "alpha_sh": alpha_sh,
        "skin_mask": None,
    }
    
    cfg = HDUVConfig(
        uv_size=int(uv_size),
        super_sample=2,
        enable_delighting=False,
        enable_symmetry_fill=True,
        enable_detail_boost=True,
        device="cpu",
    )
    
    try:
        gen = HDUVTextureGenerator(cfg)
        uv_render, uv_beauty, observed, confidence, aux = gen.generate(bgr, recon_dict)
        
        # Сохранение изображения UV-текстуры
        uv_png_path = out_dir / "uv_texture.png"
        cv2.imwrite(str(uv_png_path), uv_render)
        files["uv_texture"] = "uv_texture.png"
        
        # Сохранение бинарного uv.npz
        obs_bool = np.asarray(observed, bool)
        conf_f16 = np.asarray(confidence, np.float16)
        np.savez_compressed(
            out_dir / "uv.npz",
            texture_bgr=np.asarray(uv_render, np.uint8),
            confidence=conf_f16,
            observed_mask=obs_bool,
            uv_coords=np.asarray(uv_coords, np.float32),
        )
        files["uv_data"] = "uv.npz"
        
        # Экспорт 3D Wavefront OBJ + MTL (с привязкой к uv_texture.png)
        if save_mesh:
            obj_path = out_dir / "mesh.obj"
            mtl_path = out_dir / "mesh.mtl"
            _write_obj_with_mtl(obj_path, mtl_path, v_obj, normals, uv_coords, triangles, "uv_texture.png")
            files["mesh"] = "mesh.obj"
            files["mesh_material"] = "mesh.mtl"
            
    except Exception as exc:
        print(f"Warning: UV texture generation failed: {exc}")
        
    return files


def _write_obj_with_mtl(obj_path: Path,
                       mtl_path: Path,
                       vertices: np.ndarray,
                       normals: np.ndarray,
                       uv: np.ndarray,
                       triangles: np.ndarray,
                       texture_name: str = "uv_texture.png") -> None:
    """Записывает 3D-модель OBJ с координатами текстуры и материалом MTL."""
    mtl_content = (
        "newmtl face_material\n"
        "Ka 0.2 0.2 0.2\n"
        "Kd 0.8 0.8 0.8\n"
        "Ks 0.0 0.0 0.0\n"
        "illum 2\n"
        f"map_Kd {texture_name}\n"
    )
    mtl_path.write_text(mtl_content, encoding="utf-8")
    
    with open(obj_path, "w", encoding="utf-8") as f:
        f.write("mtllib mesh.mtl\nusemtl face_material\n")
        for x, y, z in vertices:
            f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for u, v in uv[:, :2]:
            f.write(f"vt {u:.6f} {v:.6f}\n")
        for nx, ny, nz in normals:
            f.write(f"vn {nx:.6f} {ny:.6f} {nz:.6f}\n")
        for tri in triangles:
            a, b, c = int(tri[0]) + 1, int(tri[1]) + 1, int(tri[2]) + 1
            f.write(f"f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n")


def rasterize_visible_face_mask(bgr: np.ndarray,
                                recon_data: dict[str, Any]) -> np.ndarray:
    """Растризует проекцию видимых треугольников BFM-сетки в бинарную маску лица.

    🚪 FALLBACK-путь: используется только когда семантическая сегментация кожи
    недоступна (нет `semantic_channels_224` или сбой обратной проекции маски).
    Эта маска — овал лица целиком (включая глаза, брови и губы), поэтому её
    метрики НЕ равны метрикам app6; основной путь — `semantic_skin_mask`.
    """
    v2d = np.asarray(recon_data["vertices_2d_orig"], np.float64)
    triangles = np.asarray(recon_data["triangles"], np.int64)
    visible = np.asarray(recon_data["visible_mask"], bool)
    h, w = bgr.shape[:2]

    mask = np.zeros((h, w), np.uint8)
    tri_visible = (visible[triangles[:, 0]] & visible[triangles[:, 1]] & visible[triangles[:, 2]])
    pts = np.rint(v2d[triangles[tri_visible]]).astype(np.int32)
    if pts.size:
        # LINE_8 без сглаживания: маска должна быть бинарной (альфа 0/255 в face_mask.png)
        try:
            # Один вызов на все треугольники: sequence of contours
            cv2.fillPoly(mask, [p for p in pts], 1, lineType=cv2.LINE_8)
        except Exception:  # pragma: no cover - запасной путь по одному треугольнику
            for tri in pts:
                cv2.fillConvexPoly(mask, tri, 1, lineType=cv2.LINE_8)
    return mask.astype(bool)


def build_face_mask_rgba(bgr: np.ndarray,
                         recon_data: dict[str, Any]) -> np.ndarray | None:
    """Готовит RGBA-кроп лица в оригинальном разрешении (контракт face_mask.png из app6).

    RGB = пиксели фото, альфа = маска видимой сетки (255 — лицо). Возвращает None,
    если маска слишком мала для метрического анализа.
    """
    mask = rasterize_visible_face_mask(bgr, recon_data)
    if int(mask.sum()) < 1500:  # порог app6.stage1.authenticity._load_face_mask_rgba
        return None

    ys, xs = np.where(mask)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    h, w = mask.shape[:2]
    px, py = int(round(bw * 0.15)), int(round(bh * 0.15))
    cx0, cy0 = max(0, x0 - px), max(0, y0 - py)
    cx1, cy1 = min(w, x1 + 1 + px), min(h, y1 + 1 + py)

    crop_rgb = bgr[cy0:cy1, cx0:cx1, ::-1]  # BGR → RGB
    alpha = np.where(mask[cy0:cy1, cx0:cx1], 255, 0).astype(np.uint8)
    return np.dstack([crop_rgb, alpha])


def semantic_skin_mask(recon_data: dict[str, Any], image_shape: tuple[int, ...]) -> np.ndarray | None:
    """Маска кожи из 8 семантических каналов 3DDFA — тем же кодом app6, что и в app6 Stage 1.

    Основной путь для текстурных метрик: `app6.stage1.masks.build_mask_bundle`
    (max(skin, nose) минус глаза/брови/губы, обратная проекция на оригинал).
    Возвращает `hard_original` (bool в разрешении оригинала) или None, если
    сегментация либо обратная проекция недоступны.
    """
    channels = recon_data.get("semantic_channels_224")
    if channels is None:
        return None
    try:
        from app6.stage1.masks import build_mask_bundle

        bundle = build_mask_bundle(np.asarray(channels), recon_data["trans_params"], image_shape)
    except Exception as exc:
        print(f"Warning: semantic skin mask unavailable: {exc}")
        return None
    return bundle.hard_original


def build_skin_texture(bgr: np.ndarray,
                       recon_data: dict[str, Any],
                       out_dir: Path,
                       photo_id: str | None = None) -> dict[str, Any]:
    """Пишет `face_mask.png` и `texture.json` — полностью как в app6 Stage 1.

    Контракт app6 воспроизводится вызовами того же кода, а не копией формул:
    - маска кожи: `app6.stage1.masks.build_mask_bundle` (семантические каналы 3DDFA),
      кроп и запись: `app6.stage1.assets.save_face_mask` + bbox по ldm106 с запасом
      `CROP_MARGIN` (0.25) — т.е. та же область измерения;
    - метрики: `app6.stage1.authenticity.build_texture_package` — схема `texture-v1`
      (6 quality-метрик `q_*` + v12-панель аутентичности, hard-stop по
      `model_quality_gate.json`).

    При недоступной сегментации включается fallback на проекции видимой сетки
    (`rasterize_visible_face_mask`): набор метрик тот же, но ROI шире, поэтому
    происхождение маски всегда фиксируется в `texture.json:source.mask_origin`.

    Raises:
        ValueError | OSError: маска непригодна или не записана — engine фиксирует
        это в `skin_failure.json` (как `failed_retryable` в app6).
    """
    from app6.stage1.authenticity import build_texture_package

    out_dir.mkdir(parents=True, exist_ok=True)
    face_mask_png = out_dir / "face_mask.png"
    mask_origin = "3ddfa_semantic_skin"

    hard = semantic_skin_mask(recon_data, bgr.shape)
    written = None
    if hard is not None and int(np.count_nonzero(hard)) > 0:
        try:
            # Приватные helper'ы app6 импортируются намеренно: другой кроп-конвейер
            # (свои поля и margin) дал бы расхождение конвенций между app6 и app8.
            from app6.stage1.assets import _bbox, save_face_mask

            ldm_idx = np.asarray(recon_data["ldm106_indices"], np.int64)
            ldm_pts = np.asarray(recon_data["vertices_2d_orig"], np.float32)[ldm_idx]
            written = save_face_mask(bgr, hard, _bbox(ldm_pts, bgr.shape), out_dir)
        except Exception as exc:
            print(f"Warning: semantic face_mask failed: {exc}")
            written = None

    if written is None:
        mask_origin = "bfm_mesh_visible_projection"
        rgba = build_face_mask_rgba(bgr, recon_data)
        if rgba is None:
            raise ValueError("face mask coverage too small for authenticity metrics")
        if not cv2.imwrite(str(face_mask_png), rgba[:, :, ::-1]):  # RGBA -> BGRA
            raise OSError(f"failed to write {face_mask_png}")

    summary = build_texture_package(
        out_dir=out_dir,
        face_mask_png=face_mask_png,
        photo_id=photo_id,
    )
    files = dict(summary.get("files") or {})
    files["face_mask"] = "face_mask.png"
    if written:
        files.update(written)  # face_mask.png + face_mask.npz в контракте app6
    summary["files"] = files

    texture_path = out_dir / "texture.json"
    payload = json.loads(texture_path.read_text(encoding="utf-8"))
    payload.setdefault("source", {})["mask_origin"] = mask_origin
    texture_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
