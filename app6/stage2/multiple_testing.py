"""📊 METRIC → Множественная проверка гипотез: BH FDR по парам и зонам.
🚪 API: apply_pair_fdr(), apply_zone_fdr()
💡 NOTE: _p_from_z через erfc-аппроксимацию — стабильно на малых p.
"""
from __future__ import annotations
from app6.stage1.status_logger import log_status

from math import erfc, exp, isfinite, lgamma, log, log1p, sqrt
from typing import Any

MT_SCHEMA = "deeputin-stage2-multiple-testing-v1.0"


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


def _bh_qvalues(items: list[tuple[int, float]]) -> dict[int, float]:
    if not items:
        return {}
    ordered = sorted(items, key=lambda x: x[1])
    m = len(ordered)
    q = [1.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        idx, p = ordered[rank - 1]
        val = min(prev, p * m / rank)
        q[rank - 1] = val
        prev = val
    return {ordered[i][0]: max(0.0, min(1.0, q[i])) for i in range(m)}


def apply_pair_fdr(rows: list[dict[str, Any]], *, z_key: str = "p95_point_z", q_threshold: float = 0.10) -> dict[str, Any]:
    log_status("apply_pair_fdr", "complete")
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
        # 🔧 FIX (аудит N1): p95 из m точек — порядковая статистика, не одиночный z.
        p = _p_from_p95_z(z_value, m_points) if m_points >= 20 else _p_from_z(z_value)
        r["mt_p_approx"] = p
        tests.append((i, p))
    qmap = _bh_qvalues(tests)
    significant = 0
    for i, q in qmap.items():
        rows[i]["mt_q_value"] = q
        flag = bool(q <= q_threshold)
        rows[i]["mt_significant_fdr10"] = flag  # legacy alias
        rows[i]["mt_fdr10_diagnostic_flag"] = flag  # explicit: not a verdict
        rows[i]["mt_role"] = "diagnostic_only"
        significant += int(flag)
    return {
        "schema": MT_SCHEMA,
        "scope": "pair_metrics",
        "test_count": len(tests),
        "q_threshold": q_threshold,
        "significant_count": significant,
        "diagnostic_only": True,
        "not_a_verdict": True,
        "method": "Benjamini-Hochberg on order-statistic p for p95 of m calibrated point z-scores (independence approximation; DIAGNOSTIC ONLY; do not use as identity/material verdict)",
    }


def apply_zone_fdr(zones: list[dict[str, Any]], *, z_key: str = "robust_z", q_threshold: float = 0.10) -> dict[str, Any]:
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
