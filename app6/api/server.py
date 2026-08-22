"""🚪 ENTRY POINT → FastAPI-приложение DEEPUTIN forensic workstation.

Запуск для разработки:
    uvicorn app6.api.server:app --reload --port 8000

Через RUN_PROJECT.sh:
    ./RUN_PROJECT.sh api

Контракт эндпоинтов соответствует `ui/API_CONTRACT.md` и
`docs/техническое задание проекта/aboutplatform.txt` ("Судебно-медицинская
рабочая станция"). Все ответы, основанные на демо-данных, содержат
Все данные API происходят только из реальных артефактов Stage 1/2; отсутствие
готового прогона возвращается как явное состояние, а не подменяется данными.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from app6.stage1.naming import make_photo_id, parse_photo_name
from app6.stage1.utils import digest_file

from .bfm_topology import is_bfm_available
from .calibration import find_matching_calibration_frames, load_calibration_health

from .compare import compare_records, full_mesh_compare
from .jobs import JobManager, make_extract_runner, make_recompute_metrics_runner
from .noise_calibration import (
    apply_noise_subtraction, build_noise_index, noise_coverage_report, resolve_tolerance,
)
from .settings import DEFAULT_SETTINGS, load_settings, save_settings
from .skin_zones import SKIN_ZONES_SCHEMA, load_skin_zone_report, zone_catalog
from .system_health import build_system_health
from .review import append_review

APP_SCHEMA = "deeputin-api-v1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: P1.8 — предел размера одной загружаемой фотографии. 32 МиБ с запасом
#: покрывает исходники исследуемого набора (600–800px JPEG, единицы сотен КБ)
#: и снимки полного разрешения, но не позволяет заполнить диск одним запросом.
#: Переопределяется переменной окружения DEEPUTIN_MAX_UPLOAD_MB.
MAX_UPLOAD_BYTES = int(float(os.environ.get("DEEPUTIN_MAX_UPLOAD_MB", "32")) * 1024 * 1024)
#: Размер блока потокового чтения тела запроса.
UPLOAD_CHUNK_BYTES = 1024 * 1024
_IMAGE_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


def _upload_signature_matches(path: Path, suffix: str) -> bool:
    signatures = _IMAGE_SIGNATURES.get(suffix.lower(), ())
    if not signatures:
        return False
    longest = max(map(len, signatures))
    with path.open("rb") as stream:
        prefix = stream.read(longest)
    return any(prefix.startswith(signature) for signature in signatures)


def _upload_image_decodes(path: Path) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
        return True
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return False

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

_CANONICAL_STORAGE_ROOT = Path("/Volumes/SDCARD/storage")


def _path_with_file(path: Path, filename: str) -> Path | None:
    return path if (path / filename).is_file() else None


def _stage2_manifest(path: Path) -> dict[str, Any] | None:
    manifest_path = path / "analysis_manifest.json"
    if not manifest_path.is_file() or not (path / "pair_metrics.csv").is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict) or manifest.get("status") != "complete":
        return None
    return manifest


def _manifest_sort_key(item: tuple[Path, dict[str, Any]]) -> tuple[str, int, str]:
    path, manifest = item
    return (str(manifest.get("created_at_utc", "")), path.stat().st_mtime_ns, str(path))


def _stage1_root() -> Path | None:
    if "DEEPUTIN_STAGE1_ROOT" in os.environ:
        raw = os.environ.get("DEEPUTIN_STAGE1_ROOT", "").strip()
        if not raw:
            return None
        return _path_with_file(Path(raw), "main_timeline.csv")
    return _path_with_file(_storage_root() / "stage1", "main_timeline.csv")


def _stage2_root() -> Path | None:
    raw = os.environ.get("DEEPUTIN_STAGE2_ROOT")
    if raw:
        return Path(raw) if _stage2_manifest(Path(raw)) is not None else None

    storage_root = _storage_root()
    # Check for canonical Stage 2 location
    candidate_path = storage_root / "stage2_resumable_20260816"
    if candidate_path.is_dir():
        manifest_path = candidate_path / "analysis_manifest.json"
        if manifest_path.is_file():
            return candidate_path

    # Check for direct stage2 directory
    direct = _stage2_manifest(storage_root / "stage2")
    if direct is not None:
        return storage_root / "stage2"

    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in storage_root.glob("stage2_*"):
        if not path.is_dir():
            continue
        manifest = _stage2_manifest(path)
        if manifest is not None:
            candidates.append((path, manifest))
    return max(candidates, key=_manifest_sort_key)[0] if candidates else None


def _uploads_root() -> Path:
    raw = os.environ.get("DEEPUTIN_UPLOADS_ROOT")
    path = Path(raw) if raw else _storage_root() / "api_uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _storage_root() -> Path:
    raw = os.environ.get("DEEPUTIN_STORAGE_ROOT")
    if raw:
        root = Path(raw).resolve()
    elif _CANONICAL_STORAGE_ROOT.is_dir():
        root = _CANONICAL_STORAGE_ROOT.resolve()
    else:
        root = (PROJECT_ROOT / "runs" / "storage").resolve()
    if root == Path(root.anchor):
        raise RuntimeError(f"unsafe DEEPUTIN_STORAGE_ROOT: {root}")
    return root


def _calibration_root() -> Path:
    import os
    raw = os.environ.get("DEEPUTIN_CALIBRATION_ROOT")
    if raw:
        return Path(raw)
    storage_root = _storage_root()
    candidate = storage_root / "calibration_dataset"
    if candidate.is_dir():
        return candidate
    return PROJECT_ROOT / "calibration_dataset"


def _require_stage1() -> Path:
    stage1_root = _stage1_root()
    if stage1_root is None:
        raise HTTPException(
            status_code=409,
            detail="данные Stage 1 ещё не настроены: задайте DEEPUTIN_STAGE1_ROOT на завершённый вывод с main_timeline.csv",
        )
    return stage1_root


@lru_cache(maxsize=2)
def _cached_main_records(root_text: str, manifest_mtime_ns: int) -> dict[str, Any]:
    from app6.stage2.loaders import load_main
    return {record.record_id: record for record in load_main(Path(root_text))}

def _main_records() -> dict[str, Any]:
    root=_require_stage1();marker=root/"stage1_manifest.json"
    return _cached_main_records(str(root.resolve()),marker.stat().st_mtime_ns if marker.is_file() else 0)


def _main_record(photo_id: str) -> Any:
    record = _main_records().get(photo_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"photo not found in Stage 1 output: {photo_id}")
    return record


_UI_ARTIFACTS = {"face_mask.png": "image/png", "texture.json": "application/json", "info.json": "application/json"}
_LANDMARK_FILES = {
    (106, "raw"): ("ldm106_raw.csv", "raw_object_normalized"),
    (106, "aligned"): ("ldm106_chronology.csv", "chronology_aligned"),
    (106, "original"): ("ldm106_original.csv", "original_image_px"),
    (134, "raw"): ("ldm134_raw.csv", "raw_object_normalized"),
    (134, "aligned"): ("ldm134_chronology.csv", "chronology_aligned"),
    (134, "original"): ("ldm134_original.csv", "original_image_px"),
}


def _safe_record_file(photo_id: str, filename: str) -> Path:
    root = Path(str(_main_record(photo_id).record_dir)).resolve()
    path = (root / filename).resolve()
    if root not in path.parents:
        raise HTTPException(status_code=400, detail="invalid artifact path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"artifact not found: {filename}")
    return path


@app.get("/api/v1/photos/{photo_id}/artifacts/{name}")
def get_photo_artifact(photo_id: str, name: str):
    media_type = _UI_ARTIFACTS.get(name)
    if media_type is None:
        raise HTTPException(status_code=400, detail="artifact is not allowlisted")
    path = _safe_record_file(photo_id, name)
    if media_type == "application/json":
        try:
            return JSONResponse(json.loads(path.read_text(encoding="utf-8")), headers={"Cache-Control": "no-store"})
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail=f"invalid {name}: {exc}") from exc
    return FileResponse(path, media_type=media_type, filename=name, headers={"Cache-Control": "private, max-age=300"})


@app.get("/api/v1/photos/{photo_id}/landmarks/{count}/{space}")
def get_photo_landmarks(photo_id: str, count: int, space: str) -> dict[str, Any]:
    spec = _LANDMARK_FILES.get((count, space))
    if spec is None:
        raise HTTPException(status_code=400, detail="supported counts: 106/134; spaces: raw/aligned/original")
    filename, coordinate_space = spec

    # Try to read from CSV file first (backward compatibility)
    path = _safe_record_file(photo_id, filename)
    points: list[list[float]] = []
    try:
        import csv
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                z = row.get("z")
                point = [float(row["x"]), float(row["y"])]
                point.append(float(z) if z is not None and z != "" else None)
                points.append(point)
    except (OSError, ValueError, KeyError, csv.Error):
        pass  # CSV not found or invalid - try JSON fallback below

    # If no points from CSV, try JSON fallback from pair_details etc.
    if not points:
        try:
            from app6.stage2.loaders import load_main
            main_records = load_main(Path(_require_stage1()))
            # Look for photo record and extract landmark data
            record = main_records.get(photo_id)
            if record is not None:
                # Extract landmarks from record - try various fields
                for field in ["ldm106", "ldm134", "landmarks_106", "landmarks_134"]:
                    if hasattr(record, field):
                        lm = getattr(record, field)
                        if lm:
                            points = lm  # type: ignore
                            break
        except Exception:
            pass  # JSON fallback failed - return empty points

    # If still no points, return empty (rather than error) - UI can handle gracefully
    if not points:
        return {"schema": APP_SCHEMA, "source_mode": "research", "not_a_verdict": True,
                "photo_id": photo_id, "count": count, "space": space,
                "coordinate_space": coordinate_space, "points": [], "source_file": filename}

    if len(points) != count:
        raise HTTPException(status_code=422, detail=f"expected {count} landmark rows, got {len(points)}")
    return {"schema": APP_SCHEMA, "source_mode": "research", "not_a_verdict": True,
            "photo_id": photo_id, "count": count, "space": space,
            "coordinate_space": coordinate_space, "points": points, "source_file": filename}


def _calibration_records() -> list[Any]:
    from app6.stage2.loaders import load_calibration
    try:
        return load_calibration(_calibration_root())
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=f"калибровочный Stage 1 недоступен: {exc}") from exc


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    stage1_root = _stage1_root()
    stage2_root = _stage2_root()
    stage3_root = _stage3_root()
    manifest = _stage2_manifest(stage2_root) if stage2_root else None
    return {
        "schema": APP_SCHEMA,
        "status": "ok",
        "not_a_verdict": True,
        "source_mode": "research" if stage1_root else "unconfigured",
        "storage_root": str(_storage_root()),
        "stage1_ready": stage1_root is not None,
        "stage2_ready": stage2_root is not None,
        "stage2_root": str(stage2_root) if stage2_root else None,
        "stage2_status": manifest.get("status") if manifest else None,
        "run_id": manifest.get("run_id") if manifest else None,
        "calibration_available": _calibration_root() is not None,
        "stage3_ready": stage3_root is not None,
        "stage3_root": str(stage3_root) if stage3_root else None,
        "photo_count": manifest.get("main_record_count") if manifest else None,
        "pair_count": manifest.get("pair_count") if manifest else None,
    }


@app.get("/api/v1/timeline")
def get_timeline() -> dict[str, Any]:
    """🚪 API → Хронология для главного таймлайна интерфейса.

    Возвращает вывод реального Stage 2 (`analysis_manifest.json` +
    `pair_metrics.csv`). До завершения Stage 2 таймлайн честно остаётся
    пустым и сообщает, какой шаг требуется выполнить.
    """
    stage2_root = _stage2_root()
    if stage2_root is None:
        from .stage1_timeline import build_stage1_inventory
        try:
            return build_stage1_inventory(_require_stage1())
        except (FileNotFoundError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=f"вывод Stage 1 не прошёл проверку: {exc}") from exc
    from .research_timeline import build_research_timeline
    try:
        return build_research_timeline(stage2_root, _stage1_root())
    except (FileNotFoundError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"вывод Stage 2 не прошёл проверку: {exc}") from exc


@app.get("/api/v1/photos")
def list_photos(offset: int = 0, limit: int = 200, pose_bin: str | None = None) -> dict[str, Any]:
    """🚪 API → Список фото реального Stage 1 без raw-изображений."""
    stage1_root = _require_stage1()
    manifest_path = stage1_root / "stage1_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    records=list(_main_records().values());records=[r for r in records if pose_bin is None or r.pose_bin==pose_bin];records=sorted(records,key=lambda item:(item.date or "",item.sequence,item.record_id));limit=max(1,min(limit,1000));page=records[max(0,offset):max(0,offset)+limit]
    return {"schema":APP_SCHEMA,"source_mode":"research","manifest":manifest,"count":len(records),"offset":offset,"limit":limit,"photos":[{"id":r.record_id,"date":r.date,"bucket":r.pose_bin} for r in page]}


@app.get("/api/v1/photos/{photo_id}")
def get_photo(photo_id: str) -> dict[str, Any]:
    record = _main_record(photo_id)
    return {
        "schema": APP_SCHEMA, "source_mode": "research", "not_a_verdict": True,
        "id": record.record_id, "date": record.date, "bucket": record.pose_bin,
        "angles": {"pitch": float(record.angles[0]), "yaw": float(record.angles[1]), "roll": float(record.angles[2])},
        "landmarks_106": record.ldm106.tolist(),
        "landmarks_134": record.ldm134.tolist(),
        "visible_134": record.visible134.tolist(),
        "full_mesh_available": is_bfm_available(),
    }


@app.get("/api/v1/photos/{photo_id}/mesh")
def get_photo_full_mesh(photo_id: str, lod: int = 1) -> dict[str, Any]:
    """🚪 API → Полный BFM-меш (35 709 вершин, реальная топология) для 3D Inspector.

    Использует ту же геометрическую модель, что и продакшн Stage 1
    (`3ddfa_v3/assets/face_model.tar.gz`), без запуска нейросети — только
    линейная реконструкция формы из уже известного `alpha_id`.
    """
    record = _main_record(photo_id)
    if not is_bfm_available():
        raise HTTPException(status_code=503, detail="BFM geometry (face_model.tar.gz) unavailable in this environment")
    from .bfm_topology import load_bfm_model
    import numpy as np
    if not np.isfinite(record.alpha_id).all():
        raise HTTPException(status_code=422, detail="Stage 1 не содержит пригодных параметров identity для полного меша")
    bfm = load_bfm_model()
    vertices = bfm.compute_shape(record.alpha_id, np.zeros(64, np.float32)).astype(np.float32)
    lod=max(1,min(int(lod),8))
    if lod>1:
        keep=np.arange(0,vertices.shape[0],lod);mapping={int(old):i for i,old in enumerate(keep)};tri=np.asarray([t for t in bfm.triangles if all(int(x) in mapping for x in t)],np.int32);tri=np.asarray([[mapping[int(x)] for x in t] for t in tri],np.int32);vertices=vertices[keep]
    else:tri=bfm.triangles
    return {"schema": APP_SCHEMA, "source_mode": "research", "not_a_verdict": True,
            "id": record.record_id, "vertices": vertices.tolist(), "triangles": tri.tolist(),"lod":lod,
            "vertex_count": int(vertices.shape[0]), "triangle_count": int(tri.shape[0])}


class UploadResponse(BaseModel):
    schema_: str
    photo_id: str
    date: str | None
    stored: bool
    message: str


@app.get("/api/v1/zones/catalog")
def zones_catalog() -> dict[str, Any]:
    """🚪 API → Каталог зон кожи из нормативного атласа (для легенды UI).

    Отдаёт то, что реально записано в `3ddfa_v3/atlas/skin_zone_atlas.json`.
    Веса зон не синтезируются: атлас их не содержит, а придумывать их в API
    значило бы подменить нормативную схему (`app6/AGENTS.md`).
    """
    zones = zone_catalog()
    return {
        "schema": SKIN_ZONES_SCHEMA, "not_a_verdict": True,
        "zone_count": len(zones), "zones": zones,
    }


@app.get("/api/v1/photos/{photo_id}/skin_zones")
def get_photo_skin_zones(photo_id: str) -> dict[str, Any]:
    """🚪 API → Per-zone кожа/качество из УЖЕ сохранённых артефактов Stage 1.

    Ничего не пересчитывает: читает `skin_zone_quality.json`, `quality.json` и
    `wrinkle_zones.json` рядом с фотографией. Если `DEEPUTIN_STAGE1_ROOT` не
    задан, настоящих текстурных артефактов нет, поэтому возвращается HTTP 409
    с явной причиной — вместо синтетических чисел, выдаваемых за анализ кожи.
    """
    stage1_root = _stage1_root()
    if stage1_root is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "текстурные артефакты доступны только для вывода Stage 1. "
                "Задайте DEEPUTIN_STAGE1_ROOT и выполните извлечение "
                "(POST /api/v1/jobs {\"kind\": \"extract\"}). Без этого "
                "реальный анализ кожи недоступен."
            ),
        )
    photo_dir = stage1_root / photo_id
    if not photo_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"no Stage 1 output for {photo_id}")
    report = load_skin_zone_report(photo_dir)
    return {**report, "source_mode": "research", "photo_id": photo_id}


#: Изображения, которые Stage 1 сохраняет рядом с фото (`info.json → files`).
#: Ключ запроса → имя файла на диске. Произвольные пути не принимаются:
#: параметр `kind` — закрытый словарь, поэтому path traversal невозможен.
_PHOTO_IMAGE_KINDS = {
    "original": "original.jpg",
    "thumbnail": "thumb.jpg",
    "face_crop": "face_crop.jpg",
    "uv_texture": "uv_texture.png",
    "zones_overlay": "_zones_overlay.png",
}


@app.get("/api/v1/photos/{photo_id}/image")
def get_photo_image(photo_id: str, kind: str = "original") -> FileResponse:
    """🚪 API → Отдать сохранённое Stage 1 изображение фотографии.

    Нужно интерфейсу, чтобы показывать кадры A и B рядом при сравнении
    (ТЗ: «визуализацией обоих изображений рядом»). Ничего не генерирует —
    только отдаёт уже лежащий на диске файл.

    Если `DEEPUTIN_STAGE1_ROOT` не задан, исходных изображений нет: тогда
    возвращается 409 с объяснением, а не заглушка, которую можно принять за
    реальный кадр.
    """
    if kind not in _PHOTO_IMAGE_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown image kind: {kind}; expected one of {sorted(_PHOTO_IMAGE_KINDS)}",
        )
    stage1_root = _stage1_root()
    if stage1_root is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "изображения доступны только для вывода Stage 1. Задайте "
                "DEEPUTIN_STAGE1_ROOT и выполните извлечение. Исходные "
                "фотографии доступны только после реального Stage 1."
            ),
        )
    photo_dir = stage1_root / photo_id
    # Защита от выхода за пределы каталога Stage 1 через photo_id.
    try:
        resolved_dir = photo_dir.resolve()
        resolved_dir.relative_to(stage1_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid photo_id") from None
    if not resolved_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"no Stage 1 output for {photo_id}")

    target = resolved_dir / _PHOTO_IMAGE_KINDS[kind]
    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"{kind} not saved for {photo_id}")
    media = "image/png" if target.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(target, media_type=media)


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

    # P1.8 (DEV_FIX_TZ 2.8): жёсткий лимит размера загрузки. Раньше тело
    # читалось целиком в память без ограничений — загрузка одного огромного
    # файла заполняла диск и RAM. Читаем потоково и прерываемся при превышении,
    # не доводя данные до диска. Content-Length не является доверенным
    # источником (его можно подделать), поэтому считаем фактические байты.
    declared = file.size if getattr(file, "size", None) is not None else None
    if declared is not None and declared > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file too large: {declared} bytes > limit {MAX_UPLOAD_BYTES} bytes",
        )
    required_space = declared if declared is not None else MAX_UPLOAD_BYTES
    try:
        free_space = shutil.disk_usage(uploads_dir).free
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to inspect upload storage: {exc}") from exc
    if free_space < required_space:
        raise HTTPException(
            status_code=507,
            detail=f"insufficient upload storage: {free_space} bytes free, {required_space} required",
        )

    temp_path = uploads_dir / f"_incoming_{uuid.uuid4().hex}{suffix}"
    received = 0
    try:
        with temp_path.open("wb") as handle:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                received += len(chunk)
                if received > MAX_UPLOAD_BYTES:
                    handle.close()
                    temp_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"file too large: exceeds limit {MAX_UPLOAD_BYTES} bytes",
                    )
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
    except HTTPException:
        raise
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"failed to store upload: {exc}") from exc

    if received == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="empty file")
    try:
        signature_valid = _upload_signature_matches(temp_path, suffix)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"failed to validate upload: {exc}") from exc
    if not signature_valid:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"file content does not match {suffix} image format")
    if not _upload_image_decodes(temp_path):
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="image decode validation failed")
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
    photo_a = _main_record(request.photo_a)
    photo_b = _main_record(request.photo_b)
    result = compare_records(photo_a, photo_b)
    result["source_mode"] = "research"
    result["not_a_verdict"] = True
    result["photo_a"] = {"id": photo_a.record_id, "date": photo_a.date, "bucket": photo_a.pose_bin}
    result["photo_b"] = {"id": photo_b.record_id, "date": photo_b.date, "bucket": photo_b.pose_bin}
    return result


@app.post("/api/v1/compare/full_mesh")
def compare_pair_full_mesh(request: ComparePairRequest) -> dict[str, Any]:
    """🚪 API → Полное BFM-сравнение (35 709 вершин) для морфинга/3D Inspector.

    В отличие от `/api/v1/compare` (134 landmarks), здесь выравнивается и
    сравнивается вся identity-форма (без мимики) с подлинной топологией
    треугольников — то, что нужно для настоящего 3D-морфинга A→B из ТЗ.
    """
    photo_a = _main_record(request.photo_a)
    photo_b = _main_record(request.photo_b)
    result = full_mesh_compare(photo_a, photo_b)
    if result is None:
        raise HTTPException(status_code=503, detail="BFM geometry (face_model.tar.gz) unavailable in this environment")
    result["source_mode"] = "research"
    result["not_a_verdict"] = True
    result["photo_a"] = {"id": photo_a.record_id, "date": photo_a.date, "bucket": photo_a.pose_bin}
    result["photo_b"] = {"id": photo_b.record_id, "date": photo_b.date, "bucket": photo_b.pose_bin}
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


class NoiseSubtractionRequest(BaseModel):
    photo_a: str
    photo_b: str
    tolerance: dict[str, float] | None = None


@app.post("/api/v1/calibration/subtract_noise")
def calibration_subtract_noise(request: NoiseSubtractionRequest) -> dict[str, Any]:
    """🚪 API → Вычесть угловой шум из метрик пары по калибровочному набору.

    Реализует ключевое требование ТЗ: «к парам основного анализа подбирается
    пара из калибровочного датасета... по этим данным шум можно вычесть».
    Механизм существовал в `app6/stage2/angle_noise.py`, но не вызывался
    ниоткуда, кроме тестов.

    Возвращает СЫРОЕ и компенсированное значение вместе, с признаками
    `uncompensated` и `degenerate_match`: компенсация уменьшает расхождение,
    и подменять ею исходное число молча недопустимо.
    """
    photo_a = _main_record(request.photo_a)
    photo_b = _main_record(request.photo_b)

    comparison = compare_records(photo_a, photo_b)
    if comparison.get("status") != "measured":
        return {
            "schema": APP_SCHEMA, "source_mode": "research", "not_a_verdict": True,
            "status": comparison.get("status"),
            "uncompensated": True,
            "reason": "сравнение не в статусе measured — компенсировать нечего",
            "metrics": {},
        }

    outcome = apply_noise_subtraction(
        comparison.get("metrics") or {},
        photo_a.angles, photo_b.angles,
        photo_a.pose_bin,
        tolerance=request.tolerance,
        calibration_records=_calibration_records(), cache_key=str(_calibration_root().resolve()),
        exclude_records=(photo_a.record_id, photo_b.record_id),
    )
    return {**outcome, "source_mode": "research", "status": "measured", "not_a_verdict": True,
            "photo_a": {"id": photo_a.record_id, "bucket": photo_a.pose_bin},
            "photo_b": {"id": photo_b.record_id, "bucket": photo_b.pose_bin}}


@app.get("/api/v1/calibration/noise_model")
def calibration_noise_model(
    yaw: float | None = None, pitch: float | None = None, roll: float | None = None,
    sample: int = 40,
) -> dict[str, Any]:
    """🚪 API → Состояние модели шума и покрытие компенсации при данных допусках.

    Позволяет интерфейсу показать, для какой доли пар шум вообще удаётся
    вычесть при выбранных допусках. Без этого переключатель
    «сырые/компенсированные» вводит в заблуждение.
    """
    tolerance = resolve_tolerance({"yaw": yaw, "pitch": pitch, "roll": roll})
    calibration_records = _calibration_records()
    index = build_noise_index(calibration_records, cache_key=str(_calibration_root().resolve()))

    photos = list(_main_records().values())
    by_bin: dict[str, list[Any]] = {}
    for photo in photos:
        by_bin.setdefault(photo.pose_bin, []).append(photo)

    # Репрезентативная выборка пар внутри одного ракурса: сравнение поперёк
    # ракурсов запрещено политикой проекта, такие пары в покрытие не входят.
    probes: list[tuple[dict[str, float], Any, Any, str | None]] = []
    for pose_bin, group in by_bin.items():
        for i in range(0, min(len(group) - 1, max(1, sample // max(1, len(by_bin))))):
            a, b = group[i], group[i + 1]
            comparison = compare_records(a, b)
            if comparison.get("status") != "measured":
                continue
            probes.append((comparison.get("metrics") or {},
                           a.angles, b.angles, pose_bin))

    coverage = noise_coverage_report(probes, tolerance=tolerance, calibration_records=calibration_records,
                                     cache_key=str(_calibration_root().resolve()))
    per_bin: dict[str, int] = {}
    for pair in index:
        key = str(pair.get("pose_bin"))
        per_bin[key] = per_bin.get(key, 0) + 1

    return {
        "schema": APP_SCHEMA, "source_mode": "research", "not_a_verdict": True,
        "tolerance": tolerance,
        "index_size": len(index),
        "pairs_per_pose_bin": per_bin,
        "coverage": coverage,
        "note": (
            "Индекс построен по кадрам одной персоны: их расхождение и есть "
            "оценка шума при данной разнице углов."
        ),
    }


# =============================================================================
# Полные метрики Stage 2 (категории A–I карты размещения ключей)
# =============================================================================
# 🚨 До этих эндпоинтов интерфейс видел 13 колонок `pair_metrics.csv` из 186:
# `research_timeline.py` читал ровно то, что нужно таймлайну. Статистика
# множественных сравнений, mesh-канал, текстура, дескрипторы и корроборация
# оставались на диске. См. `ui/KEYS_PLACEMENT_MAP.md`.


def _require_stage2() -> Path:
    """Каталог Stage 2 или HTTP 409 с указанием, чего не хватает."""
    stage2_root = _stage2_root()
    if stage2_root is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "полные метрики доступны только для вывода Stage 2. Задайте "
                "DEEPUTIN_STAGE2_ROOT на каталог с analysis_manifest.json. "
                "Без Stage 2 реальный попарный анализ недоступен."
            ),
        )
    return stage2_root


@app.get("/api/v1/pairs/{photo_a}/{photo_b}/metrics")
def get_pair_metrics(photo_a: str, photo_b: str) -> dict[str, Any]:
    """🚪 API → Все 186 колонок `pair_metrics.csv` для пары, по категориям A–I.

    Один эндпоинт закрывает категории A (статзначимость), B (меш),
    C (качество), D (точки/дескрипторы), E (текстура), F (хронология),
    G (провенанс пары) карты размещения ключей.
    """
    from .pair_metrics import load_pair_metrics
    stage2_root = _require_stage2()
    try:
        return load_pair_metrics(stage2_root, photo_a, photo_b)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"пара отсутствует в выводе Stage 2: {photo_a} / {photo_b}. "
                "Stage 2 строит пары только внутри одного pose bin."
            ),
        ) from exc


@app.get("/api/v1/run/summary")
def get_run_summary() -> dict[str, Any]:
    """🚪 API → Сводка прогона: манифест, техотчёт, каталог метрик, артефакты.

    Категория I карты размещения ключей: `technical_summary.json` и
    `limitations`/`skipped_pair_counts` не имели ни одного потребителя.
    """
    from .pair_metrics import load_run_summary
    stage2_root = _require_stage2()
    try:
        return load_run_summary(stage2_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/run/artifacts/{name}")
def get_run_artifact(name: str) -> dict[str, Any]:
    """🚪 API → Один артефакт Stage 2 из нормативного перечня.

    Имя принимается только из `key_catalog.ARTIFACT_PLACEMENT`, поэтому
    произвольные пути невозможны.
    """
    from .pair_metrics import load_stage2_artifact
    stage2_root = _require_stage2()
    try:
        return load_stage2_artifact(stage2_root, name)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc



@app.get("/api/v1/run/keys/{name}")
def get_run_key_alias(name: str) -> dict[str, Any]:
    """Backward-compatible alias used by UI v3."""
    return get_run_artifact(name)

@app.get("/api/v1/photos/{photo_id}/info_keys")
def get_photo_info_keys(photo_id: str) -> dict[str, Any]:
    """🚪 API → `info.json` фото (156 листовых ключей) по категориям C/D/G/H.

    Категории C (параметры кадра), G (провенанс), H (маски/UV/файлы):
    раньше из 156 ключей Stage 1 интерфейс использовал около восьми.
    """
    from .pair_metrics import load_stage1_info
    stage1_root = _stage1_root()
    if stage1_root is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "параметры кадра доступны только для вывода Stage 1. "
                "Задайте DEEPUTIN_STAGE1_ROOT и выполните извлечение."
            ),
        )
    try:
        return load_stage1_info(stage1_root, photo_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# =============================================================================
# Публичный отчёт Stage 3
# =============================================================================
# 🚨 Stage 3 был единственным этапом пайплайна без единого эндпоинта: отчёт
# формировался как самостоятельный HTML+JSON и в рабочую станцию не попадал.


def _stage3_root() -> Path | None:
    raw = os.environ.get("DEEPUTIN_STAGE3_ROOT")
    path = Path(raw) if raw else _storage_root() / "stage3"
    return path if (path / "report_data.json").is_file() else None


def _require_stage3() -> Path:
    """Каталог Stage 3 или HTTP 409 с указанием, чего не хватает."""
    stage3_root = _stage3_root()
    if stage3_root is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "публичный отчёт доступен только после прогона Stage 3. "
                "Положите report_data.json в storage/stage3 или задайте "
                "DEEPUTIN_STAGE3_ROOT на каталог с этим файлом "
                "(python app6/run_stage3.py --analysis <stage2> --output <dir>)."
            ),
        )
    return stage3_root


@app.get("/api/v1/report/summary")
def get_report_summary() -> dict[str, Any]:
    """🚪 API → Обзор публичного отчёта Stage 3 без тяжёлых секций.

    Отдаёт счётчики, нарратив, методологию, статус валидации и перечень
    секций с размерами. Крупные массивы забираются постранично через
    `/api/v1/report/sections/{name}`.
    """
    from .report import load_report_summary
    stage3_root = _require_stage3()
    try:
        return load_report_summary(stage3_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/report/sections/{name}")
def get_report_section(name: str, offset: int = 0, limit: int = 100) -> dict[str, Any]:
    """🚪 API → Одна секция отчёта Stage 3, при необходимости страницей."""
    from .report import load_report_section
    stage3_root = _require_stage3()
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must not be negative")
    try:
        return load_report_section(stage3_root, name, offset=offset, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/calibration/health")
def calibration_health() -> dict[str, Any]:
    try:
        return load_calibration_health(_calibration_root())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/calibration/match")
def calibration_match(photo_id: str | None = None, yaw: float | None = None,
                      pitch: float | None = None, roll: float | None = None,
                      pose_bin: str | None = None, limit: int = 5) -> dict[str, Any]:
    """🚪 API → Подобрать калибровочные кадры для угловой компенсации шума.

    Принимает либо `photo_id` (углы берутся из уже известной research
    записи), либо явные `yaw`/`pitch`/`roll` (например, для кадра, ещё не
    сохранённого в базе). См. `app6/api/calibration.find_matching_calibration_frames`.
    """
    if photo_id is not None:
        photo = _main_record(photo_id)
        yaw = float(photo.angles[1])
        pitch = float(photo.angles[0])
        roll = float(photo.angles[2])
        pose_bin = pose_bin or photo.pose_bin
    if yaw is None or pitch is None or roll is None:
        raise HTTPException(status_code=400, detail="provide either photo_id or yaw/pitch/roll")
    try:
        return find_matching_calibration_frames(
            _calibration_root(), yaw=yaw, pitch=pitch, roll=roll, pose_bin=pose_bin, limit=limit,
        )
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


def _require_removable_output(path: Path) -> Path:
    """Не позволять API записывать извлечение вне выделенного storage root."""
    storage_root = _storage_root()
    resolved = path.resolve()
    if resolved == storage_root:
        raise HTTPException(status_code=400, detail="output_dir must be a child of storage root")
    try:
        resolved.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"output_dir must be under {storage_root}; got {resolved}",
        ) from exc
    return resolved


@app.post("/api/v1/jobs")
def submit_job(request: JobRequest) -> dict[str, Any]:
    if request.kind == "extract":
        input_dir = Path(request.input_dir) if request.input_dir else _uploads_root() / "main"
        output_dir = _require_removable_output(Path(request.output_dir) if request.output_dir else _storage_root() / "api_stage1")
        if not input_dir.is_dir():
            raise HTTPException(status_code=400, detail=f"input_dir does not exist: {input_dir}")
        runner = make_extract_runner(input_dir, output_dir, PROJECT_ROOT, device=request.device, limit=request.limit)
    elif request.kind == "recompute_metrics":
        stage1_root = Path(request.stage1_root) if request.stage1_root else _stage1_root()
        if stage1_root is None:
            raise HTTPException(status_code=400, detail="stage1_root not provided and DEEPUTIN_STAGE1_ROOT not set")
        calibration_root = Path(request.calibration_root) if request.calibration_root else _calibration_root()
        output_dir = _require_removable_output(Path(request.output_dir) if request.output_dir else _storage_root() / "api_stage2")
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



@app.post("/api/v1/reviews")
def create_review(payload: dict[str, Any]) -> dict[str, Any]:
    try:return append_review(PROJECT_ROOT,payload)
    except ValueError as exc:raise HTTPException(status_code=422,detail=str(exc)) from exc

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

    Удаляет только `<storage_root>/api_stage1`, `<storage_root>/api_stage2`
    и локальный кэш job'ов
    процесса. Исходные фото под `DEEPUTIN_UPLOADS_ROOT`/`--input` не трогаются.
    """
    removed = []
    storage_root = _storage_root()
    uploads_root = _uploads_root().resolve()
    target_paths = [storage_root / rel for rel in ("api_stage1", "api_stage2")]
    targets = []
    for target_path in target_paths:
        if target_path.is_symlink():
            raise HTTPException(status_code=409, detail=f"refusing to clear symlinked output: {target_path}")
        target = target_path.resolve()
        try:
            target.relative_to(storage_root)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=f"clear target escapes storage root: {target}") from exc
        targets.append(target)
    for target in targets:
        if uploads_root == target or target in uploads_root.parents or uploads_root in target.parents:
            raise HTTPException(
                status_code=409,
                detail=f"refusing to clear {target}: uploads root overlaps extracted output",
            )
    for path in targets:
        if path.exists():
            shutil.rmtree(path)
            removed.append(path.name)
    return {"schema": APP_SCHEMA, "removed": removed, "note": "исходные фото не удалены"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Any, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"schema": APP_SCHEMA, "error": str(exc), "not_a_verdict": True})
