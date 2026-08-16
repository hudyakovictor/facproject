"""📊 METRIC → Множественная проверка гипотез: BH FDR по парам и зонам.
🚪 API: apply_pair_fdr(), apply_zone_fdr()
💡 NOTE: _p_from_z через erfc-аппроксимацию — стабильно на малых p.
"""
from __future__ import annotations
from app6.stage1.status_logger import log_status

from math import erfc, exp, isfinite, lgamma, log, log1p, sqrt
from typing import Any

import numpy as np

from app6.stage2.fdr_control import benjamini_hochberg

MT_SCHEMA = "deeputin-stage2-multiple-testing-v1.2"
DEFAULT_FDR_LEVEL = 0.05


def _p_from_z(z: float) -> float:
    try:
        z = abs(float(z))
        return max(0.0, min(1.0, erfc(z / sqrt(2.0))))
    except Exception:
        return 1.0


def _p_from_p95_z(z: float, m: int) -> float:
    """🔧 FIX (аудит N1): p-value для 95-го перцентиля m z-скоров.

    Раньше p95_point_z трактовался как одиночный N(0,1) z — под нулевой гипотезой
    p95 из ~134 значений ~1.65, поэтому почти каждая пара выглядела "значимой".
    Порядковая статистика: p95 > t <=> число превышений |z|>t >= k, k = floor(0.05*m)+1,
    X ~ Binomial(m, q), q = P(|Z|>t). Допущение независимости точек — приближение;
    предпочтительная замена в будущем — эмпирический null p95_point_z из
    пересчитанного калибровочного датасета.
    """
    try:
        z = abs(float(z)); m = max(int(m), 1)
    except Exception:
        return 1.0
    q = max(min(erfc(z / sqrt(2.0)), 1.0), 1e-300)
    if q >= 1.0:
        return 1.0
    k = int(0.05 * m) + 1
    total = 0.0
    for j in range(k, m + 1):
        lp = (lgamma(m + 1) - lgamma(j + 1) - lgamma(m - j + 1)
              + j * log(q) + (m - j) * log1p(-q))
        total += exp(lp)
    return max(0.0, min(1.0, total))


def _bh_qvalues(items: list[tuple[int, float]],
                *, m_override: int | None = None) -> dict[int, float]:
    """Thin wrapper around fdr_control.benjamini_hochberg — single canonical BH."""
    if not items:
        return {}
    ordered = sorted(items, key=lambda x: x[1])
    idx_list = [i for i, _ in ordered]
    p_values = np.array([p for _, p in ordered], dtype=np.float64)
    adjusted, _ = benjamini_hochberg(p_values, fdr_level=1.0)  # raw q-values
    # Apply m_override scaling for dependence-inflation (patch 8)
    m = len(items)
    scale = 1.0
    if m_override is not None:
        scale = max(1.0, m / float(max(1, int(m_override))))
    # Scale and emit in original order
    result: dict[int, float] = {}
    for order_idx, orig_idx in enumerate(idx_list):
        result[orig_idx] = max(0.0, min(1.0, float(adjusted[order_idx]) * scale))
    return result


def apply_pair_fdr(rows: list[dict[str, Any]], *, z_key: str = "p95_point_z",
                   q_threshold: float = DEFAULT_FDR_LEVEL,
                   photo_count: int | None = None) -> dict[str, Any]:
    log_status("apply_pair_fdr", "complete")
    # Пары одного фото — зависимые наблюдения. Эффективное число независимых
    # тестов ограничено числом фото: n_eff = photo_count // 2 (пары считаются
    # попарно, но не более чем по одной «хорошей» паре на два фото).
    n_eff = None if photo_count is None else max(1, int(photo_count) // 2)
    tests: list[tuple[int, float]] = []
    for i, r in enumerate(rows):
        z = r.get(z_key)
        if z is None:
            continue
        try:
            z_value = float(z)
        except (TypeError, ValueError):
            continue
        if not isfinite(z_value):
            continue
        m_points = int(r.get("calibrated_point_count") or 0)
        if m_points >= 20:
            # 🔧 FIX (аудит N1): p95 из m точек — порядковая статистика.
            p = _p_from_p95_z(z_value, m_points)
            r["mt_point_support"] = "full"
            r["mt_role_detail"] = "p95_order_statistic_v1"
        else:
            # Мало точек → порядковая статистика ненадёжна, одиночный z fallback.
            p = _p_from_z(z_value)
            r["mt_point_support"] = "limited"
            r["mt_role_detail"] = "p95_order_statistic_unreliable_below_20_points; single-z fallback"
        r["mt_p_approx"] = p
        tests.append((i, p))
    qmap = _bh_qvalues(tests, m_override=n_eff)
    significant = 0
    for i, q in qmap.items():
        rows[i]["mt_q_value"] = q
        flag = bool(q <= q_threshold)
        rows[i]["mt_significant_fdr10"] = flag  # legacy alias
        rows[i]["mt_fdr10_diagnostic_flag"] = flag  # explicit: not a verdict
        rows[i]["mt_role"] = "diagnostic_only"
        significant += int(flag)
    dependence_inflation = 1.0
    if n_eff is not None and tests:
        dependence_inflation = max(1.0, len(tests) / float(n_eff))
    return {
        "schema": MT_SCHEMA,
        "scope": "pair_metrics",
        "test_count": len(tests),
        "effective_test_count": n_eff,
        "dependence_inflation": round(dependence_inflation, 4),
        "independence_policy": "photo_cluster_v1",
        "independence_note": ("пары из одного фото кластеризованы; "
                              "n_eff = photo_count // 2; ранжирование по всем m"),
        "q_threshold": q_threshold,
        "significant_count": significant,
        "diagnostic_only": True,
        "not_a_verdict": True,
        "method": "Benjamini-Hochberg on order-statistic p for p95 of m calibrated point z-scores; q scaled by dependence inflation (DIAGNOSTIC ONLY; do not use as identity/material verdict)",
    }


def apply_zone_fdr(zones: list[dict[str, Any]], *, z_key: str = "robust_z", q_threshold: float = DEFAULT_FDR_LEVEL) -> dict[str, Any]:
    log_status("apply_zone_fdr", "complete")
    tests: list[tuple[int, float]] = []
    for i, zrow in enumerate(zones):
        if zrow.get("status") != "measured" and zrow.get("mesh_zone_status") != "measured":
            continue
        z = zrow.get(z_key)
        if z is None:
            continue
        try:
            z_value = float(z)
        except (TypeError, ValueError):
            continue
        if not isfinite(z_value):
            continue
        p = _p_from_z(z_value)
        zrow["mt_p_approx"] = p
        tests.append((i, p))
    qmap = _bh_qvalues(tests)
    significant = 0
    for i, q in qmap.items():
        zones[i]["mt_q_value"] = q
        flag = bool(q <= q_threshold)
        zones[i]["mt_significant_fdr10"] = flag
        zones[i]["mt_fdr10_diagnostic_flag"] = flag
        zones[i]["mt_role"] = "diagnostic_only"
        significant += int(flag)
    return {
        "schema": MT_SCHEMA,
        "scope": "zone_metrics",
        "test_count": len(tests),
        "q_threshold": q_threshold,
        "significant_count": significant,
        "diagnostic_only": True,
        "not_a_verdict": True,
        "method": "Benjamini-Hochberg on approximate p-values (DIAGNOSTIC ONLY)",
    }
