from pathlib import Path
from abc import ABC, abstractmethod
import hashlib, io, json, re, zipfile, threading, datetime
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from server.config import ROOT, CONFIG, read_yaml, atomic_json, digest, classify
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
    with _lock:
        db = read_db()
        added = []
        for name, content in items:
            # Archive paths only choose a group; they are never extracted to a path.
            rel = Path(name.replace("\\", "/"))
            filename = safe_name(rel.name)
            g = safe_name(
                rel.parent.name if rel.parent.name not in ("", ".") else group
            )
            if rel.suffix.lower() not in EXT:
                continue
            if len(content) > 30 * 1024 * 1024:
                raise ValueError(f"Файл слишком велик: {filename}")
            try:
                img = Image.open(io.BytesIO(content))
                img.verify()
                img = Image.open(io.BytesIO(content))
                if img.width * img.height > 40_000_000:
                    raise ValueError("Слишком большое изображение")
            except Exception as e:
                raise ValueError(f"Не удалось прочитать {filename}: {e}")
            sha = hashlib.sha256(content).hexdigest()
            id = digest({"hash": sha, "group": g, "filename": filename})
            if any(p["id"] == id for p in db["photos"]):
                continue
            path = ROOT / "data/groups" / g / (id + rel.suffix.lower())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            thumb = ROOT / "cache" / id / "thumb.jpg"
            thumb.parent.mkdir(parents=True, exist_ok=True)
            ImageOps.fit(
                ImageOps.exif_transpose(img).convert("RGB"),
                (160, 160),
                method=Image.Resampling.LANCZOS,
            ).save(thumb, quality=85)
            p = {
                "id": id,
                "hash": sha,
                "name": filename,
                "group": g,
                "path": str(path.relative_to(ROOT)),
                "date": parse_date(filename),
                "precropped": bool(precropped),
                "demo": demo,
                "angle_override": None,
            }
            db["photos"].append(p)
            added.append(id)
        if demo:
            db["demo"] = True
        write_db(db)
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
        path = ROOT / "vendor/3DDFA-V3/examples/1.jpg"
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
    if found is None or found.get("deleted_at"):
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
    ps = [
        p
        for p in read_db()["photos"]
        if not p.get("deleted_at") and (ids is None or p["id"] in ids)
    ]
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
            if changes["date"]:
                datetime.date.fromisoformat(changes["date"])
            p["date"] = changes["date"] or None
        if "angle_override" in changes:
            ov = changes["angle_override"]
            if ov is not None:
                if not isinstance(ov, dict) or any(
                    k not in ("yaw", "pitch", "roll") or not -180 <= float(v) <= 180
                    for k, v in ov.items()
                ):
                    raise ValueError("Некорректные углы")
            p["angle_override"] = ov
        if "precropped" in changes:
            p["precropped"] = bool(changes["precropped"])
        if "cohort" in changes:
            cohort = str(changes["cohort"]).strip()
            if len(cohort) > 80:
                raise ValueError("Название группы не должно превышать 80 символов")
            p["cohort"] = cohort or None
        write_db(db)
        return state(p)


def trash_photos(ids, restore=False):
    import time

    with _lock:
        db = read_db()
        known = {p["id"] for p in db["photos"]}
        if not set(ids) <= known:
            raise ValueError("Неизвестный ID фотографии")
        changed = 0
        for p in db["photos"]:
            if p["id"] in ids:
                if restore:
                    p.pop("deleted_at", None)
                else:
                    p["deleted_at"] = time.time()
                changed += 1
        write_db(db)
        return {"changed": changed, "recoverable": True}


def purge_demo_photos(ids=None):
    """Permanently erase ONLY synthetic demo entries and their derived cache."""
    with _lock:
        db = read_db()
        demo = [p for p in db["photos"] if p.get("demo") and not p.get("deleted_at")]
        requested = set([p["id"] for p in demo] if ids is None else ids)
        if any(
            p["id"] not in {x["id"] for x in demo} for p in demo if p["id"] in requested
        ):
            raise ValueError("Неизвестный demo-файл")
        if not requested.issubset({p["id"] for p in demo}):
            raise ValueError(
                "Можно безвозвратно удалить только сгенерированные demo-фото"
            )
        import shutil

        removed = []
        for p in db["photos"]:
            if p["id"] in requested and p.get("demo"):
                (ROOT / p["path"]).unlink(missing_ok=True)
                shutil.rmtree(ROOT / "cache" / p["id"], ignore_errors=True)
                removed.append(p["id"])
        db["photos"] = [p for p in db["photos"] if p["id"] not in requested]
        db["demo"] = any(
            p.get("demo") and not p.get("deleted_at") for p in db["photos"]
        )
        write_db(db)
        if not db["demo"]:
            (ROOT / "data/demo-source.png").unlink(missing_ok=True)
        return {"removed": len(removed), "only_demo": True}
