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

app = FastAPI(title="3D Face Morphing Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bgr_to_base64_jpeg(bgr: np.ndarray, quality: int = 90) -> str:
    _, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "3D Face Morphing API", "version": "1.0.0"}


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
        
        # 5. Формирование ответа
        response_payload = {
            "status": "success",
            "metadata": {
                "photo_a_yaw": float(res_a["angles_deg"][1]),
                "photo_b_yaw": float(res_b["angles_deg"][1]),
                "aligned_to": [0.0, 0.0, 0.0],
                "mean_3d_difference": round(mean_diff, 4),
                "max_3d_difference": round(max_diff, 4),
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
