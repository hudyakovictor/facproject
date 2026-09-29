"""🚀 FastAPI Сервер 3D Face Morphing (app8 + uv_module)."""
from __future__ import annotations
import base64, io, sys
from pathlib import Path
from typing import Any
import cv2
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import numpy as np
from PIL import Image

# Добавляем корень проекта в путь
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app8.reconstruction import reconstruct_image
from morphing.backend.aligner import align_identity_mesh_to_zero
from morphing.backend.uv_extractor import extract_enhanced_uv
from morphing.backend.gif_renderer import generate_morph_gif
import tempfile
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="3D Face Morphing Server", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── BFM-совместимые индексы зон (приблизительные диапазоны по FLAME/BFM39k) ─
_ZONE_INDICES: dict[str, tuple[int, int]] = {
    "forehead":    (0,     3000),
    "left_eye":    (3000,  7000),
    "right_eye":   (7000,  11000),
    "nose":        (11000, 17000),
    "left_cheek":  (17000, 23000),
    "right_cheek": (23000, 29000),
    "mouth_chin":  (29000, 35709),
}


def _bgr_to_base64_jpeg(bgr: np.ndarray, quality: int = 90) -> str:
    _, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")


def _parse_vertices(data: Any) -> np.ndarray:
    """Конвертирует плоский список float → (N, 3) ndarray."""
    arr = np.array(data, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 3)
    return arr


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "3D Face Morphing API", "version": "2.0.0"}


@app.post("/api/morph-pair")
async def morph_pair(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)):
    """Принимает 2 фотографии, выполняет 3D-реконструкцию, выравнивает в (0,0,0) и генерирует HD UV-текстуры."""
    try:
        # Чтение входных байтов
        bytes_a = await photo_a.read()
        bytes_b = await photo_b.read()
        
        im_a = Image.open(io.BytesIO(bytes_a)).convert("RGB")
        im_b = Image.open(io.BytesIO(bytes_b)).convert("RGB")
        
        bgr_a = cv2.cvtColor(np.array(im_a), cv2.COLOR_RGB2BGR)
        bgr_b = cv2.cvtColor(np.array(im_b), cv2.COLOR_RGB2BGR)
        
        # 1. 3D Реконструкция через app8
        res_a = reconstruct_image(io.BytesIO(bytes_a), device="cpu")
        if res_a is None:
            raise HTTPException(status_code=400, detail="На фото A не обнаружено лицо")
            
        res_b = reconstruct_image(io.BytesIO(bytes_b), device="cpu")
        if res_b is None:
            raise HTTPException(status_code=400, detail="На фото B не обнаружено лицо")
            
        # 2. Строгое каноническое выравнивание в (0, 0, 0) градусов
        v_a_aligned, ldm106_a, scale_a = align_identity_mesh_to_zero(res_a)
        v_b_aligned, ldm106_b, scale_b = align_identity_mesh_to_zero(res_b)
        
        # 3. Генерация улучшенных HD UV-текстур через uv_module
        _, uv_b64_a = extract_enhanced_uv(bgr_a, res_a, uv_size=1024)
        _, uv_b64_b = extract_enhanced_uv(bgr_b, res_b, uv_size=1024)
        
        # 4. Расчет разницы форм для тепловой карты (Heatmap)
        diff_magnitudes = np.linalg.norm(v_a_aligned - v_b_aligned, axis=1)  # (35709,)
        mean_diff = float(np.mean(diff_magnitudes))
        max_diff = float(np.max(diff_magnitudes))

        # 5. Предрасчёт зональных метрик (forensic-like)
        zone_scores: dict[str, float] = {}
        for zone, (i0, i1) in _ZONE_INDICES.items():
            seg_a = v_a_aligned[i0:i1]
            seg_b = v_b_aligned[i0:i1]
            d = np.linalg.norm(seg_a - seg_b, axis=1)
            zone_scores[zone] = round(float(np.mean(d)), 6)

        # Morphability Score: нормируем mean_diff на эмпирический max 0.15
        morphability = round(max(0.0, min(100.0, (1.0 - mean_diff / 0.15) * 100)), 1)

        # Cosine similarity на уплощённых векторах
        flat_a = v_a_aligned.flatten().astype(np.float64)
        flat_b = v_b_aligned.flatten().astype(np.float64)
        norm_a = np.linalg.norm(flat_a)
        norm_b = np.linalg.norm(flat_b)
        cosine_sim = float(np.dot(flat_a, flat_b) / (norm_a * norm_b + 1e-9))
        
        # 6. Формирование ответа
        response_payload = {
            "status": "success",
            "metadata": {
                "photo_a_yaw": float(res_a["angles_deg"][1]),
                "photo_b_yaw": float(res_b["angles_deg"][1]),
                "aligned_to": [0.0, 0.0, 0.0],
                "mean_3d_difference": round(mean_diff, 4),
                "max_3d_difference": round(max_diff, 4),
                "morphability_score": morphability,
                "cosine_similarity": round(cosine_sim, 4),
                "zone_scores": zone_scores,
            },
            # Топология BFM
            "triangles": res_a["triangles"].flatten().tolist(),
            "uv_coords": res_a["uv_coords"].flatten().tolist(),
            # Выровненные в 0° вершины
            "vertices_a": v_a_aligned.flatten().tolist(),
            "vertices_b": v_b_aligned.flatten().tolist(),
            # 106 ориентиров
            "landmarks_106_a": ldm106_a.flatten().tolist(),
            "landmarks_106_b": ldm106_b.flatten().tolist(),
            # HD UV текстуры из uv_module
            "texture_a_base64": uv_b64_a,
            "texture_b_base64": uv_b64_b,
            # Превью фото
            "preview_a": _bgr_to_base64_jpeg(bgr_a, quality=85),
            "preview_b": _bgr_to_base64_jpeg(bgr_b, quality=85),
        }
        
        return JSONResponse(content=response_payload)
        
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки морфинга: {exc}")


@app.post("/api/similarity")
async def compute_similarity(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)):
    """Вычисляет Euclidean mean distance и cosine similarity 3D-форм двух лиц."""
    try:
        bytes_a = await photo_a.read()
        bytes_b = await photo_b.read()

        res_a = reconstruct_image(io.BytesIO(bytes_a), device="cpu")
        if res_a is None:
            raise HTTPException(status_code=400, detail="На фото A не обнаружено лицо")
        res_b = reconstruct_image(io.BytesIO(bytes_b), device="cpu")
        if res_b is None:
            raise HTTPException(status_code=400, detail="На фото B не обнаружено лицо")

        v_a, _, _ = align_identity_mesh_to_zero(res_a)
        v_b, _, _ = align_identity_mesh_to_zero(res_b)

        dists = np.linalg.norm(v_a - v_b, axis=1)
        mean_dist = float(np.mean(dists))
        max_dist = float(np.max(dists))

        flat_a = v_a.flatten().astype(np.float64)
        flat_b = v_b.flatten().astype(np.float64)
        cosine = float(np.dot(flat_a, flat_b) / (np.linalg.norm(flat_a) * np.linalg.norm(flat_b) + 1e-9))
        morphability = round(max(0.0, min(100.0, (1.0 - mean_dist / 0.15) * 100)), 1)

        return {
            "status": "ok",
            "euclidean_mean": round(mean_dist, 6),
            "euclidean_max": round(max_dist, 6),
            "cosine_similarity": round(cosine, 6),
            "morphability_score": morphability,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка similarity: {exc}")


@app.post("/api/forensic-score")
async def forensic_score(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)):
    """Зональный forensic identity score: отдельные метрики для 7 анатомических зон лица."""
    try:
        bytes_a = await photo_a.read()
        bytes_b = await photo_b.read()

        res_a = reconstruct_image(io.BytesIO(bytes_a), device="cpu")
        if res_a is None:
            raise HTTPException(status_code=400, detail="На фото A не обнаружено лицо")
        res_b = reconstruct_image(io.BytesIO(bytes_b), device="cpu")
        if res_b is None:
            raise HTTPException(status_code=400, detail="На фото B не обнаружено лицо")

        v_a, _, _ = align_identity_mesh_to_zero(res_a)
        v_b, _, _ = align_identity_mesh_to_zero(res_b)

        zones_result: dict[str, dict] = {}
        for zone, (i0, i1) in _ZONE_INDICES.items():
            seg_a = v_a[i0:i1]
            seg_b = v_b[i0:i1]
            d = np.linalg.norm(seg_a - seg_b, axis=1)
            mean_d = float(np.mean(d))
            max_d = float(np.max(d))
            # Нормируем на эмпирический max 0.15 → score 0–100
            score = round(max(0.0, min(100.0, (1.0 - mean_d / 0.15) * 100)), 1)
            zones_result[zone] = {
                "mean_dist": round(mean_d, 6),
                "max_dist": round(max_d, 6),
                "identity_score": score,
            }

        # Глобальный взвешенный score (нос и периорбитальная зона весят больше)
        weights = {
            "forehead": 0.10,
            "left_eye": 0.18,
            "right_eye": 0.18,
            "nose": 0.22,
            "left_cheek": 0.10,
            "right_cheek": 0.10,
            "mouth_chin": 0.12,
        }
        global_score = round(
            sum(zones_result[z]["identity_score"] * w for z, w in weights.items()), 1
        )

        return {
            "status": "ok",
            "global_forensic_score": global_score,
            "zones": zones_result,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка forensic score: {exc}")


@app.post("/api/export-gif")
async def export_gif(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)):
    """Генерирует и скачивает GIF-анимацию плавного 3D-морфинга (A -> B -> A)."""
    try:
        bytes_a = await photo_a.read()
        bytes_b = await photo_b.read()
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_a, \
             tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_b, \
             tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as f_gif:
            f_a.write(bytes_a)
            f_b.write(bytes_b)
            f_a.flush()
            f_b.flush()
            
            gif_path = generate_morph_gif(f_a.name, f_b.name, f_gif.name, num_frames=24, img_size=512, fps=12)
            return FileResponse(
                path=str(gif_path),
                filename="3d_face_morph.gif",
                media_type="image/gif"
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации GIF: {exc}")


# Статическая раздача фронтенда (если собран)
STATIC_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("morphing.backend.server:app", host="0.0.0.0", port=8000, reload=True)
