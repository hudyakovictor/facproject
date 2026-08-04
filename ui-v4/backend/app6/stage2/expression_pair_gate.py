"""🚧 GATE → Контроль мимики в паре.

Кость не двигается, но открытая челюсть смещает подбородочные и щёчные точки.
Замер на 212 калибровочных кадрах (2026-08-03): пары с рассогласованием
jaw_open_detected дают медианный residual 0.070709 (n=14) против 0.002844 у
нейтральных (n=499). При контроле эпохи инфляция 10.8× (сырой замер 24.9×
без контроля эпохи). Это отдельный кластер.

Политика (F4): рассогласование флага внутри ОДНОЙ эпохи → исключение
(accepted=False, reason=jaw_state_mismatch). Между РАЗНЫМИ эпохами → страта
jaw_state_mismatch_cross_era (accepted=True, confidence=limited,
threshold_multiplier=10.8) — кросс-годовые пары не выбрасываются, но и не
смешиваются с чистыми (замер: безусловное исключение убивало 15 из 20
кросс-годовых пар, то есть временную ось исследования).

Порог по градусам (F5) приостановлен: JAW_DEGREE_GAP_ENFORCED=False, разрыв
пишется в jaw_degree_gap / jaw_degree_gap_exceeded, но пару не исключает.

⚠️ ИМЯ ФАЙЛА: в репозитории уже есть `expression_qc.py` (v2.0, мимические
зоны). Этот модуль — парный гейт по рассогласованию мимики, не заменяет его.
"""
from __future__ import annotations

from typing import Any, Final

EXPRESSION_PAIR_GATE_SCHEMA: Final[str] = "deeputin-expression-pair-gate-v1.0"

#: Разница степени открытия челюсти, выше которой пара считалась непригодной.
#: ПРИОСТАНОВЛЕН (F5, 2026-08-03): шкала jaw_open_degree несогласована внутри
#: набора — в 2006–2007 медиана 53–62 при jaw_open_detected=False, порог
#: отвечал за треть исключений (34 из 98). Снимается обратно, когда
#: jaw_open_degree станет согласован с jaw_open_detected в Stage 1.
MAX_JAW_DEGREE_GAP: Final[float] = 8.0
#: False → разрыв по градусам НЕ исключает пару, только пишется в поля
#: jaw_degree_gap / jaw_degree_gap_exceeded. True → вернуть жёсткое исключение.
JAW_DEGREE_GAP_ENFORCED: Final[bool] = False

# NOTE (2026-08-03): старый JAW_MISMATCH_INFLATION=1.46 удалён. Замер на 212
# кадрах: mismatch median 0.070709 (n=14) vs neutral 0.002844 (n=499). При
# контроле эпохи инфляция 10.8× (сырой 24.9× без контроля эпохи). Это
# отдельный кластер: исключение внутри эпохи, страта между эпохами.


def expression_gate(meta_a: dict[str, Any], meta_b: dict[str, Any],
                    *, era_a: str | None = None, era_b: str | None = None,
                    strict: bool = False) -> dict[str, Any]:
    """Fail-closed парный гейт мимики.

    - Рассогласование jaw_open_detected в ОДНУ эпоху → исключение
      (accepted=False, reason=jaw_state_mismatch).
    - Рассогласование в РАЗНЫЕ эпохи → страта jaw_state_mismatch_cross_era
      (accepted=True, confidence=limited, threshold_multiplier=10.8).
    - Эры не переданы → fail-closed: рассогласование исключает (как раньше).
    - Разрыв по градусам (JAW_DEGREE_GAP_ENFORCED=False) не исключает, а пишет
      jaw_degree_gap / jaw_degree_gap_exceeded.
    - Улыбка допускается со множителем 1.10.
    Параметр ``strict`` сохранён для совместимости вызова.
    """
    jaw_a = bool(meta_a.get("jaw_open_detected"))
    jaw_b = bool(meta_b.get("jaw_open_detected"))
    deg_a = float(meta_a.get("jaw_open_degree") or 0.0)
    deg_b = float(meta_b.get("jaw_open_degree") or 0.0)
    smile_a = bool(meta_a.get("smile_detected"))
    smile_b = bool(meta_b.get("smile_detected"))

    gap = abs(deg_a - deg_b)
    jaw_mismatch = jaw_a != jaw_b
    smile_mismatch = smile_a != smile_b
    gap_exceeded = gap > MAX_JAW_DEGREE_GAP

    if jaw_mismatch:
        if era_a is not None and era_b is not None and era_a != era_b:
            return {"schema": EXPRESSION_PAIR_GATE_SCHEMA, "accepted": True,
                    "reason": "", "stratum": "jaw_state_mismatch_cross_era",
                    "jaw_degree_gap": gap,
                    "jaw_degree_gap_exceeded": gap_exceeded,
                    "jaw_mismatch": True, "smile_mismatch": smile_mismatch,
                    "confidence": "limited", "threshold_multiplier": 10.8}
        return {"schema": EXPRESSION_PAIR_GATE_SCHEMA, "accepted": False,
                "reason": "jaw_state_mismatch", "jaw_degree_gap": gap,
                "jaw_degree_gap_exceeded": gap_exceeded,
                "jaw_mismatch": True, "smile_mismatch": smile_mismatch,
                "confidence": "excluded"}

    factor = 1.10 if smile_mismatch else 1.0
    return {"schema": EXPRESSION_PAIR_GATE_SCHEMA, "accepted": True,
            "threshold_multiplier": round(factor, 3),
            "jaw_mismatch": False, "smile_mismatch": smile_mismatch,
            "jaw_degree_gap": gap, "jaw_degree_gap_exceeded": gap_exceeded,
            "confidence": "reduced" if factor > 1.0 else "normal"}
