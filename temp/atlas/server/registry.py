"""File-discovered metric plugins. YAML overrides are per model AND pose.
Adding a decorated .py file is enough for default metrics; YAML can override all settings.
"""

from pathlib import Path
from dataclasses import dataclass
import importlib, inspect, math, sys, threading
from functools import wraps
import numpy as np
from server.config import ROOT, CONFIG, digest, read_yaml

REGISTRY = {}
_registry_lock = threading.RLock()


def locked(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with _registry_lock:
            return fn(*args, **kwargs)

    return wrapper


def definitions():
    with _registry_lock:
        return list(REGISTRY.values())


@dataclass
class Definition:
    id: str
    title: str
    model: str
    unit: str
    fn: object
    inputs: tuple
    poses: tuple


def metric(id, title, model="3ddfa_v3", unit="ratio", inputs=("vertices",), poses=()):
    def register(fn):
        REGISTRY[id] = Definition(
            id, title, model, unit, fn, tuple(inputs), tuple(poses)
        )
        return fn

    return register


@locked
def discover():
    REGISTRY.clear()
    for p in sorted((ROOT / "metrics").rglob("*.py")):
        if p.name.startswith("_") or p.name == "common.py":
            continue
        mod = ".".join(p.relative_to(ROOT).with_suffix("").parts)
        importlib.invalidate_caches()
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
        else:
            importlib.import_module(mod)


def overrides():
    out = {}
    for p in sorted((CONFIG / "metrics").glob("*/*.yaml")):
        doc = read_yaml(p)
        for m in doc.get("metrics", []):
            out[(doc["model"], doc["pose"], m["id"])] = {
                **m,
                "config_file": str(p.relative_to(ROOT)),
                "config_version": doc.get("version", 1),
            }
    return out


def version():
    files = (
        list((CONFIG / "metrics").rglob("*.yaml"))
        + list((ROOT / "metrics").rglob("*.py"))
        + [
            CONFIG / "pose_profiles.yaml",
            ROOT / "server/registry.py",
            ROOT / "server/analysis.py",
        ]
    )
    return digest({str(p.relative_to(ROOT)): p.read_text() for p in sorted(files)})


@locked
def catalog():
    from server.config import profiles

    discover()
    ov = overrides()
    poses = [p["id"] for p in profiles()["profiles"]]
    return [
        {
            "id": d.id,
            "title": ov.get((d.model, "frontal", d.id), {}).get("title", d.title),
            "model": d.model,
            "unit": ov.get((d.model, "frontal", d.id), {}).get("unit", d.unit),
            "inputs": d.inputs,
            "source": str(Path(inspect.getfile(d.fn)).relative_to(ROOT)),
            "poses": {
                p: {
                    "enabled": not d.poses or p in d.poses,
                    "thresholds": {"warn": 2.0, "alert": 3.0},
                    **ov.get((d.model, p, d.id), {}),
                }
                for p in poses
            },
        }
        for d in REGISTRY.values()
    ]


def evaluate(ctx, pose):
    ov = overrides()
    result = {}
    for d in definitions():
        key = d.id
        conf = ov.get((d.model, pose, key), {})
        if (
            pose == "unclassified"
            or not conf.get("enabled", True)
            or d.poses
            and pose not in d.poses
        ):
            result[key] = {
                "value": None,
                "reason": "Метрика отключена для этого ракурса",
            }
            continue
        if any(k not in ctx for k in d.inputs):
            result[key] = {"value": None, "reason": "Модель ещё не подключена"}
            continue
        try:
            v = float(d.fn(ctx))
            result[key] = {
                "value": v if math.isfinite(v) else None,
                "reason": None if math.isfinite(v) else "Неопределённое значение",
            }
        except Exception as e:
            result[key] = {"value": None, "reason": str(e)}
    return result


def robust_scores(rows):
    # Cohorts never mix groups or poses. Fewer than 3 samples yields no invented z-score.
    for row in rows:
        for key, item in row["metrics"].items():
            values = [
                r["metrics"][key]["value"]
                for r in rows
                if r["group"] == row["group"]
                and r["pose"] == row["pose"]
                and key in r["metrics"]
                and r["metrics"][key]["value"] is not None
            ]
            item["n"] = len(values)
            item["z"] = None
            if item["value"] is not None and len(values) >= 3:
                med = float(np.median(values))
                mad = float(np.median(np.abs(np.array(values) - med)))
                item["z"] = (
                    0.0
                    if mad < 1e-10 and abs(item["value"] - med) < 1e-10
                    else (
                        None if mad < 1e-10 else (item["value"] - med) / (1.4826 * mad)
                    )
                )
    return rows
