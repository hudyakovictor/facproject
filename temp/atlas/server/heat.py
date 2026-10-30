"""Единая реализация значений heatmap: preview, export и калибровка.

Одна и та же функция считает per-vertex значения и на сервере, и в harness,
поэтому preview и export не могут разойтись по формуле. Калибровка меняет
только значения карты, геометрия (`vertices`) и морф остаются нетронутыми.

    values = compute_heat_values(a, b, previous, triangles, metric="normal",
                                 weighting="calibrated")
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from server.config import ROOT

METRICS = ("euclid", "normal")
WEIGHTING = ("none", "calibrated")
PROFILE_PATH = ROOT / "reports/calibration/weights.json"
# Калиброванные значения живут в единицах шума, а не в долях IOD.
VMAX = {"none": 0.06, "calibrated": 4.0}

_matrix_cache: dict[tuple[int, bytes], object] = {}
_normals_cache: dict[tuple[int, bytes], np.ndarray] = {}
_mean_cache: np.ndarray | None = None


def topology_mean() -> np.ndarray:
    """Среднее лицо из data/topology.json — стабильное поле направлений."""
    global _mean_cache
    if _mean_cache is None:
        data = json.loads((ROOT / "data/topology.json").read_text())
        _mean_cache = np.asarray(data["mean"], np.float32)
    return _mean_cache


def template_normals(triangles: np.ndarray) -> np.ndarray:
    """Нормали среднего лица: одно поле на все кадры и сегменты.

    Свои нормали на каждый кадр рвали карту на стыке: end сегмента s считался
    с нормалями A_s, а start сегмента s+1 — уже с нормалями B_s, хотя это один
    и тот же переход. Единое поле делает start_{s+1} == end_s до бита.
    """
    key = (len(triangles), triangles.tobytes())
    hit = _normals_cache.get(key)
    if hit is None:
        hit = vertex_normals(topology_mean(), triangles)
        _normals_cache.clear()
        _normals_cache[key] = hit
    return hit


def vertex_normals(positions: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Площадно-взвешенные нормали вершин, как в web/src/heat.ts."""
    out = np.zeros_like(positions, dtype=np.float64)
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    n = np.cross(positions[b] - positions[a], positions[c] - positions[a])
    for k in range(3):
        np.add.at(out, triangles[:, k], n)
    length = np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)
    return (out / length).astype(np.float32)


def neighbor_matrix(triangles: np.ndarray, n: int):
    """Строки — уникальные соседи вершины, как в клиентском сглаживании."""
    key = (n, triangles.tobytes())
    hit = _matrix_cache.get(key)
    if hit is not None:
        return hit
    from scipy.sparse import coo_matrix, eye

    a = np.concatenate([triangles[:, 0], triangles[:, 1], triangles[:, 2]])
    b = np.concatenate([triangles[:, 1], triangles[:, 2], triangles[:, 0]])
    rows, cols = np.concatenate([a, b]), np.concatenate([b, a])
    matrix = coo_matrix((np.ones(len(rows), np.float32), (rows, cols)),
                        shape=(n, n)).tocsr()
    matrix.data[:] = 1.0
    matrix = (matrix + eye(n, dtype=np.float32, format="csr")).tocsr()
    scale = np.asarray(matrix.sum(axis=1)).ravel()
    matrix = matrix.multiply(1.0 / scale[:, None]).tocsr()
    _matrix_cache.clear()
    _matrix_cache[key] = matrix
    return matrix


def smooth(values: np.ndarray, triangles: np.ndarray, passes: int) -> np.ndarray:
    passes = int(max(0, min(5, passes)))
    if not passes:
        return values.astype(np.float32, copy=False)
    matrix = neighbor_matrix(triangles, len(values))
    out = np.asarray(values, np.float32)
    for _ in range(passes):
        out = np.asarray(matrix @ out, np.float32)
    return out


def normalize_metric(name: str | None) -> str:
    """Клиентские имена ('distance', 'identity') → метрики helper'а."""
    return "normal" if (name or "euclid").strip().lower() == "normal" else "euclid"


def space_array(features, metric_name: str = "distance"):
    """Пространство сравнения: identity уже канонична, иначе vertices."""
    if metric_name == "identity":
        return features.get("identity", features["vertices"])
    return features["vertices"]


def metric_values(delta: np.ndarray, normals: np.ndarray | None, metric: str) -> np.ndarray:
    if metric == "normal":
        if normals is None:
            raise ValueError("Для metric=normal нужны нормали")
        return np.abs(np.sum(delta * normals, axis=1)).astype(np.float32)
    return np.linalg.norm(delta, axis=1).astype(np.float32)


class Calibration:
    """Профиль шума: sigma по вершинам, ограниченная квантилями."""

    def __init__(self, payload: dict):
        self.payload = payload
        sigma = np.asarray(payload["sigma"], np.float32)
        lo, hi = (float(v) for v in payload["clip"])
        self.sigma = np.clip(sigma, lo, hi).astype(np.float32)
        normal = np.asarray(payload.get("sigma_normal", payload["sigma"]), np.float32)
        lo_n, hi_n = (float(v) for v in payload.get("clip_normal", payload["clip"]))
        self.sigma_normal = np.clip(normal, lo_n, hi_n).astype(np.float32)
        self.n = int(self.sigma.size)
        self.weight = (1.0 / self.sigma).astype(np.float32)
        self.weight_normal = (1.0 / self.sigma_normal).astype(np.float32)
        self.weight_sum = float(self.weight.sum())
        self.weight_normal_sum = float(self.weight_normal.sum())
        self.lo, self.hi = lo, hi
        self.lo_normal, self.hi_normal = lo_n, hi_n
        # Шум агрегата для графика Timeline, отдельно по режимам.
        # Считается harness'ом на спокойных шагах и лежит в том же профиле.
        self.chart_band = {str(k): float(v)
                           for k, v in (payload.get("chart_band") or {}).items()}

    def chart_band_for(self, name: str) -> float | None:
        return self.chart_band.get(name)

    @classmethod
    def load(cls, path: Path | str | None = None) -> Calibration | None:
        path = Path(path) if path else PROFILE_PATH
        if not path.exists():
            return None
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def fits(self, n: int) -> bool:
        return n == self.n

    def weight_for(self, metric: str) -> np.ndarray:
        return self.weight_normal if metric == "normal" else self.weight

    def z(self, values: np.ndarray, metric: str = "euclid") -> np.ndarray:
        return (np.asarray(values, np.float32) * self.weight_for(metric)).astype(np.float32)

    def aggregate(self, values: np.ndarray, metric: str = "euclid") -> float:
        total = self.weight_normal_sum if metric == "normal" else self.weight_sum
        return float(np.asarray(values, np.float32).sum() / total)


def values_for_segment(a, b, previous, *, normals=None, metric="euclid",
                       weights=None, smooth_passes=0, triangles=None):
    """(start, end) значения карты для пары a→b при опоре на previous.

    weights — множители per-vertex (1/sigma); при взвешивании значения
    получаются в единицах шума, а не в долях IOD.
    """
    if metric not in METRICS:
        raise ValueError(f"Неизвестная метрика: {metric}")
    start = metric_values(a - previous, normals, metric)
    end = metric_values(b - a, normals, metric)
    if weights is not None:
        start = start * weights
        end = end * weights
    if smooth_passes and triangles is not None:
        start = smooth(start, triangles, smooth_passes)
        end = smooth(end, triangles, smooth_passes)
    return start, end


def compute_heat_values(a, b, previous, triangles, *, metric="euclid",
                        weighting="none", calibration=None, smooth_passes=0,
                        normals=None):
    """Значения карты для сегмента a→b; previous — опорный кадр сегмента.

    a, b, previous — словари с полем `vertices` (или массивы N×3).
    normals — готовое поле направлений; по умолчанию — нормали среднего лица,
    одинаковые для start и end, чтобы карта не рвалась на стыке сегментов.
    """
    if weighting not in WEIGHTING:
        raise ValueError(f"Неизвестное взвешивание: {weighting}")
    if weighting == "calibrated" and calibration is None:
        raise ValueError("weighting=calibrated требует профиль калибровки")
    if metric == "normal" and normals is None:
        normals = template_normals(triangles)
    weights = None
    if weighting == "calibrated" and calibration:
        weights = calibration.weight_for(metric)
    if weights is not None and not calibration.fits(len(np.asarray(a))):
        raise ValueError("Профиль калибровки не совпадает по числу вершин")
    start, end = values_for_segment(
        np.asarray(a), np.asarray(b), np.asarray(previous),
        normals=normals, metric=metric, weights=weights,
        smooth_passes=smooth_passes, triangles=triangles,
    )
    return {"start": start, "end": end, "metric": metric,
            "weighting": weighting, "normals": normals}


def segment_values(a, b, previous, triangles, mode, *, metric_name="distance",
                   smoothing=0, normals=None):
    """(start, end) сегмента a→b — одна формула для preview и export.

    mode — результат resolve(); a/b/previous — словари с vertices/identity.
    """
    out = compute_heat_values(
        np.asarray(space_array(a, metric_name)),
        np.asarray(space_array(b, metric_name)),
        np.asarray(space_array(previous, metric_name)),
        triangles,
        metric=mode["metric"], weighting=mode["weighting"],
        calibration=mode["calibration"], smooth_passes=smoothing,
        normals=normals,
    )
    return out["start"], out["end"]


def settings() -> dict:
    """Режим heatmap по умолчанию из configs/runtime.yaml."""
    import yaml

    doc = yaml.safe_load((ROOT / "configs/runtime.yaml").read_text())
    block = doc.get("heatmap") or {}
    return {
        "metric": block.get("metric", "euclid"),
        "weighting": block.get("weighting", "none"),
        "calibration_profile": block.get("calibration_profile",
                                         "reports/calibration/weights.json"),
    }


def active_calibration(mode: str | None = None):
    """Профиль, если режим включён и файл существует."""
    cfg = settings()
    mode = mode or cfg["weighting"]
    if mode != "calibrated":
        return None
    path = Path(cfg["calibration_profile"])
    return Calibration.load(path if path.is_absolute() else ROOT / path)


def resolve(metric: str | None = None, weighting: str | None = None,
            profile: str | None = None) -> dict:
    """Режим карты: аргументы запроса → configs/runtime.yaml.

    Preview, export и harness зовут одну эту функцию, поэтому metric и
    weighting не могут разойтись между путями рендера.
    """
    cfg = settings()
    metric = normalize_metric(metric or cfg["metric"])
    weighting = (weighting or cfg["weighting"]).strip().lower()
    if weighting not in WEIGHTING:
        raise ValueError(f"Неизвестное взвешивание: {weighting}")
    calibration = None
    if weighting == "calibrated":
        path = Path(profile or cfg["calibration_profile"])
        calibration = Calibration.load(path if path.is_absolute() else ROOT / path)
        if calibration is None:
            raise FileNotFoundError(f"нет профиля калибровки: {path}")
    return {"metric": metric, "weighting": weighting, "calibration": calibration,
            "vmax": VMAX[weighting]}
