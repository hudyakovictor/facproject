"""🚪 ENTRY POINT → FastAPI-приложение DEEPUTIN forensic workstation.

Запуск для разработки:
    uvicorn app6.api.server:app --reload --port 8000

Через RUN_PROJECT.sh:
    ./RUN_PROJECT.sh api

Контракт эндпоинтов соответствует `ui/API_CONTRACT.md` и
`docs/техническое задание проекта/aboutplatform.txt` ("Судебно-медицинская
рабочая станция"). Все ответы, основанные на демо-данных, содержат
`source_mode: "demo"` и `not_a_verdict: true` — см. `app6/AGENTS.md`.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app6.stage1.naming import make_photo_id, parse_photo_name
from app6.stage1.utils import digest_file

from .bfm_topology import is_bfm_available
from .calibration import load_calibration_health
from .compare import compare_records, full_mesh_compare
from .demo_data import DemoPhoto, build_demo_records, build_demo_zone_maps, full_mesh_for_photo
from .jobs import JobManager, make_extract_runner, make_recompute_metrics_runner
from .settings import DEFAULT_SETTINGS, load_settings, save_settings
from .system_health import build_system_health
from .timeline import build_demo_timeline

APP_SCHEMA = "deeputin-api-v1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="DEEPUTIN Forensic Workstation API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 💡 NOTE: полный BFM-меш (~3.7 MB JSON на фото — 35 709 вершин + 70 789
# треугольников) сжимается более чем в 10 раз gzip'ом. Без этого middleware
# каждый запрос 3D Inspector/Compare был бы неоправданно тяжёлым по сети.
app.add_middleware(GZipMiddleware, minimum_size=1024)

_job_manager = JobManager()

# 💡 NOTE: demo-датасет строится лениво и кэшируется в памяти процесса —
# построение реальной геометрии (Kabsch, zone map) для 520 записей занимает
# заметное время, а данные детерминированы (тот же seed), так что кэш не
# теряет актуальность между запросами одного процесса.
_demo_cache: dict[str, Any] = {}


def _stage1_root() -> Path | None:
    import os
    raw = os.environ.get("DEEPUTIN_STAGE1_ROOT")
    if not raw:
        return None
    path = Path(raw)
    return path if (path / "main_timeline.csv").is_file() else None


def _stage2_root() -> Path | None:
    import os
    raw = os.environ.get("DEEPUTIN_STAGE2_ROOT")
    if not raw:
        return None
    path = Path(raw)
    return path if (path / "analysis_manifest.json").is_file() else None


def _uploads_root() -> Path:
    import os
    raw = os.environ.get("DEEPUTIN_UPLOADS_ROOT")
    path = Path(raw) if raw else PROJECT_ROOT / "runs" / "api_uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _calibration_root() -> Path:
    import os
    raw = os.environ.get("DEEPUTIN_CALIBRATION_ROOT")
    return Path(raw) if raw else PROJECT_ROOT / "calibration_dataset"


def _get_demo_photos() -> list[DemoPhoto]:
    if "photos" not in _demo_cache:
        photos = build_demo_records()
        zone106, zone134 = build_demo_zone_maps(photos)
        _demo_cache["photos"] = photos
        _demo_cache["zone106"] = zone106
        _demo_cache["zone134"] = zone134
        _demo_cache["by_id"] = {p.id: p for p in photos}
    return _demo_cache["photos"]


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {"schema": APP_SCHEMA, "status": "ok", "not_a_verdict": True}


@app.get("/api/v1/timeline")
def get_timeline() -> dict[str, Any]:
    """🚪 API → Хронология для главного таймлайна интерфейса.

    Возвращает вывод реального Stage 2 (`analysis_manifest.json` +
    `pair_metrics.csv`), если `DEEPUTIN_STAGE2_ROOT` указывает на валидный
    прогон; иначе — детерминированный demo-timeline (`timeline.py`),
    честно помеченный `source_mode: "demo"`.
    """
    stage2_root = _stage2_root()
    if stage2_root is not None:
        from .research_timeline import build_research_timeline
        try:
            return build_research_timeline(stage2_root)
        except Exception as exc:  # noqa: BLE001 - fall back to demo, do not 500 the UI
            payload = build_demo_timeline()
            payload["research_load_error"] = str(exc)
            return payload
    if "timeline" not in _demo_cache:
        _demo_cache["timeline"] = build_demo_timeline()
    return _demo_cache["timeline"]


@app.get("/api/v1/photos")
def list_photos() -> dict[str, Any]:
    """🚪 API → Список фото (демо или research) с метаданными без raw-изображений."""
    stage1_root = _stage1_root()
    if stage1_root is not None:
        manifest_path = stage1_root / "stage1_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        return {"schema": APP_SCHEMA, "source_mode": "research", "manifest": manifest,
                "photo_dirs": sorted(p.name for p in stage1_root.iterdir() if p.is_dir() and not p.name.startswith("_"))}
    photos = _get_demo_photos()
    return {
        "schema": APP_SCHEMA, "source_mode": "demo", "not_a_verdict": True,
        "count": len(photos),
        "photos": [{"id": p.id, "date": p.date, "bucket": p.pose_bin, "era": p.era} for p in photos],
    }


@app.get("/api/v1/photos/{photo_id}")
def get_photo(photo_id: str) -> dict[str, Any]:
    photos_by_id = _get_demo_photos() and _demo_cache["by_id"]
    photo = photos_by_id.get(photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail=f"photo not found: {photo_id}")
    record = photo.record
    return {
        "schema": APP_SCHEMA, "source_mode": "demo", "not_a_verdict": True,
        "id": photo.id, "date": photo.date, "bucket": photo.pose_bin, "era": photo.era,
        "angles": {"pitch": float(record.angles[0]), "yaw": float(record.angles[1]), "roll": float(record.angles[2])},
        "landmarks_106": record.ldm106.tolist(),
        "landmarks_134": record.ldm134.tolist(),
        "visible_134": record.visible134.tolist(),
        "full_mesh_available": is_bfm_available(),
    }


@app.get("/api/v1/photos/{photo_id}/mesh")
def get_photo_full_mesh(photo_id: str) -> dict[str, Any]:
    """🚪 API → Полный BFM-меш (35 709 вершин, реальная топология) для 3D Inspector.

    Использует ту же геометрическую модель, что и продакшн Stage 1
    (`3ddfa_v3/assets/face_model.tar.gz`), без запуска нейросети — только
    линейная реконструкция формы из уже известного `alpha_id`.
    """
    by_id = _get_demo_photos() and _demo_cache["by_id"]
    photo = by_id.get(photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail=f"photo not found: {photo_id}")
    if not is_bfm_available():
        raise HTTPException(status_code=503, detail="BFM geometry (face_model.tar.gz) unavailable in this environment")
    mesh = full_mesh_for_photo(photo)
    return {"schema": APP_SCHEMA, "source_mode": "demo", "not_a_verdict": True, "id": photo.id, **mesh}


class UploadResponse(BaseModel):
    schema_: str
    photo_id: str
    date: str | None
    stored: bool
    message: str


@app.post("/api/v1/photos/upload")
async def upload_photo(file: UploadFile = File(...)) -> dict[str, Any]:
    """🚪 API → Загрузка фото в постоянное хранилище (участвует в будущих Stage 1 прогонах).

    🚨 WARNING: не запускает Stage 1 инлайн (нет весов 3DDFA_V3 в типовом
    окружении песочницы/CI) — файл только сохраняется под валидным именем
    `YYYY_MM_DD[_N].ext` (`app6/AGENTS.md`). Извлечение выполняется отдельным
    заданием `POST /api/v1/jobs {"kind": "extract"}`.
    """
    uploads_dir = _uploads_root() / "main"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload.jpg").suffix.lower()
    if suffix not in (".jpg", ".jpeg", ".png"):
        raise HTTPException(status_code=400, detail="only .jpg/.jpeg/.png are accepted")

    temp_path = uploads_dir / f"_incoming{suffix}"
    content = await file.read()
    temp_path.write_bytes(content)
    try:
        parsed = parse_photo_name(Path(file.filename or "upload.jpg"))
    except ValueError as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"invalid filename (expected YYYY_MM_DD[_N].ext): {exc}",
        ) from exc

    digest = digest_file(temp_path)
    photo_id = make_photo_id(parsed, digest)
    final_path = uploads_dir / f"{photo_id}{suffix}"
    if final_path.is_file():
        temp_path.unlink(missing_ok=True)
        return {"schema": APP_SCHEMA, "photo_id": photo_id, "date": parsed.date_iso,
                "stored": False, "message": "photo with identical content already uploaded"}
    temp_path.rename(final_path)
    return {"schema": APP_SCHEMA, "photo_id": photo_id, "date": parsed.date_iso,
            "stored": True, "message": f"saved to {final_path}"}


@app.delete("/api/v1/photos/{photo_id}")
def delete_photo(photo_id: str) -> dict[str, Any]:
    """🚪 API → Удалить извлечённые данные фото. Исходный файл не трогается по имени,
    только Stage-1-производные под `DEEPUTIN_STAGE1_ROOT/{photo_id}`."""
    stage1_root = _stage1_root()
    if stage1_root is None:
        raise HTTPException(status_code=409, detail="no Stage 1 output configured (DEEPUTIN_STAGE1_ROOT)")
    target = stage1_root / photo_id
    if not target.is_dir():
        raise HTTPException(status_code=404, detail=f"no Stage 1 output for {photo_id}")
    shutil.rmtree(target)
    return {"schema": APP_SCHEMA, "deleted": photo_id}


class ComparePairRequest(BaseModel):
    photo_a: str
    photo_b: str


@app.post("/api/v1/compare")
def compare_pair(request: ComparePairRequest) -> dict[str, Any]:
    """🚪 API → Реальное геометрическое сравнение двух записей (демо или research).

    Использует ранее извлечённые landmarks (без повторного inference —
    соответствует "умному кэшированию" из ТЗ: 3D-модель не извлекается
    заново для уже известных фото).
    """
    by_id = _get_demo_photos() and _demo_cache["by_id"]
    photo_a = by_id.get(request.photo_a)
    photo_b = by_id.get(request.photo_b)
    if photo_a is None or photo_b is None:
        missing = [pid for pid in (request.photo_a, request.photo_b) if pid not in by_id]
        raise HTTPException(status_code=404, detail=f"unknown photo id(s): {missing}")
    result = compare_records(photo_a.record, photo_b.record)
    result["source_mode"] = "demo"
    result["photo_a"] = {"id": photo_a.id, "date": photo_a.date, "bucket": photo_a.pose_bin}
    result["photo_b"] = {"id": photo_b.id, "date": photo_b.date, "bucket": photo_b.pose_bin}
    return result


@app.post("/api/v1/compare/full_mesh")
def compare_pair_full_mesh(request: ComparePairRequest) -> dict[str, Any]:
    """🚪 API → Полное BFM-сравнение (35 709 вершин) для морфинга/3D Inspector.

    В отличие от `/api/v1/compare` (134 landmarks), здесь выравнивается и
    сравнивается вся identity-форма (без мимики) с подлинной топологией
    треугольников — то, что нужно для настоящего 3D-морфинга A→B из ТЗ.
    """
    by_id = _get_demo_photos() and _demo_cache["by_id"]
    photo_a = by_id.get(request.photo_a)
    photo_b = by_id.get(request.photo_b)
    if photo_a is None or photo_b is None:
        missing = [pid for pid in (request.photo_a, request.photo_b) if pid not in by_id]
        raise HTTPException(status_code=404, detail=f"unknown photo id(s): {missing}")
    result = full_mesh_compare(photo_a, photo_b)
    if result is None:
        raise HTTPException(status_code=503, detail="BFM geometry (face_model.tar.gz) unavailable in this environment")
    result["source_mode"] = "demo"
    result["photo_a"] = {"id": photo_a.id, "date": photo_a.date, "bucket": photo_a.pose_bin}
    result["photo_b"] = {"id": photo_b.id, "date": photo_b.date, "bucket": photo_b.pose_bin}
    return result


@app.post("/api/v1/compare/upload")
async def compare_with_upload(photo_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    """🚪 API → Сравнить существующее фото с загруженным на лету (не сохраняется в базу).

    🚨 WARNING: извлечение 3D-модели из загруженного фото требует Stage 1
    (3DDFA_V3). Без весов модели в этом окружении эндпоинт возвращает
    HTTP 501 с понятной причиной, а не выдуманный результат.
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "извлечение 3D-модели из произвольного загруженного фото требует Stage 1 "
            "(веса 3DDFA_V3, недоступны в этом окружении). Загрузите фото через "
            "/api/v1/photos/upload и запустите job kind=extract, затем сравнивайте "
            "через /api/v1/compare по photo_id."
        ),
    )


@app.get("/api/v1/calibration/health")
def calibration_health() -> dict[str, Any]:
    try:
        return load_calibration_health(_calibration_root())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class JobRequest(BaseModel):
    kind: str
    input_dir: str | None = None
    output_dir: str | None = None
    stage1_root: str | None = None
    calibration_root: str | None = None
    device: str = "auto"
    limit: int = 0


@app.post("/api/v1/jobs")
def submit_job(request: JobRequest) -> dict[str, Any]:
    if request.kind == "extract":
        input_dir = Path(request.input_dir) if request.input_dir else _uploads_root() / "main"
        output_dir = Path(request.output_dir) if request.output_dir else PROJECT_ROOT / "runs" / "api_stage1"
        if not input_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"input_dir does not exist: {input_dir}")
        runner = make_extract_runner(input_dir, output_dir, PROJECT_ROOT, device=request.device, limit=request.limit)
    elif request.kind == "recompute_metrics":
        stage1_root = Path(request.stage1_root) if request.stage1_root else _stage1_root()
        if stage1_root is None:
            raise HTTPException(status_code=400, detail="stage1_root not provided and DEEPUTIN_STAGE1_ROOT not set")
        calibration_root = Path(request.calibration_root) if request.calibration_root else _calibration_root()
        output_dir = Path(request.output_dir) if request.output_dir else PROJECT_ROOT / "runs" / "api_stage2"
        runner = make_recompute_metrics_runner(stage1_root, calibration_root, output_dir)
    else:
        raise HTTPException(status_code=400, detail=f"unknown job kind: {request.kind}")
    job_id = _job_manager.submit(request.kind, runner)
    return {"schema": APP_SCHEMA, "job_id": job_id}


@app.get("/api/v1/jobs")
def list_jobs() -> dict[str, Any]:
    return {"schema": APP_SCHEMA, "jobs": _job_manager.list_jobs()}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return job


@app.post("/api/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    ok = _job_manager.cancel(job_id)
    if not ok:
        raise HTTPException(status_code=409, detail="job not cancellable (unknown or already terminal)")
    return {"schema": APP_SCHEMA, "cancelled": job_id}


@app.get("/api/v1/system/health")
def system_health() -> dict[str, Any]:
    return build_system_health(PROJECT_ROOT)


@app.get("/api/v1/settings")
def get_settings() -> dict[str, Any]:
    return load_settings(PROJECT_ROOT)


@app.put("/api/v1/settings")
def put_settings(payload: dict[str, Any]) -> dict[str, Any]:
    return save_settings(PROJECT_ROOT, payload)


@app.post("/api/v1/settings/reset")
def reset_settings() -> dict[str, Any]:
    return save_settings(PROJECT_ROOT, DEFAULT_SETTINGS)


@app.post("/api/v1/data/clear")
def clear_data() -> dict[str, Any]:
    """🚪 API → Очистить извлечённые данные без удаления исходных фото с диска.

    Удаляет только `runs/api_stage1`, `runs/api_stage2` и локальный кэш job'ов
    процесса. Исходные фото под `DEEPUTIN_UPLOADS_ROOT`/`--input` не трогаются.
    """
    removed = []
    for rel in ("runs/api_stage1", "runs/api_stage2"):
        path = PROJECT_ROOT / rel
        if path.exists():
            shutil.rmtree(path)
            removed.append(rel)
    _demo_cache.clear()
    return {"schema": APP_SCHEMA, "removed": removed, "note": "исходные фото не удалены"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Any, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"schema": APP_SCHEMA, "error": str(exc), "not_a_verdict": True})
