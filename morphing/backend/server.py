"""FastAPI service for canonical 3D face morphing and analysis.

The API keeps reconstruction separate from the numerical analysis layer.  This
makes the latter deterministic, testable and useful for the multi-face
sequence endpoint as well as the original A/B workflow.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app8.reconstruction import reconstruct_image
from morphing.backend.aligner import (
    MAXR_TO_RMS106,
    align_identity_mesh,
    group_pose_reference,
    pose_alignment_report,
)
from morphing.backend import identity as identity_module
from morphing.backend import form_metrics as form_metrics_module
from morphing.backend.pose_noise_model import pair_noise_reference
from morphing.backend.deformation import tps_deformed_target
from morphing.backend.extrapolation import MAX_EXTRAPOLATION_HORIZON_YEARS, extrapolate_shape
from morphing.backend.quality import evaluate_image, evaluate_mesh, quality_schema
from morphing.backend.batch import similarity_matrix as build_similarity_matrix
from morphing.backend.reporting import build_pair_report, build_timeline_report, render_report_html
from morphing.backend.analysis import (
    DEFAULT_ZONE_WEIGHTS,
    forensic_metrics,
    pca_projection,
    similarity_metrics,
    symmetry_metrics,
    temporal_drift_metrics,
    uv_difference,
    zone_ranges,
)
from morphing.backend.gif_renderer import generate_morph_gif
from morphing.backend.timeline import blend_vertices, timeline_metadata
from morphing.backend.uv_extractor import extract_enhanced_uv

# Backwards-compatible reference for clients that imported the old constant;
# actual calculations use topology-aware ranges from analysis.py.
_ZONE_INDICES = zone_ranges(35709)

app = FastAPI(title="3D Face Morphing Server", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bgr_to_base64_jpeg(bgr: np.ndarray, quality: int = 90) -> str:
    ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("не удалось закодировать preview")
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")


def _bgr_to_base64_png(bgr: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", bgr, [cv2.IMWRITE_PNG_COMPRESSION, 4])
    if not ok:
        raise RuntimeError("не удалось закодировать PNG")
    return "data:image/png;base64," + base64.b64encode(buf).decode("utf-8")


def _image_bytes_to_bgr(raw: bytes) -> np.ndarray:
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"некорректный файл изображения: {exc}") from exc
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def _registry() -> dict[str, Any]:
    """Load the project Stage 2 v2 registry without making it a hard dependency."""
    try:
        # The ``proj`` copy is the 83-parameter registry referenced by the
        # morphing brief.  Keep a fallback for installations that omit it.
        from app6.stage2_v2.proj.app6.stage2_v2.params import registry_json

        return registry_json()
    except Exception:
        try:
            from app6.stage2_v2.stage2_v2.params import registry_json

            return registry_json()
        except Exception:
            return {"schema": "unavailable", "groups": [], "params": []}


def _reconstruct(raw: bytes, label: str) -> dict[str, Any]:
    """Reconstruct, align and UV-project one uploaded face."""
    result = reconstruct_image(io.BytesIO(raw), device="cpu")
    if result is None:
        raise HTTPException(status_code=400, detail=f"На фото {label} не обнаружено лицо")
    bgr = _image_bytes_to_bgr(raw)
    vertices, landmarks, scale = align_identity_mesh(result)
    texture, texture_b64 = extract_enhanced_uv(bgr, result, uv_size=1024)
    return {
        "result": result,
        "bgr": bgr,
        "vertices": vertices,
        "landmarks": landmarks,
        "scale": scale,
        "texture": texture,
        "texture_b64": texture_b64,
    }


def _align_group(faces: list[dict[str, Any]]) -> dict[str, Any]:
    """Отчёт о ракурсах группы: общий бин, несовпадение ракурсов, разброс yaw.

    Доворачивать сетки не нужно: `vertices_identity_only` — форма в объектном
    пространстве 3DMM, поза уже вынесена в `angles_deg`, поэтому `_reconstruct`
    даёт каноническую сетку сразу (центр и RMS-масштаб по 106 ландмаркам, патч 04).
    См. docstring `morphing.backend.aligner`.
    """
    reference = group_pose_reference([face["result"] for face in faces])
    return pose_alignment_report([face["result"] for face in faces], reference)


def _heat_scales(noise: dict[str, Any]) -> dict[str, float]:
    """Опоры шкалы heatmap: пол «самого холодного цвета» и «полный красный».

    Без калибровки сохраняется историческая шкала 1/18 в прежних единицах (насыщение
    при 0.0556 долях max-радиуса сетки), пересчитанная в боевые доли RMS по 106
    ландмаркам, и нулевой пол. С калибровкой:
      full — типичное расхождение вершины между разными людьми в этом ракурсе, но не
             меньше двух шумовых пер-вершинных девиаций, чтобы «красный» означал
             различие лиц, а не шум конвейера;
      base — половина типичной пер-вершинной девиации шумовой пары: всё, что ниже,
             рисуется самым холодным цветом.
    """
    default_full = round(MAXR_TO_RMS106 / 18.0, 6)
    if not noise.get("available"):
        return {"heat_full_scale": default_full, "heat_base_scale": 0.0}
    noise_v = float(noise.get("noise_vertex_p95") or 0.0)
    signal_v = float(noise.get("signal_vertex_p95") or 0.0)
    if noise_v <= 0 and signal_v <= 0:
        return {"heat_full_scale": default_full, "heat_base_scale": 0.0}
    full = float(np.clip(max(signal_v, 2.0 * noise_v) if noise_v > 0 else signal_v, 0.02, 0.6))
    base = float(np.clip(0.5 * noise_v, 0.0, 0.8 * full))
    return {"heat_full_scale": round(full, 6), "heat_base_scale": round(base, 6)}


def _parameter_heatmap(mean_delta: float) -> list[dict[str, Any]]:
    """Expose the 83 Stage 2 parameters as a traceable diagnostic layer.

    Stage 2's registry contains analysis thresholds, not 3D landmark
    coefficients.  We therefore label this as a *mesh-derived signal* rather
    than pretending a dense mesh can measure an unrelated threshold.  It is a
    useful overview for analysts and keeps provenance explicit.
    """
    registry = _registry()
    # 0.15 — историческое насыщение proxy в прежних единицах (доля max-радиуса сетки),
    # пересчитано в доли RMS по 106 ландмаркам, чтобы `mean_delta` попадал в ту же шкалу.
    signal = float(np.clip(mean_delta / (0.15 * MAXR_TO_RMS106), 0.0, 1.0))
    items: list[dict[str, Any]] = []
    for spec in registry.get("params", []):
        items.append({
            "key": spec.get("key"),
            "title": spec.get("title", spec.get("key")),
            "group": spec.get("group", "unknown"),
            "impact": spec.get("impact", "medium"),
            "default": spec.get("default"),
            "signal": round(signal, 4),
            "observed": None,
            "source": "dense-mesh mean delta proxy; registry parameter has no direct mesh observation",
        })
    return items


def _pair_payload(face_a: dict[str, Any], face_b: dict[str, Any], deformation: str = "linear") -> dict[str, Any]:
    pose = _align_group([face_a, face_b])
    vertices_a = face_a["vertices"]
    vertices_b = face_b["vertices"]
    metrics = similarity_metrics(vertices_a, vertices_b)
    render_vertices_b = vertices_b
    deformation_info: dict[str, Any] = {"mode": "linear", "method": "direct vertex correspondence"}
    if deformation.lower() in {"tps", "smooth"}:
        render_vertices_b, tps_info = tps_deformed_target(
            vertices_a,
            face_a["landmarks"],
            face_b["landmarks"],
        )
        deformation_info = {"mode": "tps", **tps_info}
    elif deformation.lower() not in {"linear", "direct"}:
        raise ValueError("deformation must be linear or tps")
    forensic = forensic_metrics(vertices_a, vertices_b, weights=DEFAULT_ZONE_WEIGHTS)
    diff_texture = uv_difference(face_a["texture"], face_b["texture"])
    quality_a = evaluate_image(face_a["bgr"], label="photo_a")
    quality_b = evaluate_image(face_b["bgr"], label="photo_b")
    result_a, result_b = face_a["result"], face_b["result"]
    mesh_quality_a = evaluate_mesh(vertices_a, result_a["triangles"])
    mesh_quality_b = evaluate_mesh(vertices_b, result_b["triangles"])
    noise = pair_noise_reference(pose, metrics)
    return {
        "status": "success",
        "metadata": {
            "photo_a_yaw": float(result_a["angles_deg"][1]),
            "photo_b_yaw": float(result_b["angles_deg"][1]),
            "aligned_to": pose["aligned_to"],
            "pose": pose,
            "noise": noise,
            **_heat_scales(noise),
            "mean_3d_difference": metrics["euclidean_mean"],
            "max_3d_difference": metrics["euclidean_max"],
            "p95_3d_difference": metrics["p95_delta"],
            "euclidean_distance": metrics["euclidean_distance"],
            "cosine_similarity": metrics["cosine_similarity"],
            "morphability_score": metrics["morphability_score"],
            "zone_scores": {
                name: data["mean_delta"] for name, data in metrics["zones"].items()
            },
            "top_5_zones": metrics["top_5_zones"],
            "forensic_score": forensic["forensic_score"],
            "forensic_score_type": forensic["score_type"],
            "probability_same_person": None,
            "forensic_interpretation": forensic["interpretation"],
            "parameter_heatmap_source": "dense-mesh mean delta proxy",
            "deformation": deformation_info,
            "quality": {
                "photo_a": quality_a.to_dict(),
                "photo_b": quality_b.to_dict(),
                "mesh_a": mesh_quality_a.to_dict(),
                "mesh_b": mesh_quality_b.to_dict(),
            },
        },
        "triangles": result_a["triangles"].flatten().tolist(),
        "uv_coords": result_a["uv_coords"].flatten().tolist(),
        "vertices_a": face_a["vertices"].flatten().tolist(),
        "vertices_b": face_b["vertices"].flatten().tolist(),
        "vertices_b_render": render_vertices_b.flatten().tolist(),
        "landmarks_106_a": face_a["landmarks"].flatten().tolist(),
        "landmarks_106_b": face_b["landmarks"].flatten().tolist(),
        "texture_a_base64": face_a["texture_b64"],
        "texture_b_base64": face_b["texture_b64"],
        "texture_diff_base64": _bgr_to_base64_png(diff_texture),
        "preview_a": _bgr_to_base64_jpeg(face_a["bgr"], quality=85),
        "preview_b": _bgr_to_base64_jpeg(face_b["bgr"], quality=85),
        "sequence_vertices": [
            face_a["vertices"].flatten().tolist(),
            render_vertices_b.flatten().tolist(),
        ],
        "sequence_landmarks": [
            face_a["landmarks"].flatten().tolist(),
            face_b["landmarks"].flatten().tolist(),
        ],
        "sequence_textures": [face_a["texture_b64"], face_b["texture_b64"]],
        "parameter_heatmap": _parameter_heatmap(metrics["euclidean_mean"]),
    }


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "3D Face Morphing API", "version": "3.0.0"}


@app.get("/api/parameter-registry")
async def parameter_registry() -> dict[str, Any]:
    """Return the Stage 2 v2 registry used by the diagnostics panel."""
    registry = _registry()
    return {
        **registry,
        "count": len(registry.get("params", [])),
        "usage_note": "Registry metadata is shown alongside dense-mesh diagnostics; it is not a substitute for a calibrated Stage 2 run.",
    }


@app.get("/api/quality-schema")
async def get_quality_schema() -> dict[str, Any]:
    return quality_schema()


@app.post("/api/report-pair")
async def report_pair(
    photo_a: UploadFile = File(...),
    photo_b: UploadFile = File(...),
    format: str = Query(default="json"),
) -> Any:
    """Build a deterministic JSON or self-contained HTML analysis report."""
    try:
        if format not in {"json", "html"}:
            raise HTTPException(status_code=400, detail="format must be json or html")
        raw_a, raw_b = await photo_a.read(), await photo_b.read()
        face_a, face_b = _reconstruct(raw_a, "A"), _reconstruct(raw_b, "B")
        pose = _align_group([face_a, face_b])
        report = build_pair_report(
            face_a["vertices"],
            face_b["vertices"],
            labels=(photo_a.filename or "A", photo_b.filename or "B"),
            quality_a=evaluate_image(face_a["bgr"], label="photo_a"),
            quality_b=evaluate_image(face_b["bgr"], label="photo_b"),
            mesh_quality_a=evaluate_mesh(face_a["vertices"], face_a["result"]["triangles"]),
            mesh_quality_b=evaluate_mesh(face_b["vertices"], face_b["result"]["triangles"]),
            provenance={
                "endpoint": "/api/report-pair",
                "reconstruction": "app8",
                "alignment": "identity_object_space",
                "pose_bin": pose["canonical_bin"],
                "aligned_to": pose["aligned_to"],
                "pose_warning": pose["warning"],
                "input_sha256": [hashlib.sha256(raw_a).hexdigest(), hashlib.sha256(raw_b).hexdigest()],
            },
        )
        if format == "html":
            return HTMLResponse(content=render_report_html(report, "3D face morphing report"))
        return JSONResponse(content=report)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка формирования отчёта: {exc}") from exc


@app.post("/api/report-timeline")
async def report_timeline(
    photos: list[UploadFile] = File(...),
    metadata: str | None = Form(default=None),
    format: str = Query(default="json"),
) -> Any:
    """Create a dated or undated JSON/HTML report for 2–4 timeline photos."""
    if not 2 <= len(photos) <= 4:
        raise HTTPException(status_code=400, detail="timeline report принимает от 2 до 4 фотографий")
    if format not in {"json", "html"}:
        raise HTTPException(status_code=400, detail="format must be json or html")
    try:
        try:
            rows = json.loads(metadata) if metadata else [{} for _ in photos]
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"metadata должен быть JSON: {exc}") from exc
        if not isinstance(rows, list) or len(rows) != len(photos):
            raise HTTPException(status_code=400, detail="metadata должен содержать запись для каждого фото")
        raw_images = [await photo.read() for photo in photos]
        faces = [_reconstruct(raw, chr(65 + index)) for index, raw in enumerate(raw_images)]
        pose = _align_group(faces)
        labels = [str((row if isinstance(row, dict) else {}).get("label") or photo.filename or f"Face {index + 1}") for index, (row, photo) in enumerate(zip(rows, photos))]
        year_values = [(row if isinstance(row, dict) else {}).get("year") for row in rows]
        years = None
        if any(value not in (None, "") for value in year_values):
            try:
                years = [float(value) for value in year_values]
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="годы в metadata должны быть заданы для всех keyframes") from exc
            if not np.isfinite(years).all() or np.any(np.diff(years) <= 0):
                raise HTTPException(status_code=400, detail="годы должны быть конечными и строго возрастающими")
        quality_keyframes = []
        for index, face in enumerate(faces):
            quality_keyframes.append({
                "index": index,
                "label": labels[index],
                "year": years[index] if years else None,
                "photo": evaluate_image(face["bgr"], label=labels[index]).to_dict(),
                "mesh": evaluate_mesh(face["vertices"], face["result"]["triangles"], label=labels[index]).to_dict(),
            })
        report = build_timeline_report(
            [face["vertices"] for face in faces],
            years,
            labels=labels,
            quality_keyframes=quality_keyframes,
            provenance={
                "endpoint": "/api/report-timeline",
                "reconstruction": "app8",
                "alignment": "identity_object_space",
                "pose_bin": pose["canonical_bin"],
                "aligned_to": pose["aligned_to"],
                "pose_warning": pose["warning"],
                "input_sha256": [hashlib.sha256(raw).hexdigest() for raw in raw_images],
            },
        )
        if format == "html":
            return HTMLResponse(content=render_report_html(report, "3D face timeline report"))
        return JSONResponse(content=report)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка формирования timeline-отчёта: {exc}") from exc


@app.post("/api/morph-pair")
async def morph_pair(
    photo_a: UploadFile = File(...),
    photo_b: UploadFile = File(...),
    deformation: str = Form(default="linear"),
) -> JSONResponse:
    """Reconstruct two faces and return a backwards-compatible pair payload."""
    try:
        if deformation.lower() not in {"linear", "direct", "tps", "smooth"}:
            raise HTTPException(status_code=400, detail="deformation должен быть linear или tps")
        raw_a, raw_b = await photo_a.read(), await photo_b.read()
        return JSONResponse(content=_pair_payload(_reconstruct(raw_a, "A"), _reconstruct(raw_b, "B"), deformation))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки морфинга: {exc}") from exc


async def _sequence_response(
    photos: list[UploadFile],
    metadata_raw: str | None,
    future_year_raw: str | None = None,
) -> dict[str, Any]:
    if not 2 <= len(photos) <= 4:
        raise HTTPException(status_code=400, detail="Для timeline нужно от 2 до 4 фотографий")
    try:
        metadata = json.loads(metadata_raw) if metadata_raw else []
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"metadata должен быть JSON-массивом: {exc}") from exc
    if metadata and (not isinstance(metadata, list) or len(metadata) != len(photos)):
        raise HTTPException(status_code=400, detail="metadata должен содержать запись для каждого фото")

    faces = []
    for index, upload in enumerate(photos):
        faces.append(await upload.read())
    reconstructed = [_reconstruct(raw, chr(65 + index)) for index, raw in enumerate(faces)]
    pose = _align_group(reconstructed)
    vertex_arrays = [face["vertices"] for face in reconstructed]
    sequence_metrics = [
        similarity_metrics(vertex_arrays[index], vertex_arrays[index + 1])
        for index in range(len(vertex_arrays) - 1)
    ]
    labels = []
    keyframes = []
    for index, item in enumerate(metadata or []):
        item = item if isinstance(item, dict) else {}
        labels.append(str(item.get("label") or f"Face {chr(65 + index)}"))
        keyframes.append({"index": index, "label": labels[-1], "year": item.get("year")})
    if not labels:
        labels = [f"Face {chr(65 + index)}" for index in range(len(reconstructed))]
        keyframes = [{"index": i, "label": label} for i, label in enumerate(labels)]

    numeric_years = []
    if metadata:
        try:
            candidate_years = [float(item.get("year")) for item in metadata]
            numeric_years = candidate_years if all(np.isfinite(candidate_years)) else []
        except (TypeError, ValueError, AttributeError):
            numeric_years = []
    future_year = None
    if future_year_raw not in (None, ""):
        try:
            future_year = float(future_year_raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="future_year должен быть числом") from exc
        if not np.isfinite(future_year):
            raise HTTPException(status_code=400, detail="future_year должен быть конечным числом")
    timeline_positions = None
    if len(numeric_years) == len(reconstructed) and max(numeric_years) > min(numeric_years):
        first_year, last_year = min(numeric_years), max(numeric_years)
        candidate_positions = [(year - first_year) / (last_year - first_year) for year in numeric_years]
        if all(right > left for left, right in zip(candidate_positions, candidate_positions[1:])):
            timeline_positions = candidate_positions
    quality_keyframes = []
    for index, face in enumerate(reconstructed):
        quality_keyframes.append({
            "index": index,
            "label": labels[index],
            "year": numeric_years[index] if len(numeric_years) == len(reconstructed) else None,
            "photo": evaluate_image(face["bgr"], label=labels[index]).to_dict(),
            "mesh": evaluate_mesh(face["vertices"], face["result"]["triangles"], label=labels[index]).to_dict(),
        })
    first, last = reconstructed[0], reconstructed[-1]
    first_last = similarity_metrics(first["vertices"], last["vertices"])
    sequence_noise = pair_noise_reference(
        pose,
        first_last,
        yaw_spread_deg=abs(float(first["result"]["angles_deg"][1]) - float(last["result"]["angles_deg"][1])),
    )
    drift = temporal_drift_metrics(numeric_years, vertex_arrays) if len(numeric_years) >= 3 else None
    extrapolation = None
    if future_year is not None:
        if len(numeric_years) < 3 or timeline_positions is None:
            raise HTTPException(status_code=400, detail="Для extrapolation нужны минимум 3 года в строго возрастающем порядке")
        if future_year <= numeric_years[-1]:
            raise HTTPException(status_code=400, detail="future_year должен быть позже последнего года")
        if future_year - numeric_years[-1] > MAX_EXTRAPOLATION_HORIZON_YEARS:
            raise HTTPException(status_code=400, detail=f"прогноз ограничен горизонтом {MAX_EXTRAPOLATION_HORIZON_YEARS:g} лет")
        prediction, extrapolation_info = extrapolate_shape(numeric_years, vertex_arrays, future_year)
        extrapolation = {**extrapolation_info, "vertices": prediction.flatten().tolist()}
    return {
        "status": "success",
        "timeline": {**timeline_metadata(len(reconstructed), labels, timeline_positions), "keyframes": keyframes},
        "extrapolation": extrapolation,
        "triangles": reconstructed[0]["result"]["triangles"].flatten().tolist(),
        "uv_coords": reconstructed[0]["result"]["uv_coords"].flatten().tolist(),
        "sequence_vertices": [face["vertices"].flatten().tolist() for face in reconstructed],
        "sequence_landmarks": [face["landmarks"].flatten().tolist() for face in reconstructed],
        "sequence_textures": [face["texture_b64"] for face in reconstructed],
        "texture_diff_base64": _bgr_to_base64_png(uv_difference(first["texture"], last["texture"])),
        "parameter_heatmap": _parameter_heatmap(first_last["euclidean_mean"]),
        "previews": [_bgr_to_base64_jpeg(face["bgr"], quality=82) for face in reconstructed],
        "metadata": {
            "keyframe_count": len(reconstructed),
            "pose": pose,
            "noise": sequence_noise,
            **_heat_scales(sequence_noise),
            "mean_adjacent_difference": round(float(np.mean([m["euclidean_mean"] for m in sequence_metrics])), 8),
            "first_last_similarity": first_last,
            "temporal_drift": drift,
            "face_space": pca_projection(vertex_arrays),
            "quality_keyframes": quality_keyframes,
            "method": "Catmull-Rom spline over aligned identity meshes",
        },
    }


@app.post("/api/morph-sequence")
@app.post("/api/morph-multi")
async def morph_sequence(
    photos: list[UploadFile] = File(...),
    metadata: str | None = Form(default=None),
    future_year: str | None = Form(default=None),
) -> dict[str, Any]:
    """Build a 2–4 keyframe Catmull-Rom face timeline."""
    try:
        return await _sequence_response(photos, metadata, future_year)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка timeline-морфинга: {exc}") from exc


@app.post("/api/similarity-matrix")
async def batch_similarity_matrix(photos: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Compare 2–16 uploaded faces as an explainable distance matrix."""
    if not 2 <= len(photos) <= 16:
        raise HTTPException(status_code=400, detail="similarity-matrix принимает от 2 до 16 фотографий")
    try:
        faces = [_reconstruct(await upload.read(), chr(65 + index)) for index, upload in enumerate(photos)]
        labels = [upload.filename or f"Face {index + 1}" for index, upload in enumerate(photos)]
        return {"status": "ok", **build_similarity_matrix([face["vertices"] for face in faces], labels)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка similarity matrix: {exc}") from exc


@app.post("/api/face-space")
async def face_space(photos: list[UploadFile] = File(...)) -> dict[str, Any]:
    """Project uploaded canonical meshes to a reproducible 3D PCA space."""
    if not 2 <= len(photos) <= 16:
        raise HTTPException(status_code=400, detail="face-space принимает от 2 до 16 фотографий")
    try:
        faces = [_reconstruct(await upload.read(), chr(65 + index)) for index, upload in enumerate(photos)]
        projection = pca_projection([face["vertices"] for face in faces])
        return {
            "status": "ok",
            "points": [
                {"index": index, "label": upload.filename or f"Face {chr(65 + index)}", "x": row[0], "y": row[1], "z": row[2]}
                for index, (upload, row) in enumerate(zip(photos, projection["coordinates"]))
            ],
            "explained_variance": projection["explained_variance"],
            "path": list(range(len(faces))),
            "highlighted": [0, 1],
            "method": projection["method"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка PCA face-space: {exc}") from exc


@app.post("/api/morph-blend")
async def morph_blend(
    photos: list[UploadFile] = File(...),
    weights: str = Form(...),
) -> dict[str, Any]:
    """Return a server-side barycentric shape blend for 2–4 uploaded faces."""
    try:
        payload = await _sequence_response(photos, None)
        raw_weights = json.loads(weights)
        if not isinstance(raw_weights, list) or len(raw_weights) != len(photos):
            raise HTTPException(status_code=400, detail="weights должен содержать вес каждого фото")
        arrays = [np.asarray(item, dtype=np.float32).reshape(-1, 3) for item in payload["sequence_vertices"]]
        blended = blend_vertices(arrays, raw_weights)
        normalized = np.asarray(raw_weights, dtype=np.float64)
        normalized /= normalized.sum()
        return {**payload, "blend": {"weights": normalized.tolist(), "vertices": blended.flatten().tolist(), "method": "normalized barycentric blend"}}
    except HTTPException:
        raise
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Некорректные blend weights: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка multi-face blend: {exc}") from exc


@app.post("/api/similarity")
async def compute_similarity(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)) -> dict[str, Any]:
    """Return dense Euclidean/cosine metrics and the five largest zones."""
    try:
        raw_a, raw_b = await photo_a.read(), await photo_b.read()
        pair = _pair_payload(_reconstruct(raw_a, "A"), _reconstruct(raw_b, "B"))
        metadata = pair["metadata"]
        return {
            "status": "ok",
            "vertex_count": len(pair["vertices_a"]) // 3,
            "euclidean_distance": metadata["euclidean_distance"],
            "euclidean_mean": metadata["mean_3d_difference"],
            "euclidean_max": metadata["max_3d_difference"],
            "p95_delta": metadata["p95_3d_difference"],
            "cosine_similarity": metadata["cosine_similarity"],
            "morphability_score": metadata["morphability_score"],
            "top_5_zones": metadata["top_5_zones"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка similarity: {exc}") from exc


@app.post("/api/forensic-score")
async def forensic_score(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)) -> dict[str, Any]:
    """Return explainable, zone-weighted geometric identity similarity."""
    try:
        raw_a, raw_b = await photo_a.read(), await photo_b.read()
        face_a, face_b = _reconstruct(raw_a, "A"), _reconstruct(raw_b, "B")
        pose = _align_group([face_a, face_b])
        result = forensic_metrics(face_a["vertices"], face_b["vertices"], weights=DEFAULT_ZONE_WEIGHTS)
        return {"status": "ok", "global_forensic_score": result["forensic_score"], "pose": pose, **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка forensic score: {exc}") from exc


@app.post("/api/symmetry")
async def face_symmetry(photo: UploadFile = File(...)) -> dict[str, Any]:
    """Compute bilateral symmetry of one canonicalized face mesh."""
    try:
        raw = await photo.read()
        face = _reconstruct(raw, "symmetry")
        return {"status": "ok", **symmetry_metrics(face["vertices"])}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка symmetry: {exc}") from exc


@app.post("/api/uv-diff")
async def texture_diff(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)) -> dict[str, Any]:
    """Return a normalized UV texture difference independent of mesh shape."""
    try:
        raw_a, raw_b = await photo_a.read(), await photo_b.read()
        face_a, face_b = _reconstruct(raw_a, "A"), _reconstruct(raw_b, "B")
        diff = uv_difference(face_a["texture"], face_b["texture"])
        return {"status": "ok", "texture_diff_base64": _bgr_to_base64_png(diff), "size": list(diff.shape[:2][::-1])}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка UV diff: {exc}") from exc


@app.post("/api/export-gif")
async def export_gif(photo_a: UploadFile = File(...), photo_b: UploadFile = File(...)) -> FileResponse:
    """Generate the existing high-quality A→B→A GIF export."""
    try:
        bytes_a, bytes_b = await photo_a.read(), await photo_b.read()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_a, tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_b, tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as f_gif:
            f_a.write(bytes_a)
            f_b.write(bytes_b)
            f_a.flush()
            f_b.flush()
            gif_path = generate_morph_gif(f_a.name, f_b.name, f_gif.name, num_frames=24, img_size=512, fps=12)
            return FileResponse(path=str(gif_path), filename="3d_face_morph.gif", media_type="image/gif")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации GIF: {exc}") from exc


# ── 3-WAY IDENTITY PROBABILITY (put / vas / udmurt) ──────────────────────
_IDENTITY_MODEL_CACHE: dict[str, Any] = {"model": None, "loaded": False, "error": None}


def _identity_model():
    """Ленивая загрузка эталонов формы; кэш на процесс."""
    if not _IDENTITY_MODEL_CACHE["loaded"]:
        _IDENTITY_MODEL_CACHE["loaded"] = True
        try:
            _IDENTITY_MODEL_CACHE["model"] = identity_module.load_prototypes()
        except FileNotFoundError:
            _IDENTITY_MODEL_CACHE["model"] = None
            _IDENTITY_MODEL_CACHE["error"] = "файл identity_prototypes.json не найден"
        except ValueError as exc:
            # Устаревшее пространство выравнивания: молча классифицировать нельзя.
            _IDENTITY_MODEL_CACHE["model"] = None
            _IDENTITY_MODEL_CACHE["error"] = str(exc)
    return _IDENTITY_MODEL_CACHE["model"]


def _landmarks_only(raw: bytes, label: str) -> np.ndarray:
    result = reconstruct_image(io.BytesIO(raw), device="cpu")
    if result is None:
        raise HTTPException(status_code=400, detail=f"На фото {label} не обнаружено лицо")
    return align_identity_mesh(result)[1]


@app.post("/api/identify-probability")
async def identify_probability(photo: UploadFile = File(...)) -> dict[str, Any]:
    """Процентное сходство загруженного лица с эталонами личностей по форме (17 метрик).

    Эвристика, не калиброванная вероятность личности.
    """
    model = _identity_model()
    if model is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Эталоны личностей недоступны — соберите identity_prototypes.json. "
                f"Причина: {_IDENTITY_MODEL_CACHE.get('error') or 'файл не читается'}"
            ),
        )
    try:
        raw = await photo.read()
        landmarks = _landmarks_only(raw, "photo")
        result = identity_module.probabilities(model, landmarks)
        return {"status": "ok", "identities": model.identities, **result}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка identify-probability: {exc}") from exc


@app.post("/api/form-metrics")
async def form_metrics(
    photo_a: UploadFile = File(...),
    photo_b: UploadFile = File(...),
) -> dict[str, Any]:
    """Все 30 утверждённых метрик формы на двух фото + «на кого из трёх лиц» по каждой.

    Цвет ячейки — это доля близости к двум ближайшим эталонам личностей (`ref` в
    `metric_bands.json`: медианы спокойных кадров put/vas/udmurt). Ровно посередине
    между двумя лицами ячейка делится 50/50, у самой медианы — один цвет. Оттенок
    «не похоже ни на кого» (`stray`) — дальше откалиброванной гулянки одного лица.
    Вердикт пары (`same`/`border`/`differ`) остаётся текстом: он про согласие двух
    снимков, а не про личность. Девять метрик, устойчивых к подфронтальному повороту,
    помечены `trusted` — интерфейс обводит их белой рамкой. MediaPipe считается в
    отдельном процессе (он не живёт с torch в одном интерпретаторе), поэтому без него
    14 метрик уходят null с причиной.
    """
    try:
        raw_a, raw_b = await photo_a.read(), await photo_b.read()
        return form_metrics_module.pair_report(raw_a, raw_b)
    except form_metrics_module.BandsMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка form-metrics: {exc}") from exc


STATIC_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("morphing.backend.server:app", host="0.0.0.0", port=8000, reload=True)
