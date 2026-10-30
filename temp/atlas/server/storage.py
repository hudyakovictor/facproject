from pathlib import Path
from abc import ABC, abstractmethod
import hashlib, io, json, re, shutil, zipfile, threading, datetime
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from server.config import ROOT, CONFIG, TDDFA_ROOT, read_yaml, atomic_json, digest, classify
from server.models.tddfa import VERSION, MODEL_HASH, get_model

EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
_lock = threading.RLock()
DB = ROOT / "data/library.json"


def safe_name(s):
    return (
        re.sub(r"[^\w\-. ()]+", "_", s, flags=re.UNICODE).strip(". ")[:160]
        or "Без имени"
    )


def parse_date(name):
    pattern = read_yaml(CONFIG / "storage.yaml")["date_regex"]
    m = re.search(pattern, Path(name).stem)
    if not m:
        return None
    try:
        return datetime.date(int(m["year"]), int(m["month"]), int(m["day"])).isoformat()
    except (ValueError, IndexError):
        return None


def read_db():
    with _lock:
        return (
            json.loads(DB.read_text()) if DB.exists() else {"photos": [], "demo": False}
        )


def write_db(db):
    with _lock:
        atomic_json(DB, db)


class StorageAdapter(ABC):
    @abstractmethod
    def scan(self): ...


class LocalStorageAdapter(StorageAdapter):
    def __init__(self, root=None):
        self.root = Path(root or ROOT / "data/groups")

    def scan(self):
        return [
            (p.parent.name, p.name, p.read_bytes())
            for p in sorted(self.root.rglob("*"))
            if p.is_file() and p.suffix.lower() in EXT
        ]


def ingest(items, group="Моя группа", precropped=False, demo=False):
    # Validate and prepare every image before touching disk/DB so one corrupt
    # file cannot leave an unindexed partial upload behind.
    staged = []
    for name, content in items:
        rel = Path(name.replace("\\", "/"))
        filename = safe_name(rel.name)
        suffix = rel.suffix.lower()
        if suffix not in EXT:
            continue
        g = safe_name(rel.parent.name if rel.parent.name not in ("", ".") else group)
        if len(content) > 30 * 1024 * 1024:
            raise ValueError(f"Файл слишком велик: {filename}")
        try:
            img = Image.open(io.BytesIO(content))
            if img.width * img.height > 40_000_000:
                raise ValueError("Слишком большое изображение")
            img.verify()
            img = Image.open(io.BytesIO(content))
            thumb_bytes = io.BytesIO()
            ImageOps.fit(ImageOps.exif_transpose(img).convert("RGB"), (160, 160),
                         method=Image.Resampling.LANCZOS).save(thumb_bytes, "JPEG", quality=85)
        except Exception as e:
            raise ValueError(f"Не удалось прочитать {filename}: {e}")
        sha = hashlib.sha256(content).hexdigest()
        photo_id = digest({"hash": sha, "group": g, "filename": filename})
        staged.append({"id": photo_id, "hash": sha, "name": filename, "group": g,
                       "suffix": suffix, "content": content, "thumb": thumb_bytes.getvalue(),
                       "date": parse_date(filename)})

    with _lock:
        db = read_db()
        known = {p["id"]: p for p in db["photos"]}
        added, created = [], []
        try:
            for item in staged:
                existing = known.get(item["id"])
                if existing is not None:
                    # id выводится из хэша, группы и имени файла, поэтому
                    # активный дубликат отсекается. Запись из старой корзины
                    # (deleted_at) стираем вместе с кэшем и принимаем файл
                    # заново, как после обычного удаления.
                    if not existing.get("deleted_at"):
                        continue
                    _delete_assets(existing)
                    db["photos"].remove(existing)
                    known.pop(item["id"], None)
                path = ROOT / "data/groups" / item["group"] / (item["id"] + item["suffix"])
                thumb = ROOT / "cache" / item["id"] / "thumb.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                thumb.parent.mkdir(parents=True, exist_ok=True)
                was_image, was_thumb = path.exists(), thumb.exists()
                path.write_bytes(item["content"])
                if not was_image: created.append(path)
                thumb.write_bytes(item["thumb"])
                if not was_thumb: created.append(thumb)
                p = {"id": item["id"], "hash": item["hash"], "name": item["name"],
                     "group": item["group"], "path": str(path.relative_to(ROOT)),
                     "date": item["date"], "precropped": bool(precropped), "demo": demo,
                     "angle_override": None}
                db["photos"].append(p)
                known[item["id"]] = p
                added.append(item["id"])
            if demo:
                db["demo"] = True
            write_db(db)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        return added


def unpack_zip(content):
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise ValueError("Невалидный ZIP-архив")
    items = []
    total = 0
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        if len(z.infolist()) > 500:
            raise ValueError("В архиве максимум 500 файлов")
        for f in z.infolist():
            if f.is_dir() or Path(f.filename).suffix.lower() not in EXT:
                continue
            total += f.file_size
            if total > 300 * 1024 * 1024 or f.file_size > 30 * 1024 * 1024:
                raise ValueError("Архив превышает лимит распаковки 300 МБ")
            items.append((f.filename, z.read(f)))
    return items


def ensure_demo():
    if read_db()["photos"]:
        return
    path = ROOT / "data/demo-source.png"
    if not path.exists():
        path = TDDFA_ROOT / "examples/1.jpg"
    image = Image.open(path).convert("RGB")
    items = []
    params = [
        (1.0, 1.0, 0),
        (1.06, 0.95, -2),
        (0.93, 1.04, 2),
        (1.03, 1.07, -1),
        (0.98, 0.97, 1),
    ]
    dates = ["2019_01_12", "2019_04_12", "2020_06_12", "2021_02_12", "2022_02_12"]
    for date, (br, co, rot) in zip(dates, params):
        im = ImageEnhance.Contrast(ImageEnhance.Brightness(image).enhance(br)).enhance(
            co
        )
        im = im.rotate(rot, Image.Resampling.BICUBIC, fillcolor=(190, 190, 190))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=94)
        items.append((date + ".jpg", b.getvalue()))
    ingest(items, "Демо · один синтетический портрет", demo=True)


def photo(id):
    found = next((p for p in read_db()["photos"] if p["id"] == id), None)
    if found is None:
        raise KeyError(id)
    return found


def key_for(p):
    return digest(
        {
            "hash": p["hash"],
            "model": VERSION,
            "weights": MODEL_HASH,
            "precropped": p["precropped"],
            "detector_confidence": read_yaml(CONFIG / "runtime.yaml").get(
                "detector_confidence", 0.7
            ),
        }
    )


def feature_path(p):
    return ROOT / "cache" / p["id"] / f"features-{key_for(p)}.npz"


def load_features(p, keys=None):
    with np.load(feature_path(p)) as f:
        return {k: f[k].copy() for k in (keys or f.files)}


def state(p):
    meta_path = ROOT / "cache" / p["id"] / "meta.json"
    meta = (
        json.loads(meta_path.read_text())
        if feature_path(p).exists() and meta_path.exists()
        else None
    )
    angles = {
        **(meta["angles"] if meta else {"yaw": 0, "pitch": 0, "roll": 0}),
        **(p.get("angle_override") or {}),
    }
    return {k: v for k, v in p.items() if k != "path"} | {
        "status": "ready" if meta else "pending",
        "meta": meta,
        "angles": angles,
        "pose": classify(angles) if meta else "unclassified",
        "thumbnail": f"/api/photos/{p['id']}/thumbnail",
        "url": f"/api/photos/{p['id']}/image",
    }


def library():
    return sorted(
        [state(p) for p in read_db()["photos"] if not p.get("deleted_at")],
        key=lambda p: (p["group"], p["date"] or "9999", p["name"]),
    )


def process(job, ids=None):
    ps = [p for p in read_db()["photos"] if ids is None or p["id"] in ids]
    hits = 0
    seconds = []
    errors = []
    for i, p in enumerate(ps):
        job.update(i / max(len(ps), 1), f"{i + 1}/{len(ps)} · {p['name']}")
        if feature_path(p).exists():
            hits += 1
            continue
        try:
            feats, meta, crop = get_model().infer(ROOT / p["path"], p["precropped"])
            meta.update(
                {
                    "file_hash": p["hash"],
                    "feature_key": key_for(p),
                    "config": {"backbone": "mbnetv3", "precropped": p["precropped"]},
                    "seed": 42,
                }
            )
            out = feature_path(p)
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".tmp.npz")
            np.savez_compressed(tmp, **feats)
            tmp.replace(out)
            crop.save(out.parent / "aligned.jpg", quality=95)
            atomic_json(out.parent / "meta.json", meta)
            seconds.append(meta["seconds"])
            (out.parent / "error.json").unlink(missing_ok=True)
        except Exception as e:
            errors.append({"id": p["id"], "error": str(e)})
            atomic_json(ROOT / "cache" / p["id"] / "error.json", {"error": str(e)})
    job.update(1, f"{len(ps) - len(errors)} готовы · {hits} из кэша")
    return {
        "photos": len(ps),
        "cache_hits": hits,
        "seconds_per_photo": float(np.mean(seconds)) if seconds else None,
        "errors": errors,
    }


def update_photo(id, changes):
    with _lock:
        db = read_db()
        p = next((p for p in db["photos"] if p["id"] == id), None)
        if p is None:
            raise KeyError(id)
        if "date" in changes:
            date = changes["date"]
            if date is not None and not isinstance(date, str):
                raise ValueError("Дата должна быть строкой ISO или пустой")
            if date:
                try:
                    datetime.date.fromisoformat(date)
                except ValueError as e:
                    raise ValueError("Некорректная дата ISO") from e
            p["date"] = date or None
        if "angle_override" in changes:
            ov = changes["angle_override"]
            if ov is not None:
                if not isinstance(ov, dict) or any(
                    k not in ("yaw", "pitch", "roll")
                    or isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not np.isfinite(v)
                    or not -180 <= v <= 180
                    for k, v in ov.items()
                ):
                    raise ValueError("Некорректные углы")
            p["angle_override"] = ov
        if "precropped" in changes:
            if not isinstance(changes["precropped"], bool):
                raise ValueError("precropped должен быть булевым значением")
            p["precropped"] = changes["precropped"]
        if "cohort" in changes:
            if changes["cohort"] is not None and not isinstance(changes["cohort"], str):
                raise ValueError("Название группы должно быть строкой")
            cohort = (changes["cohort"] or "").strip()
            if len(cohort) > 80:
                raise ValueError("Название группы не должно превышать 80 символов")
            p["cohort"] = cohort or None
        write_db(db)
        return state(p)


def _delete_assets(p):
    """Удалить исходник и кэш одной фотографии. Вызывать только после коммита БД."""
    groups_dir = (ROOT / "data/groups").resolve()
    src = (ROOT / p["path"]).resolve()
    if src.is_relative_to(groups_dir):
        src.unlink(missing_ok=True)
        try:
            src.parent.rmdir()  # пустая папка группы после последнего фото
        except OSError:
            pass
    shutil.rmtree(ROOT / "cache" / p["id"], ignore_errors=True)


def _purge_export_artifacts(ids):
    """Удалить морф-видео и манифесты, собранные из этих фото."""
    ids = set(map(str, ids))
    directory = ROOT / "exports"
    if not ids or not directory.exists():
        return 0
    removed = 0
    for manifest_path in directory.glob("*.json"):
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, ValueError):
            continue
        used = set(map(str, (manifest.get("params") or {}).get("photo_ids") or []))
        used |= {str(p.get("id")) for p in manifest.get("source_photos") or []}
        if used & ids:
            manifest_path.unlink(missing_ok=True)
            manifest_path.with_suffix(".mp4").unlink(missing_ok=True)
            removed += 1
    return removed


def purge_photos(ids):
    """Безвозвратно удалить фото: запись, исходник, кэш и производные экспорты.

    Корзины нет. Повторная загрузка того же файла создаёт запись заново и
    считает реконструкцию с нуля, потому что кэш уже стёрт.
    """
    ids = list(dict.fromkeys(map(str, ids)))
    with _lock:
        db = read_db()
        known = {p["id"] for p in db["photos"]}
        if not set(ids) <= known:
            raise ValueError("Неизвестный ID фотографии")
        wanted = set(ids)
        removed = [p for p in db["photos"] if p["id"] in wanted]
        db["photos"] = [p for p in db["photos"] if p["id"] not in wanted]
        write_db(db)
        # Ассеты трогаем только после успешного коммита: иначе живая запись
        # осталась бы без файлов.
        for p in removed:
            _delete_assets(p)
        exports = _purge_export_artifacts(ids)
        return {"deleted": len(removed), "exports": exports, "recoverable": False}


def purge_demo_photos(ids=None):
    """Irreversibly purge demo-only records and assets, never user photos."""
    with _lock:
        db = read_db()
        requested = set(map(str, ids or []))
        demos = {p["id"] for p in db["photos"] if p.get("demo")}
        if requested - demos:
            raise ValueError("Можно безвозвратно удалить только синтетические демо")
        candidates = [p for p in db["photos"] if p.get("demo") and (not requested or p["id"] in requested)]
        removed = {p["id"] for p in candidates}
        db["photos"] = [p for p in db["photos"] if p["id"] not in removed]
        db["demo"] = any(p.get("demo") for p in db["photos"])
        write_db(db)
        # Only remove assets once the DB commit succeeded; a failed commit must
        # not leave a live demo record pointing at missing files.
        for p in candidates:
            _delete_assets(p)
        return {"removed": len(removed), "only_demo": True}
