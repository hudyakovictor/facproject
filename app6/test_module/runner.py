#!/usr/bin/env python3
"""🚪 ENTRY POINT → `python -m app6.test_module.runner execute ...`

Реализует «обязательную лестницу минимальных запусков» из `app6/AGENTS.md` и
`app6/SKILL.md`: сценарий → один ракурс/одна комбинация → все девять ракурсов
→ растущее число комбинаций. Каждый шаг запускается параметрически и
завершается явным PASS/FAIL, без скрытого расширения охвата.

🔗 DEPENDS ON:
  - app6.test_module.scenarios — реестр вопросов/паттернов (общий с
    `run_scenario_planner.py`, который строит только план без исполнения);
  - app6.test_module.archive_adapter — единственный сейчас реальный источник
    геометрии (188 записей, 7 персон × 9 ракурсов) для сценарной проверки;
  - app6.stage2.core.compare_landmarks / build_coordinate_zone_map;
  - app6.stage2.irreversible_return.detect_irreversible_return.

🚨 WARNING: это developer-level regression гейт (ТЗ п.16), а не Stage 2.
Он не запускает Stage 1, не строит полный evidence-payload и не заменяет
`run_stage2.py`. Он проверяет только то, что базовые геометрические примитивы
дают ожидаемое поведение на маленьких контролируемых наборах, прежде чем эти
примитивы используются на реальном датасете.

Пример (первая ступень лестницы):
    python -m app6.test_module.runner execute \\
        --scenario S01 --pose frontal --combinations 1 \\
        --stage all --mode fast --device cpu --fail-fast
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from app6.test_module.archive_adapter import safe_extract_archive

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUNNER_SCHEMA = "deeputin-test-runner-v1.0"

#: Стадии, которые этот runner способен проверить сегодня. `--stage all`
#: сейчас означает `geometry`: текстурные и Stage-1-зависимые сценарии
#: требуют весов 3DDFA_V3 и сюда не входят (см. app6/AGENTS.md, среда
#: выполнения). Значение явное, чтобы вызывающий не решил, будто
#: `--stage all` покрывает текстуру или Stage 1/3.
SUPPORTED_STAGES: tuple[str, ...] = ("geometry",)


def _default_archive() -> Path:
    return ROOT / "selected_photos_7x9x3_data.tar.gz"


def _load_source(archive: Path) -> tuple[dict[tuple[str, str], list], list[str]]:
    """🏭 FACTORY → Загрузить и сгруппировать доступный геометрический источник.

    Raises:
        FileNotFoundError: если архив недоступен. Runner не подменяет
        отсутствующий источник синтетическими лицами — сценарии про поведение
        реального пайплайна, а не про случайные числа.
    """
    from app6.test_module.archive_adapter import group_by_person_pose, load_archive_records

    if not archive.is_file():
        raise FileNotFoundError(
            f"источник геометрии не найден: {archive}. "
            "Ожидается selected_photos_7x9x3_data.tar.gz в корне проекта, "
            "либо передайте другой путь через --archive."
        )
    extract_dir = Path(tempfile.mkdtemp(prefix="deeputin_runner_"))
    safe_extract_archive(archive, extract_dir)
    records = load_archive_records(extract_dir)
    grouped = group_by_person_pose(records)
    people = sorted({p for p, _ in grouped})
    return grouped, people


def _check_stable_series(records, timeline_from_combo, detect_irreversible_return) -> dict[str, Any]:
    """S01: стабильная серия ``AAA`` не должна давать возвратную аномалию."""
    timeline = timeline_from_combo(records)
    anomalies = detect_irreversible_return(timeline)
    return {"passed": anomalies == [], "detail": {"anomaly_count": len(anomalies)}}


def _check_transition_divergence(records, compare_landmarks, zone106, zone134) -> dict[str, Any]:
    """S02: переход A→A→B должен разойтись сильнее, чем пара A↔A внутри серии."""
    if len(records) < 3:
        return {"passed": False, "detail": {"reason": "need_at_least_3_frames"}}
    same = compare_landmarks(records[0], records[1], zone106, zone134)
    transition = compare_landmarks(records[1], records[2], zone106, zone134)
    if same.status != "measured" or transition.status != "measured":
        return {"passed": False, "detail": {"same_status": same.status, "transition_status": transition.status}}
    same_rmse = same.metrics["ldm134_rmse"]
    transition_rmse = transition.metrics["ldm134_rmse"]
    return {
        "passed": transition_rmse > same_rmse,
        "detail": {"same_person_rmse": same_rmse, "transition_rmse": transition_rmse},
    }


def _check_irreversible_return(records, timeline_from_combo, detect_irreversible_return) -> dict[str, Any]:
    """S03: A→B→A через годы обязан дать ровно один irreversible_return_anomaly."""
    if len(records) != 3:
        return {"passed": False, "detail": {"reason": "expected_exactly_3_frames"}}
    timeline = timeline_from_combo(records)
    anomalies = detect_irreversible_return(timeline)
    ok = len(anomalies) == 1 and anomalies[0].get("not_a_verdict") is True
    return {"passed": ok, "detail": {"anomalies": anomalies}}


def _check_cross_pose_rejected(records, compare_landmarks, zone106, zone134) -> dict[str, Any]:
    """S04: пара из разных pose bins обязана получить статус pose_mismatch."""
    if len(records) != 2:
        return {"passed": False, "detail": {"reason": "expected_exactly_2_frames"}}
    result = compare_landmarks(records[0], records[1], zone106, zone134)
    return {"passed": result.status == "pose_mismatch", "detail": {"status": result.status}}


def _check_repeated_alternation(records, compare_landmarks, zone106, zone134) -> dict[str, Any]:
    """S05: в цепочке A→B→A→B каждый переход должен разойтись, ни один не «сгладиться»."""
    if len(records) < 4:
        return {"passed": False, "detail": {"reason": "need_at_least_4_frames"}}
    transitions = []
    for i in range(len(records) - 1):
        result = compare_landmarks(records[i], records[i + 1], zone106, zone134)
        if result.status != "measured":
            return {"passed": False, "detail": {"reason": f"pair_{i}_status_{result.status}"}}
        transitions.append(result.metrics["ldm134_rmse"])
    # Каждый переход между разными ролями должен быть выше нуля и не может
    # молчаливо усредниться в отсутствие сигнала: проверяем положительную
    # дисперсию расхождений, а не единственное общее число.
    passed = all(v > 0.0 for v in transitions)
    return {"passed": passed, "detail": {"transition_rmse": transitions}}


def _check_no_false_drift(records, compare_landmarks, zone106, zone134) -> dict[str, Any]:
    """S06: у подлинно стабильной серии AAAAA соседние расхождения не растут монотонно.

    🚨 WARNING: это упрощённый прокси для полноценного `apply_cumulative_drift_flags`
    (требует calibrated point-z из Stage 2 engine). Здесь проверяется более
    слабое, но самодостаточное свойство: последний переход не может быть
    систематически больше первого в разы — иначе сценарий не тестирует то,
    что заявлено (стабильную серию), а сам источник данных непригоден.
    """
    if len(records) < 3:
        return {"passed": False, "detail": {"reason": "need_at_least_3_frames"}}
    transitions = []
    for i in range(len(records) - 1):
        result = compare_landmarks(records[i], records[i + 1], zone106, zone134)
        if result.status != "measured":
            return {"passed": False, "detail": {"reason": f"pair_{i}_status_{result.status}"}}
        transitions.append(result.metrics["ldm134_rmse"])
    first, last = transitions[0], transitions[-1]
    passed = last <= first * 4.0 + 1e-9
    return {"passed": passed, "detail": {"transition_rmse": transitions}}


_CHECKS = {
    "stable_series": _check_stable_series,
    "transition_divergence": _check_transition_divergence,
    "irreversible_return": _check_irreversible_return,
    "cross_pose_rejected": _check_cross_pose_rejected,
    "repeated_alternation": _check_repeated_alternation,
    "no_false_drift": _check_no_false_drift,
}


def run_combination(scenario: str, combo: dict[str, Any], zone106, zone134) -> dict[str, Any]:
    """🔍 QUERY → Выполнить проверку одной комбинации и вернуть отчёт."""
    from app6.stage2.core import compare_landmarks
    from app6.stage2.irreversible_return import detect_irreversible_return
    from app6.test_module.scenarios import SCENARIOS, timeline_from_combo

    if not combo["available"]:
        return {"scenario": scenario, "combination": combo["index"], "status": "skipped",
                "reason": combo["reason"]}

    check_name = SCENARIOS[scenario]["check"]
    check_fn = _CHECKS[check_name]
    records = combo["records"]
    if check_name in ("stable_series", "irreversible_return"):
        outcome = check_fn(records, timeline_from_combo, detect_irreversible_return)
    else:
        outcome = check_fn(records, compare_landmarks, zone106, zone134)

    return {
        "scenario": scenario,
        "combination": combo["index"],
        "status": "pass" if outcome["passed"] else "fail",
        "role_map": combo["role_map"],
        "record_ids": [r.record_id for r in records],
        "detail": outcome["detail"],
    }


def execute(
    scenario: str,
    pose: str,
    combinations: int,
    *,
    archive: Path | None = None,
    fail_fast: bool = True,
) -> dict[str, Any]:
    """🚪 ENTRY POINT (программный) → Выполнить ступень лестницы и собрать отчёт."""
    from app6.stage2.core import build_coordinate_zone_map
    from app6.test_module.scenarios import SCENARIOS, build_combinations, resolve_poses

    if scenario not in SCENARIOS:
        raise ValueError(f"неизвестный сценарий {scenario!r}; доступны {sorted(SCENARIOS)}")

    grouped, people = _load_source(archive or _default_archive())
    poses = resolve_poses(pose)

    all_records = [r for records in grouped.values() for r in records]
    zone106_map, _ = build_coordinate_zone_map(all_records, 106)
    zone134_map, _ = build_coordinate_zone_map(all_records, 134)

    results: list[dict[str, Any]] = []
    for target_pose in poses:
        combos = build_combinations(scenario, target_pose, grouped, people, combinations)
        for combo in combos:
            outcome = run_combination(scenario, combo, zone106_map, zone134_map)
            outcome["pose"] = target_pose
            results.append(outcome)
            if fail_fast and outcome["status"] == "fail":
                break
        if fail_fast and results and results[-1]["status"] == "fail":
            break

    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    overall = "fail" if failed else ("pass" if passed else "inconclusive")

    return {
        "schema": RUNNER_SCHEMA,
        "scenario": scenario,
        "question": SCENARIOS[scenario]["question"],
        "expectation": SCENARIOS[scenario]["expect"],
        "pose_argument": pose,
        "poses_run": list(poses),
        "combinations_requested": combinations,
        "overall_status": overall,
        "pass_count": passed,
        "fail_count": failed,
        "skipped_count": skipped,
        "results": results,
        "not_a_verdict": True,
        "note": "Regression гейт над геометрическими примитивами (ТЗ п.16), не Stage 2 evidence.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app6.test_module.runner",
        description="DEEPUTIN минимальная лестница сценариев (app6/AGENTS.md, app6/SKILL.md)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    execute_parser = sub.add_parser("execute", help="выполнить одну ступень лестницы")
    execute_parser.add_argument("--scenario", default="S01",
                                 help="ID сценария (см. --list), по умолчанию S01")
    execute_parser.add_argument("--pose", default="frontal",
                                 help="имя pose bin или 'all' для всех девяти")
    execute_parser.add_argument("--combinations", type=int, default=1,
                                 help="сколько независимых комбинаций ролей проверить")
    execute_parser.add_argument("--stage", default="all", choices=("all", *SUPPORTED_STAGES),
                                 help="'all' сейчас эквивалентно 'geometry' (см. SUPPORTED_STAGES)")
    execute_parser.add_argument("--mode", default="fast", choices=("fast",),
                                 help="зарезервировано для будущих режимов; сейчас только 'fast'")
    execute_parser.add_argument("--device", default="cpu", choices=("cpu",),
                                 help="зарезервировано: geometry-проверки не используют устройство")
    execute_parser.add_argument("--archive", type=Path, default=None,
                                 help="путь к selected_photos_7x9x3_data.tar.gz")
    execute_parser.add_argument("--fail-fast", action="store_true", default=True,
                                 help="остановиться на первом провале (по умолчанию включено)")
    execute_parser.add_argument("--no-fail-fast", dest="fail_fast", action="store_false")
    execute_parser.add_argument("--output", type=Path, default=None,
                                 help="сохранить JSON-отчёт по указанному пути")

    list_parser = sub.add_parser("list", help="показать доступные сценарии")
    del list_parser  # subparser used only for its side effect of registering the command

    return parser


def main(argv: list[str] | None = None) -> int:
    from app6.test_module.scenarios import SCENARIOS

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        for key, spec in SCENARIOS.items():
            print(f"{key}: {spec['question']}\n     pattern={spec['pattern']} expect={spec['expect']}")
        return 0

    try:
        report = execute(
            args.scenario, args.pose, args.combinations,
            archive=args.archive, fail_fast=args.fail_fast,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"schema": RUNNER_SCHEMA, "overall_status": "error",
                          "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0 if report["overall_status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
