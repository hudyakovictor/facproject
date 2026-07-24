"""🗺 Реестр привязки тестов к коду и стадиям пайплайна (система 'ворот').

Идея: каждая важная функция app6 закрыта блоком сценариев. Перед тем как
доверять результатам стадии или менять её код — гонятся сценарии её блоков.
status: implemented = сценарии уже есть в библиотеке; partial = частично; planned = запланировано."""
from __future__ import annotations

# Какие блоки сценариев обязаны быть зелёными, чтобы пройти ворота стадии.
STAGE_GATES: dict[str, dict] = {
    "stage1": {
        "synthetic": ["asset", "geometry"],
        "blocks": [],
        "note": "asset/topology + exact synthetic geometry before 3DDFA extraction",
    },
    "stage2": {
        "synthetic": ["asset", "geometry", "stage2"],
        "blocks": ["stability", "identity_change", "return", "rate", "same_day", "corroboration", "edge"],
        "note": "ядро анализа: все блоки",
    },
    "stage2b": {
        "synthetic": ["stage2"],
        "blocks": ["identity_change", "return"],
        "note": "приватная корроборация опирается на статусы смены/возврата",
    },
    "stage3": {
        "synthetic": ["stage2"],
        "blocks": ["identity_change", "stability", "rate"],
        "note": "отчёт не должен прятать красные статусы и рисовать ложные",
    },
}

# Привязка к конкретным функциям/модулям app6 — карта покрытия и план работ.
FUNCTION_MAP: list[dict] = [
    {"code": "stage2/multiple_testing.py:apply_pair_fdr", "blocks": ["stability"],
     "scenarios": ["S04_fdr_stress_A"], "status": "implemented",
     "what": "FDR-поправка (фикс N1): не более 10% ложно-значимых на одном человеке"},
    {"code": "stage2/engine.py:статусы пар (классификация)", "blocks": ["stability", "identity_change"],
     "scenarios": ["S01_stability_frontal_A", "S05_change_AB", "S07_series_AAABBB"], "status": "implemented",
     "what": "молчит на одном человеке, кричит на смене"},
    {"code": "stage2 — утечка позы (pose_leakage_diagnostic)", "blocks": ["stability"],
     "scenarios": ["S03_stability_all_poses_A"], "status": "implemented",
     "what": "разные ракурсы одного человека не дают ложных аномалий"},
    {"code": "stage2/baseline_return.py", "blocks": ["return"],
     "scenarios": ["S09_return_ABA", "S10_return_AABBAA", "S11_no_return_ABC"], "status": "implemented",
     "what": "возврат к базовой геометрии: есть при A-B-A, нет при A-B-C"},
    {"code": "stage2 — скорость изменений (chronology_rate_model)", "blocks": ["rate"],
     "scenarios": ["S12_rapid_change", "S13_slow_change", "S14_rapid_control_same"], "status": "implemented",
     "what": "rapid только при быстрой смене, не при медленной и не на одном человеке"},
    {"code": "stage2 — конфликт одного дня (same_day)", "blocks": ["same_day"],
     "scenarios": ["S15_same_day_ok", "S16_same_day_conflict", "S17_same_day_mixed"], "status": "implemented",
     "what": "конфликт только когда в один день реально разные люди"},
    {"code": "stage2/corroboration.py (фиксы N3a/N3b)", "blocks": ["corroboration"],
     "scenarios": ["S18_corroboration_multibin", "S19_corroboration_window", "S08_change_single_bin"], "status": "implemented",
     "what": "подтверждение только внутри временного окна и в нескольких ракурсах"},
    {"code": "stage2/alpha_chronology.py (фикс N2)", "blocks": ["identity_change"],
     "scenarios": ["S05_change_AB"], "status": "partial",
     "what": "отдельный сценарий на alpha_exp=NaN — запланирован (нужен кадр с эмоцией)"},
    {"code": "stage1/naming.py + хронология", "blocks": [],
     "scenarios": [], "status": "planned",
     "what": "FULL-дымовые тесты: дубли имён, повреждённые файлы, подпапки источников (фаза 3)"},
    {"code": "stage2/skin + текстурные метрики", "blocks": [],
     "scenarios": [], "status": "planned",
     "what": "заморожено до отдельного тестирования кожи (решение P0-4)"},
    {"code": "stage3/engine.py — визуализация статусов", "blocks": [],
     "scenarios": [], "status": "planned",
     "what": "автопроверка HTML: красные статусы попали в отчёт (фаза 2)"},
]


def gate_scenarios(stage: str, all_scenarios: list[dict], priority: str | None = None) -> list[dict]:
    """Список сценариев, которые должны быть зелёными для ворот стадии."""
    gate = STAGE_GATES.get(stage)
    if gate is None:
        raise SystemExit(f"неизвестная стадия: {stage}; доступны {sorted(STAGE_GATES)}")
    out = [s for s in all_scenarios if s["block"] in gate["blocks"]]
    if priority:
        out = [s for s in out if s["priority"] <= priority]  # P1 < P2 < P3
    return out
