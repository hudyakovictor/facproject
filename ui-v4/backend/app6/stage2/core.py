"""
🎯 CRITICAL → Ядро Stage 2: сравнение ландмарков и калиброванные оценки.

compare_landmarks(a, b) — парное сравнение по хронологически выровненным ландмаркам
(ldm*_chronology из reconstruction.npz, патч 02), residual по зонам.
build_coordinate_zone_map — карта зон для фолдинга. robust_reference/calibrated_score —
медианный референс + z-подобный score относительно калибровки;
zone_weighted_score (#16) — взвешивание по зоновой значимости с pose-confidence.
🔗 Data contract: loaders.load_main → записи stage2/engine (фильтры пар).
⚠️ Pose-bin mismatch только корроборирует, не входит в primary residual + status_warning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

import os
import numpy as np

from .anchor_policy import per_bin_anchor_mask, stable_anchor_mask
from .analysis_policy import pose_gap
from .pose_policy import BIN_NAME_TO_YAW
from .robustness import noise_adjusted_threshold
from app6.stage1.status_logger import log_status, status_warning

# 🚧 Патч 6/A11: per-pose-bin anchor policy (subset_for_bin) из артефактов
# landmark_utility.npy + visibility_prior.npy. Управляется переменной
# DEEPUTIN_PER_BIN_ANCHOR (по умолчанию включено; 0 — отключить). Любая
# недостаточность подмножества откатывается на stable_anchor_mask.
_PER_BIN_ANCHOR_ENABLED = os.environ.get("DEEPUTIN_PER_BIN_ANCHOR", "1") != "0"
_BIN_NAMES: tuple[str, ...] = tuple(BIN_NAME_TO_YAW)
_PER_BIN_ARTIFACTS = None


def _load_per_bin_artifacts():
    """Lazy load of calibration-ranked landmark utility artifacts (A11)."""
    global _PER_BIN_ARTIFACTS
    if _PER_BIN_ARTIFACTS is not None:
        return _PER_BIN_ARTIFACTS
    if not _PER_BIN_ANCHOR_ENABLED:
        return None
    try:
        atlas = os.path.join(os.path.dirname(__file__), "..", "atlas")
        utility = np.load(os.path.join(atlas, "landmark_utility.npy"), allow_pickle=False)
        prior = np.load(os.path.join(atlas, "visibility_prior.npy"), allow_pickle=False)
        _PER_BIN_ARTIFACTS = (utility, prior, _BIN_NAMES)
    except Exception:
        _PER_BIN_ARTIFACTS = None
    return _PER_BIN_ARTIFACTS


@dataclass
class Record:
    record_id: str
    dataset_id: str
    date: str | None
    sequence: int
    pose_bin: str
    angles: np.ndarray
    ldm106: np.ndarray
    ldm134: np.ndarray
    visible106: np.ndarray
    visible134: np.ndarray
    alpha_id: np.ndarray
    alpha_exp: np.ndarray
    dataset_role: str = "evidence"
    date_precision: str = "day"
    capture_event: str | None = None
    identity_only106: np.ndarray | None = None
    identity_only134: np.ndarray | None = None
    quality_status: str = "unknown"
    quality_texture_score: float = 0.0
    forehead_wrinkle_supported: bool = False
    quality_zones: dict[str, Any] = field(default_factory=dict)
    record_dir: str | None = None
    source_group: str = "unknown"
    source_digest: str | None = None
    coordinate_noise_sigma: float = 0.0
    analysis_space:str="unknown"
    date_provenance_status:str="unknown"
    exif_date:str|None=None
    date_delta_days:int|None=None
    source_claimed_date:str|None=None
    source_claimed_delta_days:int|None=None
    date_conflict_sources:list[str]=field(default_factory=list)
    source_provenance:dict[str,Any]=field(default_factory=dict)
    perceptual_dhash:str|None=None
    near_duplicate_of:str|None=None

    def has_temporal_axis(self) -> bool:
        """Есть ли у записи действующая дата для хронологического анализа."""
        return self.date is not None and self.date_precision not in ("none", "unknown")

    def __post_init__(self) -> None:
        # Калибровочные кадры не участвуют в хронологии — снимаем ложные оси.
        if self.dataset_role == "calibration":
            self.date = None
            self.date_precision = "none"
            self.date_provenance_status = "not_applicable"


@dataclass
class Comparison:
    status: str
    metrics: dict[str, float]
    zones: list[dict[str, Any]]
    diagnostics: dict[str, Any]


def _rigid_align(source: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Kabsch row-vector alignment source -> target, without scale."""
    cs = source.mean(axis=0); ct = target.mean(axis=0)
    x = source - cs; y = target - ct
    u, _, vt = np.linalg.svd(x.T @ y)
    rotation = u @ vt
    if np.linalg.det(rotation) < 0:
        vt[-1] *= -1
        rotation = u @ vt
    translation = ct - cs @ rotation
    return source @ rotation + translation, rotation.astype(np.float32), translation.astype(np.float32)


# 🎯 CRITICAL → trimmed Kabsch с диагностикой (база всех align)
def robust_rigid_align(
    source: np.ndarray,
    target: np.ndarray,
    *,
    trim_fraction: float = 0.15,
    max_iterations: int = 5,
    min_points: int = 8,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Iteratively trimmed Kabsch alignment with diagnostics.

    Large local changes must not be absorbed into the global transform.  Each
    iteration fits on the lowest-residual subset and the final transform is
    applied to all source points.  No scale is estimated.
    """
    src = np.asarray(source, np.float64)
    dst = np.asarray(target, np.float64)
    if src.shape != dst.shape or src.ndim != 2 or src.shape[1] != 3:
        raise ValueError("source/target must have equal (N,3) shape")
    finite = np.isfinite(src).all(axis=1) & np.isfinite(dst).all(axis=1)
    ids = np.flatnonzero(finite)
    if ids.size < 3:
        raise ValueError("at least 3 finite point correspondences are required")
    if ids.size < min_points:
        aligned, rotation, translation = _rigid_align(src[finite], dst[finite])
        return aligned, rotation, translation, {
            "alignment_policy": "kabsch_insufficient_for_trimming",
            "fit_point_count": int(ids.size),
            "trimmed_point_count": 0,
            "iterations": 1,
        }
    keep = ids.copy()
    iterations = 0
    rotation = np.eye(3, dtype=np.float32)
    translation = np.zeros(3, dtype=np.float32)
    trim_fraction = float(np.clip(trim_fraction, 0.0, 0.4))
    for iterations in range(1, max_iterations + 1):
        _, rotation, translation = _rigid_align(src[keep], dst[keep])
        all_aligned = src @ rotation + translation
        residual = np.linalg.norm(all_aligned[ids] - dst[ids], axis=1)
        keep_n = max(min_points, int(np.ceil(ids.size * (1.0 - trim_fraction))))
        new_keep = ids[np.argsort(residual, kind="stable")[:keep_n]]
        if np.array_equal(np.sort(new_keep), np.sort(keep)):
            keep = new_keep
            break
        keep = new_keep
    _, rotation, translation = _rigid_align(src[keep], dst[keep])
    aligned_all = src @ rotation + translation
    before = np.linalg.norm(src[ids] - dst[ids], axis=1)
    after = np.linalg.norm(aligned_all[ids] - dst[ids], axis=1)
    return aligned_all.astype(np.float32), rotation, translation, {
        "alignment_policy": "iteratively_trimmed_kabsch_v1",
        "fit_point_count": int(keep.size),
        "input_point_count": int(ids.size),
        "trimmed_point_count": int(ids.size - keep.size),
        "iterations": int(iterations),
        "residual_before_median": float(np.median(before)),
        "residual_after_median": float(np.median(after)),
        "residual_after_p95": float(np.percentile(after, 95)),
    }


def _stats(distance: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(np.mean(distance * distance))),
        "median": float(np.median(distance)),
        "p95": float(np.percentile(distance, 95)),
        "max": float(np.max(distance)),
    }


#: Источник измеренного качества выравнивания (патч 15).
ALIGNMENT_QUALITY_SOURCE: Final[str] = "measured_residual_v1"


def measured_alignment_quality(distance: np.ndarray) -> dict[str, Any]:
    """Качество выравнивания по распределению остатков.

    Не зависящий от модели признак: высокая медиана при низком trim-дрейфе
    означает локальные расхождения (мимика/костные изменения), которые trim
    сбросил в глобальный остаток, — именно они — предмет измерения.
    """
    d = np.asarray(distance, np.float64)
    finite = np.isfinite(d)
    d = d[finite]
    if d.size == 0:
        return {"source": ALIGNMENT_QUALITY_SOURCE, "status": "no_finite_points",
                "n_points": 0}
    p50 = float(np.median(d))
    p95 = float(np.percentile(d, 95))
    maxv = float(np.max(d))
    consistency = float(np.mean(d <= 2.5 * p50)) if p50 > 0 else 1.0
    return {"source": ALIGNMENT_QUALITY_SOURCE,
            "median_residual": p50, "p95_residual": p95, "max_residual": maxv,
            "consistency_fraction": round(consistency, 4),
            "n_points": int(d.size)}


def compare_landmarks(
    a: Record,
    b: Record,
    zone_map106: np.ndarray,
    zone_map134: np.ndarray,
    min_points106: int = 24,
    min_points134: int = 30,
    max_pose_distance: float = 2.5,
) -> Comparison:
    """🎯 CRITICAL → Сравнение ландмарков двух фото (ядро хронологии).

    Использует Kabsch alignment (robust_rigid_align) для выравнивания,
    затем вычисляет residual (разницу) для каждой точки.

    🔗 DEPENDS ON:
      - engine.run() — вызывается для каждой пары
      - Record.ldm134 — ДОЛЖЕН быть chronology-aligned (полная pose коррекция)
      - Record.visible134 — маска видимых точек

    APPLICABILITY:
      - Использует только общие visible landmarks.
      - Пары из разных pose bins отклоняются со статусом ``pose_mismatch``.
      - Pair-level alignment/quality gates применяются оркестратором до вызова.

    💡 NOTE:
      - Использует iteratively-trimmed Kabsch (15% trim)
      - Identity-only landmarks для expression-robust comparison
      - Zones — координатная сетка (3x3), не анатомические!

    🚨 WARNING:
      - Если Record.ldm134 НЕ chronology-aligned — результаты недостоверны!
      - При insufficient visibility (< 30 common points) — статус "insufficient_visibility"
    """
    log_status("compare_landmarks", "complete")
    if a.pose_bin != b.pose_bin:
        status_warning("compare_landmarks", f"Pose bin mismatch: {a.pose_bin} vs {b.pose_bin}")
        return Comparison(
            "pose_mismatch",
            {},
            [],
            {
                "pose_bin_a": a.pose_bin,
                "pose_bin_b": b.pose_bin,
                "pose_distance": float(
                    np.linalg.norm((a.angles - b.angles) / np.array([15.0, 20.0, 15.0]))
                ),
            },
        )

    gap = pose_gap(a.angles, b.angles, pose_bin=a.pose_bin)
    pose_distance = float(np.linalg.norm((a.angles - b.angles) / np.array([15.0, 20.0, 15.0])))
    if not gap.accepted:
        return Comparison("residual_pose_mismatch", {}, [], {
            "pose_distance": pose_distance, "pose_gap_reason": gap.reason,
            "pitch_gap_deg": gap.pitch, "yaw_gap_deg": gap.yaw, "roll_gap_deg": gap.roll,
        })

    common106 = np.asarray(a.visible106, bool) & np.asarray(b.visible106, bool)
    common134 = np.asarray(a.visible134, bool) & np.asarray(b.visible134, bool)
    diagnostics = {
        "common_visible106": int(common106.sum()), "common_visible134": int(common134.sum()),
        "coverage106": float(common106.mean()), "coverage134": float(common134.mean()),
        "pose_distance": pose_distance,
    }
    if common106.sum() < min_points106 or common134.sum() < min_points134:
        return Comparison("insufficient_visibility", {}, [], diagnostics)

    anchor106, anchor_meta106 = stable_anchor_mask(a.ldm106, common106, min_count=min_points106)
    _per_bin = _load_per_bin_artifacts()
    if _per_bin is not None:
        _utility, _prior, _bin_names = _per_bin
        anchor134, anchor_meta134 = per_bin_anchor_mask(a.ldm134, common134, pose_bin=a.pose_bin, utility=_utility, visibility_prior=_prior, min_count=min_points134, bin_names=_bin_names)
    else:
        anchor134, anchor_meta134 = stable_anchor_mask(a.ldm134, common134, min_count=min_points134)
    _, r106, t106, align106 = robust_rigid_align(b.ldm106[anchor106], a.ldm106[anchor106])
    _, r134, t134, align134 = robust_rigid_align(b.ldm134[anchor134], a.ldm134[anchor134])
    aligned106_all = b.ldm106 @ r106 + t106
    aligned134_all = b.ldm134 @ r134 + t134
    residual106 = aligned106_all[common106] - a.ldm106[common106]
    residual134 = aligned134_all[common134] - a.ldm134[common134]
    distance106 = np.linalg.norm(residual106, axis=1)
    distance134 = np.linalg.norm(residual134, axis=1)
    s106, s134 = _stats(distance106), _stats(distance134)
    def _alpha_l2(x: np.ndarray, y: np.ndarray) -> float:
        xa = np.asarray(x, np.float64).reshape(-1)
        ya = np.asarray(y, np.float64).reshape(-1)
        if xa.size == 0 or ya.size == 0 or xa.shape != ya.shape:
            return float("nan")
        if not (np.isfinite(xa).all() and np.isfinite(ya).all()):
            # Missing/disabled alpha must not become zeros or crash JSON later.
            return float("nan")
        return float(np.linalg.norm(xa - ya))

    metrics = {
        **{f"ldm106_{k}": v for k, v in s106.items()},
        **{f"ldm134_{k}": v for k, v in s134.items()},
        "alpha_id_l2": _alpha_l2(a.alpha_id, b.alpha_id),
        "alpha_exp_l2": _alpha_l2(a.alpha_exp, b.alpha_exp),
    }
    if a.identity_only134 is not None and b.identity_only134 is not None:
        _, ir, it, _ = robust_rigid_align(b.identity_only134[anchor134], a.identity_only134[anchor134])
        identity_aligned_all = b.identity_only134 @ ir + it
        metrics["identity_only_ldm134_rmse"] = float(np.sqrt(np.mean(np.sum((identity_aligned_all[common134] - a.identity_only134[common134]) ** 2, axis=1))))

    zones: list[dict[str, Any]] = []
    visible_indices134 = np.flatnonzero(common134)
    for zone_id in np.unique(zone_map134):
        local = zone_map134[visible_indices134] == zone_id
        if int(local.sum()) < 4:
            zones.append({"zone": str(zone_id), "status": "insufficient_visibility", "point_count": int(local.sum())})
            continue
        rv = residual134[local]; dist = np.linalg.norm(rv, axis=1)
        zones.append({
            "zone": str(zone_id), "status": "measured", "point_count": int(local.sum()),
            "rmse": float(np.sqrt(np.mean(dist * dist))), "median": float(np.median(dist)),
            "p95": float(np.percentile(dist, 95)),
            "signed_x": float(np.median(rv[:, 0])), "signed_y": float(np.median(rv[:, 1])),
            "signed_z": float(np.median(rv[:, 2])),
        })
    diagnostics.update({"rotation106": r106, "translation106": t106, "rotation134": r134, "translation134": t134,
                        "anchor106_count": anchor_meta106.get("anchor_count", 0), "anchor106_policy": anchor_meta106.get("anchor_policy", "unknown"), "anchor106_source": anchor_meta106.get("anchor_source", "unknown"),
                        "anchor134_count": anchor_meta134.get("anchor_count", 0), "anchor134_policy": anchor_meta134.get("anchor_policy", "unknown"),
                        "anchor134_source": anchor_meta134.get("anchor_source", "unknown"),
                        "anchor134_artifacts": bool(_per_bin is not None),
                        "alignment106_policy": align106.get("alignment_policy"), "alignment106_trimmed_count": align106.get("trimmed_point_count", 0),
                        "alignment134_policy": align134.get("alignment_policy"), "alignment134_trimmed_count": align134.get("trimmed_point_count", 0),
                        "alignment134_residual_before_median": align134.get("residual_before_median"),
                        "alignment134_residual_after_median": align134.get("residual_after_median"),
                        "alignment_quality_measured": measured_alignment_quality(distance134)})
    return Comparison("measured", metrics, zones, diagnostics)


def build_coordinate_zone_map(records: list[Record], landmark_count: int) -> tuple[np.ndarray, dict[str, Any]]:
    """Nine reproducible coordinate zones; avoids unverified anatomical labels."""
    log_status("build_coordinate_zone_map", "complete")
    if not records:
        raise ValueError("cannot build zones without records")
    stack = np.stack([r.ldm106 if landmark_count == 106 else r.ldm134 for r in records[: min(200, len(records))]])
    template = np.median(stack, axis=0)
    qx = np.quantile(template[:, 0], [1 / 3, 2 / 3]); qy = np.quantile(template[:, 1], [1 / 3, 2 / 3])
    xb = np.digitize(template[:, 0], qx); yb = np.digitize(template[:, 1], qy)
    names = np.array([[f"x_{x}_{y}" for x in ("low", "center", "high")] for y in ("low", "center", "high")])
    labels = names[yb, xb]
    meta = {"version": "coordinate-grid-v1", "landmark_count": landmark_count, "qx": qx.tolist(), "qy": qy.tolist(),
            "warning": "Coordinate zones are not anatomical labels."}
    return labels, meta


def robust_reference(values: list[float]) -> dict[str, float | int]:
    log_status("robust_reference", "complete")
    arr = np.asarray([v for v in values if np.isfinite(v)], np.float64)
    if arr.size == 0:
        return {"count": 0, "median": 0.0, "mad": 0.0, "p95": 0.0, "p99": 0.0}
    median = float(np.median(arr)); mad = float(np.median(np.abs(arr - median)))
    return {"count": int(arr.size), "median": median, "mad": mad,
            "p95": float(np.percentile(arr, 95)), "p99": float(np.percentile(arr, 99))}


def calibrated_score(
    value: float, reference: dict[str, float | int], matched: list[float],
    *, coordinate_noise_sigma: float = 0.0,
) -> dict[str, float | str]:
    """📊 METRIC — Calibrated score для одного значения.

    Сравнивает value с калибровочным распределением (same-person noise).
    Возвращает z-score и статус.
    """
    log_status("calibrated_score", "complete")
    # 🚧 GATE (D1): нефинитное значение не является измерением. Без этой проверки
    # NaN проваливался во все сравнения (NaN<=x и NaN<3.5 равны False) и получал
    # статус "elevated", то есть отсутствие данных выглядело как аномалия.
    # Для sidecar-калибровки alpha_id_l2/alpha_exp_l2 всегда NaN — баг срабатывал
    # на каждой паре. Отсутствующие данные не подменяются нулём (см. AGENTS.md).
    value_f = float(value)
    if not np.isfinite(value_f):
        return {"calibration_median": float(reference.get("median", 0.0)),
                "calibration_p95": float(reference.get("p95", 0.0)),
                "calibration_p95_unadjusted": float(reference.get("p95", 0.0)),
                "coordinate_noise_sigma": float(coordinate_noise_sigma),
                "robust_z": float("nan"), "status": "not_measurable"}
    matched_arr = np.asarray([v for v in matched if np.isfinite(v)], np.float64)
    threshold = float(reference.get("p95", 0.0))
    if matched_arr.size:
        threshold = max(threshold, float(np.percentile(matched_arr, 95)))
    unadjusted_threshold = threshold
    if coordinate_noise_sigma > 0:
        threshold = noise_adjusted_threshold(threshold, coordinate_noise_sigma)
    median = float(reference.get("median", 0.0)); mad = float(reference.get("mad", 0.0))
    z = float((value - median) / max(1.4826 * mad, 1e-8))
    if int(reference.get("count", 0)) < 7:
        status = "insufficient_calibration"
    elif value <= threshold:
        status = "within_calibration_noise"
    elif z < 3.5:
        status = "elevated_but_uncertain"
    else:
        status = "elevated"
    return {"calibration_median": median, "calibration_p95": threshold,
            "calibration_p95_unadjusted": unadjusted_threshold,
            "coordinate_noise_sigma": float(coordinate_noise_sigma),
            "robust_z": z, "status": status}


# 📊 Веса координатной сетки 3x3 для zone_weighted_score.
#
# 🚨 WARNING (D11): это НЕ анатомические и НЕ костные зоны. Ключи вида
# `x_low_low` — ячейки координатной сетки из build_coordinate_zone_map, которая
# явно документирует: "Coordinate zones are not anatomical labels". Прежний
# комментарий называл их "bone zones", что противоречило самому коду.
# Анатомические зоны живут в mesh_zone_indices.json и применяются в mesh_dense.
# Центральная ячейка имеет больший вес как наиболее стабильная и наблюдаемая
# во всех ракурсах, а не потому, что она "костная".
ZONE_WEIGHTS = {
    # Верхний ряд сетки — наиболее стабильная область (лоб/глазницы).
    "x_low_low": 1.0, "x_center_low": 1.0, "x_high_low": 1.0,
    "x_low_center": 0.9, "x_center_center": 1.2, "x_high_center": 0.9,
    "x_low_high": 0.7, "x_center_high": 0.8, "x_high_high": 0.7,
}


def zone_weighted_score(zone_rmse: dict[str, float], zone_map: np.ndarray,
                        visible_indices: np.ndarray,
                        reference: dict[str, float | int],
                        matched: list[float]) -> dict[str, float | str]:
    """📊 METRIC — Zone-weighted calibrated score.

    Учитывает что разные зоны имеют разную важность:
    - Костные зоны (лоб, нос, скулы) = высокий вес
    - Мягкие ткани (челюсть, щёки) = низкий вес

    Args:
        zone_rmse: {zone_name: rmse} для каждой зоны
        zone_map: массив зон для каждой точки
        visible_indices: индексы видимых точек
        reference: калибровочное распределение
        matched: matched calibration values

    Returns:
        dict с weighted_z, weighted_status, per_zone_scores
    """
    log_status("zone_weighted_score", "complete")
    if not zone_rmse:
        return {"weighted_z": 0.0, "weighted_status": "no_zones", "per_zone_scores": {}}

    weighted_z_sum = 0.0
    weight_sum = 0.0
    per_zone_scores = {}

    for zone_name, rmse in zone_rmse.items():
        weight = ZONE_WEIGHTS.get(zone_name, 0.5)
        score = calibrated_score(rmse, reference, matched)
        z = score["robust_z"]
        weighted_z_sum += z * weight
        weight_sum += weight
        per_zone_scores[zone_name] = {
            "rmse": rmse,
            "z": z,
            "weight": weight,
            "status": score["status"],
        }

    avg_z = weighted_z_sum / max(weight_sum, 1e-8)

    # Status based on weighted z
    if avg_z < 0:
        status = "within_calibration_noise"
    elif avg_z < 3.5:
        status = "elevated_but_uncertain"
    else:
        status = "elevated"

    return {
        "weighted_z": float(avg_z),
        "weighted_status": status,
        "per_zone_scores": per_zone_scores,
    }
