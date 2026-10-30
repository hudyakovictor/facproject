from pathlib import Path
import hashlib, json, threading
import yaml

ROOT = Path(__file__).resolve().parents[1]
# Working 3DDFA-V3 checkout on this machine: code in TDDFA_ROOT, weights in assets/.
TDDFA_ROOT = Path("/Users/victorkhudyakov/work/3ddfa_v3")
ASSETS = TDDFA_ROOT / "assets"
CONFIG = ROOT / "configs"
_lock = threading.RLock()


def read_yaml(path):
    return yaml.safe_load(Path(path).read_text())


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False))
        tmp.replace(path)


def digest(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


def profiles():
    return read_yaml(CONFIG / "pose_profiles.yaml")


def classify(angles, override=None):
    if angles.get('manual_gaze') is False:
        return 'unclassified'
    if override:
        angles = {**angles, **override}
    for p in profiles()["profiles"]:
        if all(
            p[k][0] <= float(angles[k]) <= p[k][1] for k in ("yaw", "pitch", "roll")
        ):
            return p["id"]
    return "unclassified"


def save_profiles(data):
    if len(data.get("profiles", [])) != 5:
        raise ValueError("Требуется ровно пять профилей")
    ids = [p["id"] for p in profiles()["profiles"]]
    if sorted(p["id"] for p in data["profiles"]) != sorted(ids):
        raise ValueError("Нельзя менять id профилей")
    for p in data["profiles"]:
        for key, limit in [("yaw", 180), ("pitch", 90), ("roll", 180)]:
            a, b = p[key]
            if not -limit <= a < b <= limit:
                raise ValueError(f"Некорректный диапазон {key}")
    data["version"] = profiles().get("version", 1) + 1
    with _lock:
        p = CONFIG / "pose_profiles.yaml"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        tmp.replace(p)
    return data
