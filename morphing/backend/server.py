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

from app8.reconstruction import reconstruct_image, get_mean_face_vertices
from morphing.backend.aligner import align_identity_mesh_to_zero, align_vertices_to_zero
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

_ZONE_LABELS_RU: dict[str, str] = {
    "forehead": "лоб",
    "left_eye": "левый глаз",
    "right_eye": "правый глаз",
    "nose": "нос",
    "left_cheek": "левая скула/щека",
    "right_cheek": "правая скула/щека",
    "mouth_chin": "рот/подбородок",
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


def _zone_breakdown(v_a: np.ndarray, v_b: np.ndarray) -> dict[str, dict[str, float]]:
    """Для каждой из 7 приближённых зон считает mean/max евклидову дистанцию
    между двумя выровненными сетками + локальный z-score (сколько зона
    отклоняется от среднего разброса по ВСЕМ зонам этой конкретной пары).

    Важная оговорка (см. docs/30_MORPHING_ANALYSES.md, M13): это НЕ z-score
    относительно откалиброванного датасетного шума (σ same-day noise floor
    из stage2_v2) — такой калибровки в morphing пока нет. Это z-score внутри
    7 значений текущей пары, т.е. "насколько эта зона выделяется на фоне
    остальных зон этого же сравнения". Подписано явно в ключе ``z_local``.
    """
    means = {}
    maxes = {}
    for zone, (i0, i1) in _ZONE_INDICES.items():
        d = np.linalg.norm(v_a[i0:i1] - v_b[i0:i1], axis=1)
        means[zone] = float(np.mean(d))
        maxes[zone] = float(np.max(d))

    vals = np.array(list(means.values()), dtype=np.float64)
    mu, sigma = float(np.mean(vals)), float(np.std(vals) + 1e-9)

    out: dict[str, dict[str, float]] = {}
    for zone in _ZONE_INDICES:
        mean_d = means[zone]
        z_local = (mean_d - mu) / sigma
        score = round(max(0.0, min(100.0, (1.0 - mean_d / 0.15) * 100)), 1)
        out[zone] = {
            "mean_dist": round(mean_d, 6),
            "max_dist": round(maxes[zone], 6),
            "identity_score": score,
            "z_local": round(z_local, 2),
        }
    return out


def _top_diverging_zones(zone_breakdown: dict[str, dict[str, float]], n: int = 5) -> list[dict]:
    ranked = sorted(zone_breakdown.items(), key=lambda kv: kv[1]["mean_dist"], reverse=True)
    return [
        {"zone": zone, "mean_dist": vals["mean_dist"], "z_local": vals["z_local"]}
        for zone, vals in ranked[:n]
    ]


_MEAN_FACE_CACHE: np.ndarray | None = None


def _get_aligned_mean_face() -> np.ndarray:
    """Кэшированная (35709, 3) сетка среднего лица модели, выровненная тем
    же рецептом (центр + нормировка по max-радиусу), что и лица A/B."""
    global _MEAN_FACE_CACHE
    if _MEAN_FACE_CACHE is None:
        v_mean = get_mean_face_vertices(device="cpu")
        v_mean_aligned, _scale = align_vertices_to_zero(v_mean)
        _MEAN_FACE_CACHE = v_mean_aligned
    return _MEAN_FACE_CACHE


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

        # 5. Предрасчёт зональных метрик (forensic-like) — sidecar на случай,
        # если /api/forensic-score ещё не отработал.
        zone_scores: dict[str, float] = {
            zone: vals["mean_dist"] for zone, vals in _zone_breakdown(v_a_aligned, v_b_aligned).items()
        }

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


@app.get("/api/mean-face")
async def mean_face():
    """Возвращает среднее лицо BFM (35709 вершин), выровненное тем же
    рецептом, что и лица A/B. Не зависит от входных фото — фронтенд
    запрашивает это один раз и кэширует; используется для Identity
    Decomposition: δ_A = V_A − V_mean, δ_B = V_B − V_mean."""
    try:
        v_mean = _get_aligned_mean_face()
        return {"status": "ok", "vertices_mean": v_mean.flatten().tolist()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка получения среднего лица: {exc}")


@app.post("/api/similarity")
async def compute_similarity(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)):
    """Quantitative similarity: Euclidean distance по 35 709 вершинам,
    cosine similarity векторов формы alpha_id (80-мерных 3DMM-коэффициентов,
    а не «плоских» координат вершин — так это честная мера направления в
    пространстве формы), zone breakdown и top-5 наиболее расходящихся зон."""
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
        pct_above = float(np.mean(dists > 0.025) * 100.0)

        # Cosine similarity по вершинам (обратная совместимость со старыми клиентами)
        flat_a = v_a.flatten().astype(np.float64)
        flat_b = v_b.flatten().astype(np.float64)
        cosine_vertices = float(np.dot(flat_a, flat_b) / (np.linalg.norm(flat_a) * np.linalg.norm(flat_b) + 1e-9))

        # Cosine similarity по alpha_id — 80-мерный вектор формы 3DMM, честнее
        # отражает "направление" идентичности лица, чем плоские координаты вершин.
        alpha_a = np.asarray(res_a["alpha_id"], dtype=np.float64).flatten()
        alpha_b = np.asarray(res_b["alpha_id"], dtype=np.float64).flatten()
        cosine_alpha_id = float(
            np.dot(alpha_a, alpha_b) / (np.linalg.norm(alpha_a) * np.linalg.norm(alpha_b) + 1e-9)
        )

        morphability = round(max(0.0, min(100.0, (1.0 - mean_dist / 0.15) * 100)), 1)
        zones = _zone_breakdown(v_a, v_b)
        top_zones = _top_diverging_zones(zones, n=5)

        return {
            "status": "ok",
            "euclidean_mean": round(mean_dist, 6),
            "euclidean_max": round(max_dist, 6),
            "pct_vertices_above_threshold": round(pct_above, 2),
            "cosine_similarity": round(cosine_vertices, 6),
            "cosine_similarity_alpha_id": round(cosine_alpha_id, 6),
            "morphability_score": morphability,
            "zones": zones,
            "top_diverging_zones": top_zones,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка similarity: {exc}")


# Веса анатомических зон для глобального Forensic Identity Score.
# Нос и периорбитальная зона (глаза) считаются наиболее дискриминативными
# зонами лица в антропометрии/криминалистике и получают больший вес.
_FORENSIC_ZONE_WEIGHTS: dict[str, float] = {
    "forehead":    0.10,
    "left_eye":    0.18,
    "right_eye":   0.18,
    "nose":        0.22,
    "left_cheek":  0.10,
    "right_cheek": 0.10,
    "mouth_chin":  0.12,
}


@app.post("/api/forensic-score")
async def forensic_score(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)):
    """Forensic Identity Score: вероятность, что на двух фото один и тот же
    человек, с декомпозицией по 7 анатомическим зонам (веса из
    _FORENSIC_ZONE_WEIGHTS) и текстовым объяснением, какие зоны говорят "да"
    (похожи/идентичны), а какие "нет" (отличаются сильнее прочих)."""
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

        zones_result = _zone_breakdown(v_a, v_b)

        # Глобальная вероятность "один и тот же человек" — взвешенная сумма
        # зональных identity_score (0-100) по весам зон.
        probability_same_person = round(
            sum(zones_result[z]["identity_score"] * w for z, w in _FORENSIC_ZONE_WEIGHTS.items()),
            1,
        )

        # Текстовое объяснение по зонам: "да" (совпадает) / "нет" (отличается),
        # используя локальный z-score (z_local) внутри 7 зон этой пары —
        # см. docstring _zone_breakdown про то, что это НЕ откалиброванная
        # по датасету σ, а относительный разброс внутри самой пары.
        explanation: list[dict] = []
        for zone, vals in sorted(zones_result.items(), key=lambda kv: kv[1]["z_local"]):
            z = vals["z_local"]
            zone_ru = _ZONE_LABELS_RU.get(zone, zone)
            if z <= -0.5:
                verdict = "да"
                text = f"{zone_ru} совпадают (ниже среднего расхождения по паре)"
            elif z >= 1.0:
                verdict = "нет"
                text = f"{zone_ru} отличаются на {z:.1f}σ (заметно сильнее прочих зон)"
            else:
                verdict = "нейтрально"
                text = f"{zone_ru} — расхождение на уровне среднего по паре"
            explanation.append({"zone": zone, "verdict": verdict, "z_local": z, "text": text})

        return {
            "status": "ok",
            "global_forensic_score": probability_same_person,
            "probability_same_person": probability_same_person,
            "zones": zones_result,
            "zone_weights": _FORENSIC_ZONE_WEIGHTS,
            "explanation": explanation,
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
