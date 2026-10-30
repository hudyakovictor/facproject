"""Ряд графика Timeline: значения шага хронологии из server.heat.

График не считает собственную формулу. Каждый шаг — пара соседних кадров,
значение берётся из `compute_heat_values` (тот же helper, что heatmap),
агрегируется по вершинам и получает ожидаемый шумовой уровень `band`
из профиля калибровки. Фильтр (медиана) применяется только к отображению:
`value_raw` всегда сохраняется отдельно.

    from server.chart import series
    rows = series(frames, triangles, metric="weighted_normal")
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from server.config import ROOT
from server.heat import Calibration, compute_heat_values, resolve, template_normals

METRICS = ("euclid", "normal", "weighted_euclid", "weighted_normal")
FILTERS = ("none", "median")
WINDOWS = (3, 5)
Z_LEVELS = (1.0, 3.0)


def settings() -> dict:
    """Блок chart из configs/runtime.yaml."""
    import yaml

    doc = yaml.safe_load((ROOT / "configs/runtime.yaml").read_text())
    block = doc.get("chart") or {}
    return {
        "metric": block.get("metric", "euclid"),
        "weighting": block.get("weighting", "none"),
        "temporal_filter": block.get("temporal_filter", "none"),
        "filter_window": int(block.get("filter_window", 3)),
        "calibration_profile": block.get(
            "calibration_profile", "reports/calibration/weights.json"
        ),
    }


def mode(metric: str | None = None, weighting: str | None = None,
         profile: str | Path | None = None) -> dict:
    """Режим графика: euclid | normal | weighted_euclid | weighted_normal."""
    cfg = settings()
    name = (metric or cfg["metric"]).strip().lower()
    if name not in METRICS:
        raise ValueError(f"Неизвестный режим графика: {name}")
    base = "normal" if name.endswith("normal") else "euclid"
    weight = "calibrated" if name.startswith("weighted") else "none"
    if weighting:
        weight = weighting.strip().lower()
    out = resolve(base, weight, profile or cfg["calibration_profile"])
    out["name"] = ("weighted_" if out["weighting"] == "calibrated" else "") + out["metric"]
    # Профиль нужен и без взвешивания: по нему считаются z и band.
    if out["calibration"] is None:
        path = Path(profile or cfg["calibration_profile"])
        out["calibration"] = Calibration.load(path if path.is_absolute() else ROOT / path)
    return out


def median_window(values: list[float], window: int) -> list[float]:
    """Медианное окно для отображения; край — по доступным точкам."""
    if window not in WINDOWS:
        raise ValueError("Окно фильтра: 3 или 5")
    half = window // 2
    out = []
    for i in range(len(values)):
        chunk = values[max(0, i - half): i + half + 1]
        out.append(float(np.median(chunk)))
    return out


def step(a: np.ndarray, b: np.ndarray, triangles: np.ndarray, cfg: dict,
         normals: np.ndarray | None = None) -> dict:
    """Один шаг хронологии a→b: агрегаты и шумовой уровень."""
    out = compute_heat_values(
        np.asarray(a), np.asarray(b), np.asarray(a), triangles,
        metric=cfg["metric"], weighting=cfg["weighting"],
        calibration=cfg["calibration"], normals=normals,
    )
    values = np.asarray(out["end"], np.float64)
    cal = cfg["calibration"]
    if cal is None:
        row = {"value_raw": float(values.mean()), "band": None, "z_mean": None,
               "z_p95": None, "frac_z_gt3": None, "low_confidence_fraction": None}
    else:
        weights = cal.weight_for(cfg["metric"])
        calibrated = cfg["weighting"] == "calibrated"
        # Взвешенные значения helper уже отдаёт в единицах шума (|d| * 1/sigma),
        # поэтому повторно умножать их на вес нельзя.
        z = values if calibrated else values * weights
        sigma = cal.sigma_normal if cfg["metric"] == "normal" else cal.sigma
        if calibrated:
            total = cal.weight_normal_sum if cfg["metric"] == "normal" else cal.weight_sum
            value = float(values.sum() / max(total, 1e-9))
        else:
            value = float(values.mean())
        # band — шум агрегата из профиля (спокойные шаги корпуса). Без него —
        # стандартная ошибка среднего по сигмам вершин.
        band = cal.chart_band_for(cfg["name"])
        if band is None:
            if calibrated:
                band = float(np.sqrt(len(values)) / max(float(weights.sum()), 1e-9))
            else:
                band = float(np.sqrt(np.sum(np.asarray(sigma, np.float64) ** 2)) /
                             max(len(values), 1))
        row = {
            "value_raw": value,
            "band": band,
            "z_mean": float(z.mean()),
            "z_p95": float(np.percentile(z, 95)),
            "frac_z_gt3": float((z > 3).mean()),
            "low_confidence_fraction": float((z < 1).mean()),
        }
    row["significance"] = (
        None if row["band"] in (None, 0) else float(row["value_raw"] / row["band"])
    )
    return row


def series(frames: list, triangles: np.ndarray, cfg: dict, *,
           temporal_filter: str = "none", window: int = 3,
           normals: np.ndarray | None = None) -> list[dict]:
    """Ряд по шагам: value_raw/value_display/band/significance."""
    if len(frames) < 2:
        return []
    if temporal_filter not in FILTERS:
        raise ValueError(f"Неизвестный фильтр: {temporal_filter}")
    if normals is None:
        normals = template_normals(triangles)
    rows = []
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        if isinstance(a, dict):
            a = a["vertices"]
        if isinstance(b, dict):
            b = b["vertices"]
        row = step(a, b, triangles, cfg, normals=normals)
        row.update({"from": i - 1, "to": i})
        rows.append(row)
    raw = [r["value_raw"] for r in rows]
    display = raw if temporal_filter == "none" else median_window(raw, window)
    for row, value in zip(rows, display, strict=True):
        row["value_display"] = value
    return rows
