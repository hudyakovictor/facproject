import asyncio, base64, csv, io, json, os, time
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated
import numpy as np
import yaml
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from server.config import ROOT, CONFIG, ASSETS, atomic_json, profiles, save_profiles
from server import storage, registry, analysis, chart
from server.jobs import queue
from server.models.tddfa import availability, get_model
from server.rendering import export_morph, rasterize, colorize
from server.heat import (
    compute_heat_values,
    resolve as heat_resolve,
    segment_values,
    space_array as metric_array,
)


@asynccontextmanager
async def lifespan(app):
    registry.discover()
    yield


app = FastAPI(title="ATLAS · Face Workbench", version="0.1.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=2000, compresslevel=3)


def model_settings():
    p = ROOT / "data/model_settings.json"
    return json.loads(p.read_text()) if p.exists() else {"3ddfa_v3": True}


def find_photo(id):
    try:
        return storage.photo(id)
    except KeyError:
        raise HTTPException(404, "Фото не найдено")


@lru_cache(maxsize=1)
def topology_data():
    p = ROOT / "data/topology.json"
    if not p.exists():
        topo = get_model().topology()
        p.write_text(json.dumps(topo, separators=(",", ":")))
    data = json.loads(p.read_text())
    if "uv" not in data and (ASSETS / "face_model.npy").exists():
        from server.models.tddfa import get_model

        data["uv"] = get_model().basis["uv_coords"][:, :2].round(7).tolist()
        atomic_json(p, data)
    return data


@app.get("/api/health")
def health():
    import imageio_ffmpeg
    from server.ocular import availability as ocular_availability

    return {
        "ok": True,
        "version": "0.1.0",
        "cpu": os.cpu_count(),
        "seed": 42,
        "ffmpeg": Path(imageio_ffmpeg.get_ffmpeg_exe()).exists(),
        "mediapipe": ocular_availability(),
    }


@app.get("/api/models")
def models():
    actual = availability()
    actual["enabled"] = model_settings().get("3ddfa_v3", True) and actual["available"]
    from server.ocular import availability as ocular_availability

    mp = ocular_availability()
    return [actual, mp] + [
        {
            "id": id,
            "title": title,
            "available": False,
            "enabled": False,
            "reason": "Не установлена · следующий этап",
        }
        for id, title in [
            ("fan", "FAN"),
            ("adaface", "AdaFace"),
        ]
    ]


@app.put("/api/models/3ddfa_v3")
def set_model(data: dict = Body(...)):
    settings = model_settings()
    settings["3ddfa_v3"] = bool(data.get("enabled", True))
    atomic_json(ROOT / "data/model_settings.json", settings)
    return settings


@app.get("/api/library")
def library():
    ps = storage.library()
    seconds = [p["meta"]["seconds"] for p in ps if p["meta"]]
    for p in ps:
        err = ROOT / "cache" / p["id"] / "error.json"
        if err.exists():
            p["error"] = json.loads(err.read_text())["error"]
    return {
        "photos": ps,
        "groups": sorted(set(p["group"] for p in ps)),
        "seconds_per_photo": round(float(np.mean(seconds)), 3) if seconds else None,
        "jobs": queue.list(),
    }


@app.post("/api/library/trash")
def trash_library(data: dict = Body(...)):
    """Корзины нет: удаление стирает запись, исходник, кэш и экспорты."""
    ids = data.get("photo_ids", [])
    if data.get("demo_only"):
        ids = [
            p["id"]
            for p in storage.read_db()["photos"]
            if p.get("demo") and not p.get("deleted_at")
        ]
    if not isinstance(ids, list) or len(ids) > 5000:
        raise HTTPException(400, "Некорректный список фото")
    try:
        return storage.purge_photos(ids)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/library/trash")
def list_trash():
    """Оставлено для совместимости: удалённые фото нигде не хранятся."""
    return {"photos": []}


@app.post("/api/library/restore")
def restore_library(data: dict = Body(...)):
    raise HTTPException(410, "Восстановление недоступно: удаление необратимо")


@app.post("/api/upload")
async def upload(
    files: Annotated[list[UploadFile], File()],
    group: Annotated[str, Form()] = "Моя группа",
    precropped: Annotated[bool, Form()] = False,
):
    items = []
    total = 0
    try:
        for f in files:
            content = await f.read(100 * 1024 * 1024 + 1)
            total += len(content)
            if total > 100 * 1024 * 1024:
                raise ValueError("Лимит загрузки за раз — 100 МБ")
            items += (
                storage.unpack_zip(content)
                if (f.filename or "").lower().endswith(".zip")
                else [(f.filename or "photo.jpg", content)]
            )
        # Повторная загрузка удалённого файла даёт ту же запись заново:
        # старый кэш стёрт при удалении, поэтому ingest запускает полный
        # цикл реконструкции, а не отдаёт готовые features.
        ids = storage.ingest(items, group, precropped)
        if not ids:
            return {"added": 0, "message": "Нет новых изображений", "job": None}
        enabled = model_settings().get("3ddfa_v3", True)
        ready = availability()["available"]
        job = (
            queue.submit("process", lambda j: storage.process(j, ids), {"ids": ids})
            if enabled and ready
            else None
        )
        reason = None if job else (
            availability().get("reason") if not ready else "Плагин 3DDFA_V3 выключен"
        )
        return {"added": len(ids), "job": job, "reason": reason}
    except (ValueError, OSError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/process")
def process(data: dict = Body(default={})):
    if not model_settings().get("3ddfa_v3", True):
        raise HTTPException(409, "Плагин 3DDFA_V3 выключен")
    if not availability()["available"]:
        raise HTTPException(503, availability()["reason"])
    ids = data.get("photo_ids")
    if ids is not None:
        if not isinstance(ids, list) or len(ids) > 500 or any(not isinstance(x, str) for x in ids):
            raise HTTPException(400, "Некорректный список фото")
        if len(set(ids)) != len(ids):
            raise HTTPException(400, "Список фото содержит повторы")
        active = {p["id"] for p in storage.library()}
        if set(ids) - active:
            raise HTTPException(400, "Список содержит неизвестные или удалённые фото")
    return queue.submit("process", lambda j: storage.process(j, ids), {"ids": ids})


@app.post("/api/scan")
def scan():
    db = storage.read_db()
    known = {str((ROOT / p["path"]).resolve()) for p in db["photos"]}
    items = []
    for p in (ROOT / "data/groups").rglob("*"):
        if (
            p.is_file()
            and p.suffix.lower() in storage.EXT
            and p.stat().st_size <= 30 * 1024 * 1024
            and str(p.resolve()) not in known
        ):
            items.append((p.parent.name + "/" + p.name, p.read_bytes()))
    ids = storage.ingest(items) if items else []
    if not model_settings().get("3ddfa_v3", True) or not availability()["available"]:
        return {
            "added": len(ids),
            "job": None,
            "reason": "Модель выключена или недоступна",
        }
    return {
        "added": len(ids),
        "job": queue.submit("process", lambda j: storage.process(j), {}),
    }


@app.patch("/api/photos/{id}")
def patch_photo(id: str, data: dict = Body(...)):
    find_photo(id)
    try:
        return storage.update_photo(id, data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/eyes/analyze")
def analyze_eyes(data: dict = Body(...)):
    from server import ocular

    ids = data.get("photo_ids", [])
    known = {p["id"]: p for p in storage.library()}
    if (
        not isinstance(ids, list)
        or not ids
        or len(ids) > 5000
        or any(id not in known for id in ids)
    ):
        raise HTTPException(400, "Некорректный список фотографий")
    if not ocular.availability()["available"]:
        raise HTTPException(503, ocular.availability()["reason"])
    return queue.submit(
        "eyes",
        lambda j: ocular.batch(j, ids),
        {"photo_ids": ids, "model": ocular.VERSION},
    )


@app.get("/api/photos/{id}/eyes")
def eye_measure(id: str):
    from server import ocular

    try:
        photo = storage.photo(id)
        detection, _, _ = ocular.paths(photo)
        if not detection.exists():
            return {
                "id": id,
                "status": "pending",
                "message": "Измерьте текущий кадр, чтобы увидеть landmarks и радиусы глаз.",
            }
        return ocular.measure(photo)
    except FileNotFoundError:
        raise HTTPException(404, "Фото не найдено")
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.patch("/api/photos/{id}/eye-annotations")
def eye_annotations(id: str, data: dict = Body(...)):
    from server import ocular

    try:
        return ocular.annotate(storage.photo(id), data)
    except FileNotFoundError:
        raise HTTPException(404, "Сначала создайте автоматическую разметку")
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/eyes/report")
def eyes_report(group: str = "__all"):
    from server.ocular import report

    return report(group)


@app.get("/api/eyes/report.csv")
def eyes_csv(group: str = "__all"):
    from server.ocular import report

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "id",
            "name",
            "group",
            "date",
            "eligible",
            "reviewed",
            "quality_flags",
            "yaw",
            "pitch",
            "roll",
            *[m[0] for m in __import__("server.ocular", fromlist=["CATALOG"]).CATALOG],
        ]
    )
    for r in report(group)["rows"]:
        writer.writerow(
            [r[k] for k in ["id", "name", "group", "date", "eligible", "reviewed"]]
            + [" | ".join(r["exclusion_reasons"])]
            + [r["angles"].get(k) for k in ["yaw", "pitch", "roll"]]
            + [
                r["metrics"][m[0]]
                for m in __import__("server.ocular", fromlist=["CATALOG"]).CATALOG
            ]
        )
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8")


@app.get("/api/calibration/noise")
def get_noise_calibration():
    from server.calibration import load_noise
    return load_noise() or {"calibrated": False}


@app.post("/api/calibration/noise")
def create_noise_calibration(payload: dict = Body(...)):
    from server.calibration import calculate_noise
    participants = payload.get("participants", [])
    def load_mesh(photo_id):
        p = find_photo(photo_id)
        if p.get("status") != "ready":
            raise ValueError(f"Фото {p.get('name', photo_id)} ещё не обработано")
        feats = storage.load_features(p, ["vertices"])
        return feats["vertices"]
    try:
        result = calculate_noise(participants, load_mesh)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(400, str(exc))
    return result


@app.get("/api/photos/{id}/image")
def image(id: str):
    return FileResponse(ROOT / find_photo(id)["path"])


@app.get("/api/photos/{id}/thumbnail")
def thumb(id: str):
    find_photo(id)
    return FileResponse(ROOT / "cache" / id / "thumb.jpg", media_type="image/jpeg")


@app.get("/api/photos/{id}/aligned")
def aligned(id: str):
    find_photo(id)
    p = ROOT / "cache" / id / "aligned.jpg"
    if not p.exists():
        raise HTTPException(404, "Фото ещё не обработано")
    return FileResponse(p, media_type="image/jpeg")


@app.get("/api/photos/{id}/texture")
def photo_texture(id: str):
    p = find_photo(id)
    from PIL import Image, ImageOps
    import io

    image = ImageOps.exif_transpose(Image.open(ROOT / p["path"])).convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=97, subsampling=0, optimize=True)
    return Response(
        buf.getvalue(),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600", "ETag": p["hash"]},
    )


@app.get("/api/photos/{id}/uv-texture")
def baked_uv_texture(id: str):
    """Canonical 3DDFA UV atlas baked from source-photo pixels (not a per-vertex
    image-space UV override). Cached by photo features and UV baker version.
    """
    p = find_photo(id)
    feature = storage.feature_path(p)
    if not feature.exists():
        raise HTTPException(409, "Фото ещё не обработано")
    from PIL import Image, ImageOps
    from server.uv_texture import UV_BAKER_VERSION, bake_photo_to_uv
    cache = ROOT / "cache" / id / f"uv-atlas-{UV_BAKER_VERSION}-{storage.key_for(p)}.png"
    if not cache.exists():
        if not availability()["available"]:
            raise HTTPException(503, availability()["reason"])
        feats = storage.load_features(p, ["alpha"])
        meta = json.loads((ROOT / "cache" / id / "meta.json").read_text())
        with Image.open(ROOT / p["path"]) as im:
            rgb = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
        model = get_model()
        source_uv = model.photo_uv(feats["alpha"], rgb.shape[1], rgb.shape[0], meta["alignment"])
        atlas, _mask = bake_photo_to_uv(rgb, source_uv, model.basis["uv_coords"], model.tri, 1024)
        # Texture loading from WebGL and a simultaneous MP4 export can race on
        # a cache miss. Use a unique atomic temp file; both builders may safely
        # publish the same deterministic atlas without deleting each other's temp.
        import uuid
        tmp = cache.with_name(f"{cache.stem}.{uuid.uuid4().hex}.tmp.png")
        try:
            Image.fromarray(atlas, "RGB").save(tmp, format="PNG", optimize=True)
            tmp.replace(cache)
        finally:
            tmp.unlink(missing_ok=True)
    return FileResponse(
        cache,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=3600",
            "ETag": f'"{UV_BAKER_VERSION}-{storage.key_for(p)}"',
        },
    )


@app.get("/api/photos/{id}/photo-uv")
def photo_uv(id: str):
    p = find_photo(id)
    feature = storage.feature_path(p)
    if not feature.exists():
        raise HTTPException(409, "Фото ещё не обработано")
    import hashlib

    path = ROOT / "cache" / id / f"photo-uv-{storage.key_for(p)}.npy"
    if path.exists():
        raw = path.read_bytes()
    else:
        if not availability()["available"]:
            raise HTTPException(503, availability()["reason"])
        f = storage.load_features(p, ["alpha"])
        meta = json.loads((ROOT / "cache" / id / "meta.json").read_text())
        from PIL import Image, ImageOps

        im = ImageOps.exif_transpose(Image.open(ROOT / p["path"]))
        w, h = im.size
        model = get_model()
        uv = model.photo_uv(f["alpha"], w, h, meta["alignment"])
        tmp = path.with_suffix(".tmp")
        np.save(tmp, uv, allow_pickle=False)
        actual = tmp if tmp.exists() else Path(str(tmp) + ".npy")
        actual.replace(path)
        raw = path.read_bytes()
    return Response(
        raw,
        media_type="application/octet-stream",
        headers={
            "X-Vertex-Count": "35709",
            "Cache-Control": "private, no-cache",
            "ETag": storage.key_for(p),
        },
    )


@app.get("/api/photos/{id}/mesh")
def mesh(id: str):
    p = find_photo(id)
    if not storage.feature_path(p).exists():
        raise HTTPException(409, "Сначала обработайте фото")
    f = storage.load_features(p)
    arr = np.concatenate(
        [f["vertices"].ravel(), f["identity"].ravel(), f["albedo"].ravel()]
    ).astype("<f4")
    return Response(
        arr.tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Vertex-Count": str(len(f["vertices"])),
            "Cache-Control": "private, no-cache",
            "ETag": storage.key_for(p),
        },
    )


@app.get("/api/topology")
def topology():
    return topology_data()


@app.get("/api/metrics")
def metrics():
    return analysis.metrics_table()


@app.post("/api/metrics/reload")
def reload_metrics():
    try:
        return analysis.metrics_table()
    except Exception as e:
        raise HTTPException(400, "Ошибка плагина метрики: " + str(e))


@app.put("/api/metric-config")
def metric_config(data: dict = Body(...)):
    model = data.get("model")
    pose = data.get("pose")
    key = data.get("id")
    if (
        model not in ("3ddfa_v3", "mediapipe", "fan", "adaface")
        or pose not in [p["id"] for p in profiles()["profiles"]]
        or key not in registry.REGISTRY
    ):
        raise HTTPException(400, "Неизвестная метрика или профиль")
    path = CONFIG / "metrics" / model / f"{pose}.yaml"
    doc = yaml.safe_load(path.read_text())
    m = next((m for m in doc["metrics"] if m["id"] == key), None)
    if m is None:
        m = {"id": key}
        doc["metrics"].append(m)
    if "enabled" in data:
        m["enabled"] = bool(data["enabled"])
    if "thresholds" in data:
        warn = float(data["thresholds"].get("warn", 2))
        alert = float(data["thresholds"].get("alert", 3))
        if not 0 < warn <= alert <= 20:
            raise HTTPException(400, "Пороги: 0 < warn ≤ alert ≤ 20")
        m["thresholds"] = {"warn": warn, "alert": alert}
    doc["version"] = doc.get("version", 1) + 1
    tmp = path.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
    tmp.replace(path)
    return {"ok": True, "path": str(path.relative_to(ROOT)), "version": doc["version"]}


@app.get("/api/profiles")
def pose_profiles():
    return profiles()


@app.put("/api/profiles")
def pose_profiles_put(data: dict = Body(...)):
    try:
        return save_profiles(data)
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/projection")
def projection(params: dict = Body(...)):
    ids = params.get("photo_ids", [])
    if not 2 <= len(ids) <= 500:
        raise HTTPException(400, "Нужно от 2 до 500 обработанных фото")
    if (
        params.get("method", "pca") not in ("pca", "umap", "tsne")
        or params.get("distance", "cosine") not in ("cosine", "euclidean")
        or params.get("dimensions", 2) not in (2, 3)
    ):
        raise HTTPException(400, "Некорректные параметры проекции")
    for id in ids:
        find_photo(id)
    for key, default, lo, hi in [
        ("n_neighbors", 15, 2, 200),
        ("min_dist", 0.1, 0, 1),
        ("perplexity", 15, 1, 100),
        ("clusters", 3, 1, 30),
        ("seed", 42, 0, 999999),
    ]:
        if not lo <= float(params.get(key, default)) <= hi:
            raise HTTPException(400, "Некорректный " + key)
    return queue.submit("projection", lambda j: analysis.project(j, params), params)


@app.post("/api/morph")
def morph(params: dict = Body(...)):
    ids = params.get("photo_ids", [])
    if not 2 <= len(ids) <= 10 or len(set(ids)) != len(ids):
        raise HTTPException(400, "Выберите от 2 до 10 разных обработанных фото")
    for id in ids + ([params["reference_id"]] if params.get("reference_id") else []):
        p = find_photo(id)
        if not storage.feature_path(p).exists():
            raise HTTPException(400, "Все фото должны быть обработаны")
    if (
        not 0.2 <= float(params.get("seconds", 2)) <= 10
        or not 6 <= int(params.get("fps", 24)) <= 60
        or int(params.get("resolution", 512)) not in (256, 512, 768, 1024)
    ):
        raise HTTPException(400, "Некорректные параметры видео")
    if params.get("easing", "smooth") not in ("linear", "smooth"):
        raise HTTPException(400, "Неизвестная интерполяция")
    # Режим карты: явные параметры или дефолт из configs/runtime.yaml. Режим
    # фиксируется в задании, чтобы export не зависел от правки конфига.
    try:
        heat_mode = heat_resolve(params.get("metric"), params.get("weighting"))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(400, str(exc)) from exc
    params["weighting"] = heat_mode["weighting"]
    # Калиброванные значения живут в единицах шума, поэтому у них свой потолок.
    default_vmax = heat_mode["vmax"]
    for key, default, lo, hi in [
        ("vmin", 0, -10, 10),
        ("vmax", default_vmax, -10, 10),
        ("gamma", 1, 0.1, 5),
        ("opacity", 0.85, 0, 1),
        ("yaw", 0, -180, 180),
    ]:
        if not lo <= float(params.get(key, default)) <= hi:
            raise HTTPException(400, "Некорректный " + key)
    params["vmax"] = float(params.get("vmax", default_vmax))
    if float(params.get("vmin", 0)) >= params["vmax"]:
        raise HTTPException(400, "Верхний порог должен быть больше нижнего")
    if params.get("metric") not in (None, "distance", "identity", "normal"):
        raise HTTPException(400, "Неизвестная карта или палитра")
    if params.get("palette", "turbo") not in (
        "turbo",
        "viridis",
        "coolwarm",
        "custom",
    ):
        raise HTTPException(400, "Неизвестная карта или палитра")
    if not 0 <= int(params.get("smoothing", 0)) <= 5:
        raise HTTPException(400, "Сглаживание: 0–5")
    if params.get("palette") == "custom":
        from PIL import ImageColor

        try:
            for key in ("low", "mid", "high"):
                ImageColor.getrgb(params[key])
            if not 0.05 <= float(params.get("midPosition", 0.5)) <= 0.95:
                raise ValueError()
        except Exception:
            raise HTTPException(400, "Некорректные цветовые остановки")
    return queue.submit("morph", lambda j: export_morph(j, params), params)


def heat_space(features, lm):
    """App heat space: центр — середина средних контуров глаз, масштаб — IOD."""
    out = dict(features)
    eye = features["vertices"][lm]
    left, right = eye[36:42].mean(axis=0), eye[42:48].mean(axis=0)
    center = (left + right) / 2
    iod = max(float(np.linalg.norm(left - right)), 1e-8)
    out["vertices"] = ((features["vertices"] - center) / iod).astype(np.float32)
    out["identity"] = ((features["identity"] - center) / iod).astype(np.float32)
    if "identity_metric" in features:
        out["identity_metric"] = ((features["identity_metric"] - center) / iod).astype(np.float32)
    return out, iod


def segment_heat(a, b, r, *, tri, morphing, t, metric, weighting, smoothing):
    """(start, end, mode) для сегмента a→b с опорой на r через server/heat.py.

    Значения считает единственная реализация, поэтому preview, export и
    /api/photos/{id}/heat не могут разойтись по формуле. Для морфа
    start=|a−r|, end=|b−a|; без морфа меняется только start=|current−r|.
    """
    mode = heat_resolve(metric, weighting)
    if morphing:
        start, end = segment_values(a, b, r, tri, mode, metric_name=metric,
                                    smoothing=smoothing)
        return start, end, mode
    # Без морфа карта — расстояние текущей интерполяции до reference;
    # end здесь не используется: preview берёт только start.
    current = metric_array(a, metric) * (1 - t) + metric_array(b, metric) * t
    out = compute_heat_values(
        current, metric_array(b, metric), metric_array(r, metric), tri,
        metric=mode["metric"], weighting=mode["weighting"],
        calibration=mode["calibration"], smooth_passes=smoothing,
    )
    return out["start"], out["end"], mode


@app.get("/api/photos/{id}/heat")
def heat_values(
    id: str,
    other: str | None = None,
    reference: str | None = None,
    morphing: bool = True,
    t: float = 0,
    metric: str | None = None,
    weighting: str | None = None,
    smoothing: int = 0,
    normalizeScale: bool = False,
):
    """Start/end значения карты тем же кодом, что preview и export.

    Браузер не считает normal displacement и веса сам: он получает готовые
    значения и только раскрашивает их.
    """
    p = find_photo(id)
    if not storage.feature_path(p).exists():
        raise HTTPException(409, "Фото ещё не обработано")
    if not reference:
        raise HTTPException(400, "Нужен reference")
    a_raw = storage.load_features(p)
    b_raw = storage.load_features(find_photo(other)) if other else a_raw
    r_raw = storage.load_features(find_photo(reference))
    top_data = topology_data()
    lm = np.asarray(top_data["landmarks"]["ldm68"], np.int32)
    tri = np.asarray(top_data["triangles"], np.int32)
    frames = []
    for raw in (a_raw, b_raw, r_raw):
        norm, _ = heat_space(raw, lm)
        frames.append(norm if normalizeScale else raw)
    try:
        start, end, mode = segment_heat(
            *frames, tri=tri, morphing=morphing, t=float(np.clip(t, 0, 1)),
            metric=metric, weighting=weighting, smoothing=smoothing,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(409, str(exc))
    packed = {name: base64.b64encode(np.asarray(v, "<f4").tobytes()).decode("ascii")
              for name, v in (("start", start), ("end", end))}
    return {
        "metric": mode["metric"],
        "weighting": mode["weighting"],
        "vmax": mode["vmax"],
        "count": int(len(start)),
        "dtype": "float32",
        "encoding": "base64-le",
        **packed,
    }


def chart_sequence(group: str):
    """Кадры хронологии группы в том же порядке, что и Timeline."""
    ps = [
        p
        for p in storage.library()
        if (group in ("", "__all") or p["group"] == group) and p["status"] == "ready"
    ]
    ps.sort(key=lambda p: (p["date"] or "9999", p["name"]))
    signature = tuple((p["id"], storage.feature_path(p).stat().st_mtime_ns) for p in ps)
    return ps, signature


def chart_config_signature() -> tuple:
    """Ключ кэша ряда: блок chart и mtime профиля.

    Без этого смена temporal_filter/metric в конфиге не видна: lru_cache
    держал бы старый ряд до изменения feature-файла.
    """
    cfg = chart.settings()
    path = Path(cfg["calibration_profile"])
    if not path.is_absolute():
        path = ROOT / path
    mtime = path.stat().st_mtime_ns if path.exists() else 0
    return (cfg["metric"], cfg["weighting"], cfg["temporal_filter"],
            int(cfg["filter_window"]), str(path), mtime)


@lru_cache(maxsize=32)
def chart_payload(group: str, metric: str, signature: tuple,
                  config_signature: tuple) -> dict:
    """Ряд графика: raw и calibrated считаются сервером из одного helper.

    Кадры идут в том же пространстве, что heatmap: center + IOD по ldm68.
    Клиент только рисует готовые ряды и не применяет собственных формул.
    """
    cfg_metric, _cfg_weight, temporal_filter, window, profile_path, _mtime = config_signature
    known = {p["id"]: p for p in storage.read_db()["photos"]}
    top = topology_data()
    lm = np.asarray(top["landmarks"]["ldm68"], np.int32)
    tri = np.asarray(top["triangles"], np.int32)
    active = chart.mode(metric or cfg_metric, profile=profile_path)
    base_metric = active["metric"]
    frames, meta = [], []
    for pid, _ in signature:
        p = known[pid]
        raw = storage.load_features(p)
        frames.append(heat_space(raw, lm)[0])
        meta.append(
            {"id": pid, "name": p["name"], "date": p["date"], "group": p["group"]}
        )
    raw_cfg = chart.mode(base_metric, weighting="none", profile=profile_path)
    calibrated_cfg = chart.mode(base_metric, weighting="calibrated", profile=profile_path)
    rows_raw = chart.series(
        frames,
        tri,
        raw_cfg,
        temporal_filter=temporal_filter,
        window=window,
    )
    rows_calibrated = chart.series(
        frames,
        tri,
        calibrated_cfg,
        temporal_filter=temporal_filter,
        window=window,
    )
    for i, (a, b) in enumerate(zip(meta, meta[1:], strict=False)):
        rows_raw[i].update({"from": a["id"], "to": b["id"]})
        rows_calibrated[i].update({"from": a["id"], "to": b["id"]})
    return {
        "mode": {
            "name": active["name"],
            "metric": base_metric,
            "weighting": active["weighting"],
            "temporal_filter": temporal_filter,
            "filter_window": window,
        },
        "frames": meta,
        "rows": rows_calibrated,
        "rows_raw": rows_raw,
        "rows_calibrated": rows_calibrated,
    }


@app.get("/api/chart/series")
def chart_series(group: str = "__all", metric: str | None = None):
    """Ряд графика Timeline: value_raw, value_display, band, significance.

    Режим берётся из блока chart в configs/runtime.yaml; metric — только
    явный override для parity-проверок, как у /api/photos/{id}/heat.
    """
    try:
        chart.mode(metric or None)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(409, str(exc)) from exc
    _, signature = chart_sequence(group)
    return chart_payload(group, metric or "", signature, chart_config_signature())


@app.get("/api/chart/series.csv")
def chart_series_csv(group: str = "__all", metric: str | None = None):
    """Тот же ряд графика, что и /api/chart/series, но выгрузкой в CSV.

    Значения берёт `chart_payload` (server/chart.py поверх compute_heat_values) —
    второй формулы нет; выгрузка только сериализует готовые rows.
    """
    _, signature = chart_sequence(group)
    payload = chart_payload(group, metric or "", signature, chart_config_signature())
    dates = {f["id"]: f["date"] for f in payload["frames"]}
    cols = ["from", "to", "from_date", "to_date", "value_raw", "value_display",
            "band", "significance", "z_mean", "z_p95", "frac_z_gt3",
            "low_confidence_fraction"]
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([payload["mode"]["name"], *cols[4:]])
    writer.writerow(cols)
    for row in payload["rows"]:
        writer.writerow([
            row.get("from"), row.get("to"),
            dates.get(row.get("from")), dates.get(row.get("to")),
            *[row.get(c) for c in cols[4:]],
        ])
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="atlas-chart-series.csv"'},
    )


@app.get("/api/photos/{id}/preview")
def preview(
    id: str,
    reference: str | None = None,
    t: float = 0,
    other: str | None = None,
    morphing: bool = False,
    size: int = 512,
    vmax: float | None = None,
    vmin: float = 0,
    palette: str = "turbo",
    heatmap: bool = True,
    yaw: float = 0,
    pitch: float = 0,
    zoom: float = 1,
    gamma: float = 1,
    opacity: float = 0.85,
    metric: str | None = None,
    weighting: str | None = None,
    texture: bool = False,
    normalizeScale: bool = False,
    inverse: bool = False,
    outsideOpacity: float = 0.85,
    onlyAbove: bool = False,
    smoothing: int = 0,
    wireframe: bool = False,
    low: str = "#3155c6",
    mid: str = "#5bd8b1",
    high: str = "#ed6558",
    midPosition: float = 0.5,
):
    p = find_photo(id)
    if not storage.feature_path(p).exists():
        raise HTTPException(409, "Фото ещё не обработано")
    a_raw = storage.load_features(p)
    b_photo = find_photo(other) if other else p
    b_raw = storage.load_features(b_photo) if other else a_raw
    top_data = topology_data()
    lm = np.asarray(top_data["landmarks"]["ldm68"], np.int32)
    tri = np.asarray(top_data["triangles"], np.int32)
    a_norm, _ = heat_space(a_raw, lm)
    b_norm, _ = heat_space(b_raw, lm)
    a = a_norm if normalizeScale else a_raw
    b = b_norm if normalizeScale else b_raw
    t = float(np.clip(t, 0, 1))
    v = a["vertices"] * (1 - t) + b["vertices"] * t
    if texture:
        from server.rendering import _source_photo_vertex_colors
        uv = top_data["uv"]
        color_a = _source_photo_vertex_colors(p, a_raw, uv)
        color_b = _source_photo_vertex_colors(b_photo, b_raw, uv)
        cols = color_a * (1 - t) + color_b * t
    else:
        cols = np.tile(np.array([0.53, 0.59, 0.65], np.float32), (len(v), 1))
    if reference and heatmap:
        r_raw = storage.load_features(find_photo(reference))
        r_norm, _ = heat_space(r_raw, lm)
        r = r_norm if normalizeScale else r_raw
        try:
            start_values, end_values, mode = segment_heat(
                a, b, r, tri=tri, morphing=morphing, t=t, metric=metric,
                weighting=weighting, smoothing=smoothing,
            )
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(409, str(exc))
        if vmax is None:
            vmax = mode["vmax"]
        values = start_values * (1 - t) + end_values * t if morphing else start_values
        custom = {
            "low": low,
            "mid": mid,
            "high": high,
            "midPosition": min(0.95, max(0.05, midPosition)),
        }
        try:
            heat_start = colorize(start_values, lo=vmin, hi=max(vmin + 0.00001, vmax), palette=palette, gamma=max(0.1, min(5, gamma)), inverse=inverse, custom=custom)
            heat_end = colorize(end_values, lo=vmin, hi=max(vmin + 0.00001, vmax), palette=palette, gamma=max(0.1, min(5, gamma)), inverse=inverse, custom=custom)
        except Exception:
            raise HTTPException(400, "Некорректная палитра")
        heat = heat_start * (1 - t) + heat_end * t if morphing else heat_start
        alpha_start = np.full((len(v), 1), np.clip(opacity, 0, 1), np.float32)
        alpha_end = alpha_start.copy()
        if onlyAbove:
            alpha_start[start_values <= vmin] = 0
            alpha_end[end_values <= vmin] = 0
        else:
            alpha_start[start_values <= vmin] = np.clip(outsideOpacity, 0, 1)
            alpha_end[end_values <= vmin] = np.clip(outsideOpacity, 0, 1)
        # Interpolate RGBA endpoint maps. The first keyframe is transparent;
        # later segments begin with the previous pair's map, never with zero.
        alpha = alpha_start * (1 - t) + alpha_end * t if morphing else alpha_start
        cols = cols * (1 - alpha) + heat * alpha
    size = min(768, max(128, int(size)))
    rgb = rasterize(
        v,
        tri,
        cols,
        size,
        yaw,
        pitch,
        zoom=np.clip(zoom, 0.5, 2.5),
        wireframe=wireframe,
    )
    out = io.BytesIO()
    from PIL import Image

    Image.fromarray(rgb).save(out, "PNG")
    return Response(
        out.getvalue(), media_type="image/png", headers={"Cache-Control": "no-cache"}
    )


@app.get("/api/jobs")
def jobs():
    return queue.list()


@app.post("/api/jobs/{id}/cancel")
def cancel(id: str):
    if id not in queue.items:
        raise HTTPException(404, "Задача не найдена")
    if queue.items[id]["status"] in ("queued", "running"):
        queue.update(id, cancel_requested=True, message="Отмена после текущего шага")
    return queue.items[id]


@app.get("/api/events")
async def events():
    async def stream():
        last = -1
        tick = 0
        while True:
            if queue.revision != last:
                last = queue.revision
                yield (
                    "data: "
                    + json.dumps(
                        {"revision": last, "jobs": queue.list()}, ensure_ascii=False
                    )
                    + "\n\n"
                )
            elif tick % 30 == 0:
                yield ": keepalive\n\n"
            tick += 1
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            # GZipMiddleware (см. начало файла) не трогает ответ, у которого
            # Content-Encoding уже задан: без этой строки браузер с
            # Accept-Encoding: gzip получал сжатый поток, который Starlette
            # не сбрасывал на лету, и SSE молчал — статус обновлялся только
            # шестисекундным опросом /api/jobs.
            "Content-Encoding": "identity",
        },
    )


@app.get("/api/exports/{name}")
def export_file(name: str):
    if (
        Path(name).name != name
        or not name.startswith("morph-")
        or Path(name).suffix not in (".mp4", ".json")
    ):
        raise HTTPException(404)
    p = ROOT / "exports" / name
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(
        p,
        filename=name,
        media_type="video/mp4" if p.suffix == ".mp4" else "application/json",
    )


@app.get("/api/export/metrics.csv")
def metrics_csv():
    t = analysis.metrics_table()
    s = io.StringIO()
    w = csv.writer(s)
    keys = [m["id"] for m in t["catalog"]]
    w.writerow(
        ["photo_id", "group", "date", "pose"]
        + [f"{key}:{mode}" for key in keys for mode in ("value", "robust_z")]
    )
    for r in t["rows"]:
        w.writerow(
            [r["id"], r["group"], r["date"], r["pose"]]
            + [r["metrics"][k][v] for k in keys for v in ("value", "z")]
        )
    return Response(
        "\ufeff" + s.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="atlas-metrics.csv"'},
    )


@app.get("/api/workspace")
def workspace():
    p = ROOT / "workspace.json"
    return json.loads(p.read_text()) if p.exists() else None


@app.put("/api/workspace")
def workspace_put(data: dict = Body(...)):
    if len(json.dumps(data)) > 1024 * 1024:
        raise HTTPException(400, "Раскладка слишком велика")
    atomic_json(ROOT / "workspace.json", data)
    return {"ok": True}


@app.get("/api/runtime")
def runtime_get():
    return {
        "torch_threads": 2,
        "detector_confidence": 0.7,
        **yaml.safe_load((CONFIG / "runtime.yaml").read_text()),
    }


@app.put("/api/runtime")
def runtime_put(data: dict = Body(...)):
    threads = int(data.get("torch_threads", 2))
    confidence = float(data.get("detector_confidence", 0.7))
    if not 1 <= threads <= 2 or not 0.4 <= confidence <= 0.95:
        raise HTTPException(400, "Потоки: 1–2. Порог: 0.4–0.95")
    doc = runtime_get()
    doc.update(torch_threads=threads, detector_confidence=confidence)
    doc["version"] += 1
    (CONFIG / "runtime.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    return doc


# Production: one origin and one process for UI, API, SSE and exports.
# Added last so it never shadows API routes. Vite remains usable for development.
if (ROOT / "web/dist").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "web/dist", html=True), name="frontend")
