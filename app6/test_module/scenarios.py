"""📚 Библиотека сценариев v1 (21 шт). Каждый сценарий = кадры + ожидания-инварианты.
Плейсхолдеры людей: A=person_01, A2=person_04, B=person_02, C=person_03, D=person_05.
При генерации комбинаций каждый вариант получает свой набор людей из PERSON_SETS
или детерминированной перестановки доступных людей.
Даты условные — они задают хронологию теста, а не реальное время съёмки."""
from __future__ import annotations
from itertools import permutations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_module.config import RED_STATUSES, SCENARIOS_DIR

A, A2, B, C, D = "A", "A2", "B", "C", "D"
CHANGE = ["coherent_jump_candidate", "alpha_id_jump_candidate", "persistent_geometric_change"]
RAPID = ["rapid_change_candidate", "persistent_rapid_change_candidate"]
RED = sorted(RED_STATUSES)

ALL_PERSONS = tuple(f"person_{i:02d}" for i in range(1, 8))
POSE_NO_TO_BIN = {
    1: "left_profile",
    2: "left_deep",
    3: "left_mid",
    4: "left_light",
    5: "frontal",
    6: "right_light",
    7: "right_mid",
    8: "right_deep",
    9: "right_profile",
}
POSE_NO_TO_YAW = {1: -70.0, 2: -45.0, 3: -32.5, 4: -17.5, 5: 0.0, 6: 17.5, 7: 32.5, 8: 45.0, 9: 70.0}
YAW_TO_REFERENCE_POSE = {0: 5, -20: 4, 20: 6, -45: 2, 45: 8, -70: 1, 70: 9}

# Сколько комбинаций генерировать по умолчанию для каждого теста.
# -1 в CLI означает минимальный development-режим: 1 комбинация на тест.
# Позже здесь можно точечно поставить, например, {"S18_corroboration_multibin": 15}.
DEFAULT_COMBINATIONS_BY_SCENARIO: dict[str, int] = {}


def _norm_combo_count(value: int | str | None) -> int:
    """-1/0/None => 1, положительное число => столько комбинаций."""
    if value is None:
        return 1
    n = int(value)
    return 1 if n <= 0 else n


def person_set(variant: int) -> tuple[str, str, str, str, str]:
    """Balanced deterministic roles for seven curated people.

    For the development contract combinations are intentionally limited to 1..7.
    c00..c06 rotate people so every person appears in the key roles. The 21
    scenarios still use their historical roles A/A2/B/C/D, but no scenario needs
    more than three distinct people for its actual anomaly logic.
    """
    if variant < 7:
        people = ALL_PERSONS
        a = people[variant % 7]
        b = people[(variant + 1) % 7]
        c = people[(variant + 2) % 7]
        d = people[(variant + 3) % 7]
        # A2 is a separate same-person-control role for S02 only.
        return (a, b, b, c, d)
    idx = variant - 7
    for i, combo in enumerate(permutations(ALL_PERSONS, 5)):
        if i == idx:
            return combo
    raise ValueError(f"слишком много комбинаций: {variant}; максимум {7 + 2520}")


def parse_pose(value: str | int | None) -> list[int]:
    """frontal -> [5], all -> [1..9], or a concrete pose number."""
    if value is None:
        return [5]
    if isinstance(value, int):
        n = value
        if n not in POSE_NO_TO_BIN:
            raise SystemExit("pose must be 1..9, frontal, or all")
        return [n]
    v = str(value).strip().lower()
    if v == "frontal":
        return [5]
    if v == "all":
        return list(range(1, 10))
    try:
        n = int(v)
    except ValueError:
        raise SystemExit("pose must be 1..9, frontal, or all")
    if n not in POSE_NO_TO_BIN:
        raise SystemExit("pose must be 1..9, frontal, or all")
    return [n]


def _shift_frame_yaw(yaw: float, primary_pose_no: int) -> float:
    """Map a template yaw to a concrete primary pose.

    Most scenarios are single-bin and use yaw=0. Multi-bin scenarios keep their
    relative offsets around the primary pose where possible.
    """
    key = int(round(float(yaw)))
    ref_pose = YAW_TO_REFERENCE_POSE.get(key, 5)
    delta = ref_pose - 5
    new_pose = min(9, max(1, int(primary_pose_no) + delta))
    return POSE_NO_TO_YAW[new_pose]


def _apply_pose(frames: list[dict], pose_no: int) -> list[dict]:
    out = []
    for fr in frames:
        nf = dict(fr)
        nf["yaw"] = _shift_frame_yaw(float(fr["yaw"]), pose_no)
        nf["pose_no"] = pose_no
        nf["pose_bin_requested"] = POSE_NO_TO_BIN[pose_no]
        out.append(nf)
    return out


def _f(person, yaw, date, group="auto"):
    return {"person": person, "yaw": yaw, "date": date, "group": group}


def _ser(person, yaw, dates, group="auto"):
    return [_f(person, yaw, d, group) for d in dates]


def _remap_frames(frames: list[dict], mapping: dict) -> list[dict]:
    out = []
    for fr in frames:
        nf = dict(fr)
        nf["person"] = mapping.get(fr["person"], fr["person"])
        out.append(nf)
    return out


def _base_frames() -> dict[str, list[dict]]:
    return {
        "S01_stability_frontal_A": _ser(A, 0, ["2001_03_10", "2001_09_15", "2002_04_20", "2003_02_11", "2004_06_30"]),
        "S02_stability_frontal_A2": _ser(A2, 0, ["2002_01_10", "2002_07_15", "2003_03_20", "2004_01_11", "2005_05_30"]),
        "S03_stability_all_poses_A": [_f(A, y, d) for y, d in [(0, "2002_01_10"), (-20, "2002_02_10"), (20, "2002_03_10"),
                                                                (-45, "2002_04_10"), (45, "2002_05_10"), (-70, "2002_06_10"), (70, "2002_07_10")]],
        "S04_fdr_stress_A": _ser(A, 0, [f"{2001 + i // 12}_{i % 12 + 1:02d}_10" for i in range(14)]),
        "S05_change_AB": _ser(A, 0, ["2001_05_10", "2002_06_12"]) + [_f(B, 0, "2003_07_15")],
        "S06_change_CD": _ser(C, 0, ["2001_05_10", "2002_06_12"]) + [_f(D, 0, "2003_07_15")],
        "S07_series_AAABBB": _ser(A, 0, ["2001_03_10", "2001_09_10", "2002_03_10"]) + _ser(B, 0, ["2003_03_10", "2003_09_10", "2004_03_10"]),
        "S08_change_single_bin": [_f(A, 0, "2001_03_10"), _f(A, 0, "2002_03_10"), _f(B, 0, "2003_03_10"),
                                   _f(A, -20, "2001_04_10"), _f(A, -20, "2002_04_10"), _f(A, -20, "2003_04_10")],
        "S09_return_ABA": [_f(A, 0, "2001_05_10"), _f(A, 0, "2002_05_10"), _f(B, 0, "2003_05_10"),
                           _f(B, 0, "2003_11_10"), _f(A, 0, "2005_01_10")],
        "S10_return_AABBAA": _ser(A, 0, ["2001_03_10", "2001_09_10"]) + _ser(B, 0, ["2002_03_10", "2002_09_10"]) + _ser(A, 0, ["2003_03_10", "2003_09_10"]),
        "S11_no_return_ABC": [_f(A, 0, "2001_03_10"), _f(B, 0, "2003_03_10"), _f(C, 0, "2005_03_10")],
        "S12_rapid_change": [_f(A, 0, "2004_05_01"), _f(B, 0, "2004_05_04")],
        "S13_slow_change": [_f(A, 0, "2001_03_10"), _f(B, 0, "2009_03_10")],
        "S14_rapid_control_same": [_f(A, 0, "2004_05_01"), _f(A, 0, "2004_05_04")],
        "S15_same_day_ok": [_f(A, 0, "2003_06_15"), _f(A, 0, "2003_06_15")],
        "S16_same_day_conflict": [_f(A, 0, "2003_06_15"), _f(B, 0, "2003_06_15")],
        "S17_same_day_mixed": [_f(A, 0, "2003_06_15"), _f(A, 0, "2003_06_15"), _f(B, 0, "2003_06_15")],
        "S18_corroboration_multibin": [_f(A, 0, "2002_12_01", "src_a"), _f(B, 0, "2003_06_10", "src_a"),
                                        _f(A, -20, "2002_12_15", "src_b"), _f(B, -20, "2003_06_20", "src_b"),
                                        _f(A, 20, "2003_01_05", "src_c"), _f(B, 20, "2003_07_01", "src_c")],
        "S19_corroboration_window": [_f(A, 0, "2002_12_01", "src_a"), _f(B, 0, "2003_06_10", "src_a"),
                                      _f(A, -20, "2003_01_05", "src_b"), _f(B, -20, "2003_10_25", "src_b")],
        "S20_minimal_pair": [_f(A, 0, "2001_01_10"), _f(A, 0, "2005_01_10")],
        "S21_long_gaps": _ser(A, 0, ["2001_03_10", "2007_03_10", "2013_03_10"]),
    }


def library(variant: int = 0) -> list[dict]:
    scn: list[dict] = []
    pset = person_set(variant)
    mapping = {
        "A": pset[0],
        "A2": pset[1],
        "B": pset[2],
        "C": pset[3],
        "D": pset[4],
    }
    base = _base_frames()

    def add(sid, block, priority, frames, expect, description, mode="fast"):
        scn.append({
            "id": sid, "block": block, "priority": priority, "mode": mode,
            "description": description,
            "person_set": {"A": mapping["A"], "A2": mapping["A2"], "B": mapping["B"], "C": mapping["C"], "D": mapping["D"]},
            "frames": _remap_frames(frames, mapping),
            "expect": expect,
        })

    expectations = {
        "S01_stability_frontal_A": ([{"type": "no_red_pairs"}], "AAAAA: один человек, фронт, месяцы между кадрами — нет аномалий"),
        "S02_stability_frontal_A2": ([{"type": "no_red_pairs"}], "AAAAA на другом человеке — контроль нормы на второй геометрии"),
        "S03_stability_all_poses_A": ([{"type": "no_red_pairs"}], "Один человек во всех ракурсах — проверка отсутствия утечки позы"),
        "S04_fdr_stress_A": ([{"type": "no_red_pairs"}, {"type": "fdr_significant_fraction_max", "value": 0.10}], "14 кадров одного человека — доля 'значимых' пар после FDR ≤ 10% (тест фикса N1)"),
        "S05_change_AB": ([{"type": "pair_status", "frames": [2, 3], "any_of": CHANGE},
                            {"type": "pair_status_not", "frames": [1, 2], "none_of": RED}], "AAB: смена личности ровно между 2-м и 3-м кадром"),
        "S06_change_CD": ([{"type": "pair_status", "frames": [2, 3], "any_of": CHANGE},
                            {"type": "pair_status_not", "frames": [1, 2], "none_of": RED}], "AAB на другой паре людей — вариант сложности"),
        "S07_series_AAABBB": ([{"type": "pair_status", "frames": [3, 4], "any_of": CHANGE},
                                {"type": "pair_status_not", "frames": [1, 2], "none_of": RED},
                                {"type": "pair_status_not", "frames": [2, 3], "none_of": RED},
                                {"type": "pair_status_not", "frames": [4, 5], "none_of": RED},
                                {"type": "pair_status_not", "frames": [5, 6], "none_of": RED}], "AAABBB: одно событие смены, внутри блоков чисто"),
        "S08_change_single_bin": ([{"type": "status_present", "any_of": CHANGE},
                                    {"type": "corroboration", "frames": [2, 3], "any_of": ["not_corroborated"]}], "Смена только во фронтальном ракурсе — кросс-подтверждения быть не должно"),
        "S09_return_ABA": ([{"type": "status_present", "any_of": CHANGE},
                             {"type": "baseline_return_events", "min": 1}], "AABBA: возврат к исходной геометрии должен быть найден"),
        "S10_return_AABBAA": ([{"type": "baseline_return_events", "min": 1}], "AABBAA: возврат после серии"),
        "S11_no_return_ABC": ([{"type": "baseline_return_events", "max": 0}], "ABC: три разных человека — возврата быть не должно (анти-тест)"),
        "S12_rapid_change": ([{"type": "status_present", "any_of": RAPID + CHANGE}], "A→B за 3 дня — биологически невероятная скорость"),
        "S13_slow_change": ([{"type": "status_absent", "statuses": RAPID},
                              {"type": "status_present", "any_of": CHANGE}], "A→B за 8 лет — смена есть, rapid — НЕТ"),
        "S14_rapid_control_same": ([{"type": "status_absent", "statuses": RAPID}, {"type": "no_red_pairs"}], "Один человек через 3 дня — контроль ложного rapid"),
        "S15_same_day_ok": ([{"type": "status_absent", "statuses": ["same_day_structural_conflict"]}, {"type": "no_red_pairs"}], "Два кадра одного человека в один день — конфликта нет"),
        "S16_same_day_conflict": ([{"type": "status_present", "any_of": ["same_day_structural_conflict"]}], "A и B в один день — структурный конфликт обязан сработать"),
        "S17_same_day_mixed": ([{"type": "status_present", "any_of": ["same_day_structural_conflict"]},
                                 {"type": "pair_status_not", "frames": [1, 2], "none_of": ["same_day_structural_conflict"]}], "A+A+B в один день — конфликт локализован на B"),
        "S18_corroboration_multibin": ([{"type": "status_present", "any_of": CHANGE},
                                         {"type": "corroboration", "frames": [1, 2], "any_of": ["corroborated_multiple_pose_bins", "corroborated_one_pose_bin"]}], "Событие видно в 3 ракурсах из 3 источников — должно быть подтверждено (тест N3)"),
        "S19_corroboration_window": ([{"type": "corroboration", "frames": [1, 2], "any_of": ["not_corroborated"]}], "'Поддержка' за пределами временного окна — НЕ засчитывается (тест N3b)"),
        "S20_minimal_pair": ([{"type": "no_red_pairs"}], "Минимальный набор из 2 фото — пайплайн отрабатывает без падений"),
        "S21_long_gaps": ([{"type": "no_red_pairs"}, {"type": "status_absent", "statuses": RAPID}], "Пропуски по 6 лет — никаких ложных rapid"),
    }
    priorities = {
        "S01_stability_frontal_A": "P1", "S02_stability_frontal_A2": "P2", "S03_stability_all_poses_A": "P1",
        "S04_fdr_stress_A": "P1", "S05_change_AB": "P1", "S06_change_CD": "P2", "S07_series_AAABBB": "P1",
        "S08_change_single_bin": "P2", "S09_return_ABA": "P1", "S10_return_AABBAA": "P2", "S11_no_return_ABC": "P1",
        "S12_rapid_change": "P1", "S13_slow_change": "P1", "S14_rapid_control_same": "P2",
        "S15_same_day_ok": "P1", "S16_same_day_conflict": "P1", "S17_same_day_mixed": "P2",
        "S18_corroboration_multibin": "P1", "S19_corroboration_window": "P1",
        "S20_minimal_pair": "P2", "S21_long_gaps": "P2",
    }
    blocks = {
        "S01_stability_frontal_A": "stability", "S02_stability_frontal_A2": "stability", "S03_stability_all_poses_A": "stability",
        "S04_fdr_stress_A": "stability", "S05_change_AB": "identity_change", "S06_change_CD": "identity_change",
        "S07_series_AAABBB": "identity_change", "S08_change_single_bin": "corroboration", "S09_return_ABA": "return",
        "S10_return_AABBAA": "return", "S11_no_return_ABC": "return", "S12_rapid_change": "rate", "S13_slow_change": "rate",
        "S14_rapid_control_same": "rate", "S15_same_day_ok": "same_day", "S16_same_day_conflict": "same_day",
        "S17_same_day_mixed": "same_day", "S18_corroboration_multibin": "corroboration", "S19_corroboration_window": "corroboration",
        "S20_minimal_pair": "edge", "S21_long_gaps": "edge",
    }
    for sid, frames in base.items():
        expect, desc = expectations[sid]
        add(sid, blocks[sid], priorities[sid], frames, expect, desc)
    return scn


def _scenario_combo_count(base_id: str, default: int, overrides: dict[str, int] | None) -> int:
    if overrides and base_id in overrides:
        return _norm_combo_count(overrides[base_id])
    if base_id in DEFAULT_COMBINATIONS_BY_SCENARIO:
        return _norm_combo_count(DEFAULT_COMBINATIONS_BY_SCENARIO[base_id])
    return _norm_combo_count(default)


def select_base_ids(selector: str | None) -> list[str]:
    base_ids = [s["id"] for s in library(0)]
    if selector is None or str(selector).lower() == "all":
        return base_ids
    raw = str(selector).strip()
    wanted: list[str] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if token.isdigit():
            token = f"S{int(token):02d}"
        matches = [sid for sid in base_ids if sid == token or sid.startswith(token)]
        if not matches:
            raise SystemExit(f"неизвестный scenario: {part}; доступны S01..S21 или all")
        wanted.extend(matches)
    # stable unique
    seen = set()
    return [x for x in wanted if not (x in seen or seen.add(x))]


def parse_combination_overrides(items: list[str] | None) -> dict[str, int]:
    """Parse CLI overrides: S04_fdr_stress_A=15."""
    out: dict[str, int] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"ожидается BASE_ID=N, получено: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"пустой base_id в override: {item}")
        out[key] = _norm_combo_count(value)
    return out


def generate(combinations: int = -1, overrides: dict[str, int] | None = None, *, clean: bool = True,
             scenario: str | None = "all", pose: str | int | None = "frontal") -> int:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    if clean:
        for old in SCENARIOS_DIR.glob("*.json"):
            old.unlink()
    count = 0
    base_ids = select_base_ids(scenario)
    pose_nos = parse_pose(pose)
    unknown = sorted(set(overrides or {}) - set(base_ids))
    if unknown:
        raise SystemExit(f"неизвестные scenario ids в --scenario-combinations: {unknown}")
    for base_id in base_ids:
        n = _scenario_combo_count(base_id, combinations, overrides)
        if n > 7:
            raise SystemExit("combinations must be 1..7 for this curated seven-person dataset")
        for v in range(n):
            lib = {s["id"]: s for s in library(v)}
            s = lib[base_id]
            for pose_no in pose_nos:
                sid = f"{base_id}_p{pose_no:02d}_v{v:02d}"
                obj = dict(s)
                obj["id"] = sid
                obj["variant"] = v
                obj["combo_no"] = v + 1
                obj["base_id"] = base_id
                obj["pose_no"] = pose_no
                obj["pose_bin"] = POSE_NO_TO_BIN[pose_no]
                obj["combination_count_for_base"] = n
                obj["frames"] = _apply_pose(s["frames"], pose_no)
                (SCENARIOS_DIR / f"{sid}.json").write_text(
                    json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
                count += 1
    return count
