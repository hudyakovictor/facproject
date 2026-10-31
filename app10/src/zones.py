"""Фиксированные зоны лица как индексы вершин.

Топология сетки одна для всех кадров, поэтому зоны задаются ОДИН раз на
канонической сетке (медиана нейтральных кадров) и дальше не пересчитываются.
Зоны не перекрываются: вершина попадает в первую подходящую зону по приоритету.

ВНИМАНИЕ: границы ниже взяты из прежнего zonal_calibrate.py и НЕ валидированы.
Перед использованием проверь картинку reports/zones_check.png и поправь правила.
"""
import json
import hashlib
from pathlib import Path

import numpy as np

# порядок = приоритет (первая подходящая зона побеждает). y/absx: [lo, hi], None = без границы
DEFAULT_RULES = {
    "eyes": {"y": [-0.25, 0.0], "absx": [0.1, 0.35]},
    "eyebrows": {"y": [-0.05, 0.15], "absx": [0.15, 0.4]},
    "nose": {"y": [-0.45, 0.05], "absx": [None, 0.15]},
    "lips": {"y": [-0.65, -0.25], "absx": [None, 0.2]},
    "chin": {"y": [None, -0.55], "absx": [None, 0.25]},
    "forehead": {"y": [0.15, None], "absx": [None, None]},
    "cheeks": {"y": [-0.5, 0.1], "absx": [0.2, 0.5]},
    "jaw": {"y": [-0.7, -0.3], "absx": [0.25, 0.5]},
}


def _inside(values, bounds):
    lo, hi = bounds
    ok = np.ones(values.shape, dtype=bool)
    if lo is not None:
        ok &= values > lo
    if hi is not None:
        ok &= values < hi
    return ok


def canonical_mesh(meshes):
    """Поэлементная медиана по списку сеток (K, N, 3) -> (N, 3)."""
    arr = np.stack([np.asarray(m, dtype=np.float64) for m in meshes], axis=0)
    return np.median(arr, axis=0)


def build_zones(canon_v, rules=None, min_vertices=10):
    """Возвращает dict зона -> массив индексов. Зоны не пересекаются."""
    rules = rules or DEFAULT_RULES
    v = np.asarray(canon_v)
    if v.ndim != 2 or v.shape[1] != 3:
        raise ValueError(f"ожидается (N,3), получено {v.shape}")
    x, y = v[:, 0], v[:, 1]
    free = np.ones(len(v), dtype=bool)
    zones = {}
    for name, r in rules.items():
        mask = free & _inside(y, r["y"]) & _inside(np.abs(x), r["absx"])
        idx = np.where(mask)[0]
        if len(idx) < min_vertices:
            raise ValueError(f"зона {name}: {len(idx)} вершин (< {min_vertices}), правила нужно поправить")
        zones[name] = idx
        free &= ~mask
    return zones


def check_disjoint(zones):
    seen = np.concatenate(list(zones.values()))
    return len(seen) == len(np.unique(seen))


def zones_sha256(zones):
    """Канонический хеш содержимого зон (только индексы вершин). Меняется при правке границ."""
    canon = {k: sorted(int(i) for i in idx) for k, idx in sorted(zones.items())}
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def save_zones(path, zones, n_vertices, rules=None, source=None):
    data = {
        "n_vertices": int(n_vertices),
        "validated": False,
        "zones_sha256": zones_sha256(zones),
        "rules": rules or DEFAULT_RULES,
        "source": source or {},
        "zones": {k: [int(i) for i in v] for k, v in zones.items()},
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False))
    return data


def load_zones(path, n_vertices=None):
    d = json.loads(Path(path).read_text())
    if n_vertices is not None and int(d["n_vertices"]) != int(n_vertices):
        raise ValueError(f"зоны для {d['n_vertices']} вершин, а в сетке {n_vertices}")
    zones = {k: np.asarray(v, dtype=np.int64) for k, v in d["zones"].items()}
    return zones, d
