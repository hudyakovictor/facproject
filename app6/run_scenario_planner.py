#!/usr/bin/env python3
"""🚪 ENTRY POINT → Планировщик минимальных сценарных цепочек (ТЗ п.16).

`AGENTS.md` требует лестницу минимальных прогонов: один кадр → 10 → 100 → полный
набор, и запрещает запускать всё сразу. Планировщик подбирает наименьший набор
кадров, отвечающий на конкретный вопрос, и печатает готовый план без запуска
тяжёлых стадий.

Сценарии соответствуют `docs/future_testing_module.txt`: каждый проверяет одну
гипотезу о поведении системы, а не отдельную функцию.

Пример:
    python app6/run_scenario_planner.py --scenario S03 --pose frontal --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCENARIOS: dict[str, dict[str, Any]] = {
    "S01": {"question": "Отличает ли система шум от реального изменения?",
            "pattern": ["A", "A", "A"], "expect": "без аномалий: стабильная серия"},
    "S02": {"question": "Замечает ли система смену личности?",
            "pattern": ["A", "A", "B"], "expect": "расхождение на переходе A→B"},
    "S03": {"question": "Детектируется ли возврат A→B→A?",
            "pattern": ["A", "B", "A"], "expect": "irreversible_return_anomaly"},
    "S04": {"question": "Не путает ли система смену ракурса со сменой лица?",
            "pattern": ["A", "A"], "cross_pose": True, "expect": "pose_mismatch, а не аномалия"},
    "S05": {"question": "Устойчив ли вывод при чередовании носителей?",
            "pattern": ["A", "B", "A", "B"], "expect": "повторяющиеся переходы"},
    "S06": {"question": "Копится ли постепенный дрейф?",
            "pattern": ["A", "A", "A", "A", "A"], "expect": "cumulative_drift при накоплении"},
}


def build_plan(scenario: str, pose: str, archive_root: Path | None = None) -> dict[str, Any]:
    """🏭 FACTORY → Построить план сценария из доступных данных архива."""
    from app6.test_module.archive_adapter import (
        POSE_BINS, group_by_person_pose, load_archive_records, with_synthetic_dates,
    )

    if scenario not in SCENARIOS:
        raise ValueError(f"неизвестный сценарий {scenario}; доступны {sorted(SCENARIOS)}")
    if pose != "all" and pose not in POSE_BINS:
        raise ValueError(f"неизвестный ракурс {pose}; доступны {list(POSE_BINS)}")

    spec = SCENARIOS[scenario]
    records = load_archive_records(archive_root) if archive_root else []
    grouped = group_by_person_pose(records) if records else {}
    people = sorted({p for p, _ in grouped}) if grouped else []

    poses = list(POSE_BINS) if pose == "all" else [pose]
    frames: list[dict[str, Any]] = []
    for target_pose in poses:
        role_to_person = {}
        available = [p for p in people if grouped.get((p, target_pose))]
        for index, role in enumerate(sorted(set(spec["pattern"]))):
            if index < len(available):
                role_to_person[role] = available[index]
        selected = []
        for step, role in enumerate(spec["pattern"]):
            person = role_to_person.get(role)
            if person is None:
                continue
            pool = grouped[(person, target_pose)]
            selected.append(pool[step % len(pool)])
        for record in with_synthetic_dates(selected):
            frames.append({"pose_bin": target_pose, "role_sequence": spec["pattern"],
                           "person": record.dataset_id, "record_id": record.record_id,
                           "date": record.date})

    return {"scenario": scenario, "question": spec["question"],
            "expectation": spec["expect"], "pose": pose,
            "frame_count": len(frames), "frames": frames,
            "data_available": bool(records),
            "note": "даты синтетические: задают порядок хронологии, не датировку съёмки"}


def main() -> int:
    parser = argparse.ArgumentParser(description="DEEPUTIN scenario planner (ТЗ п.16)")
    parser.add_argument("--scenario", default="S01", choices=sorted(SCENARIOS))
    parser.add_argument("--pose", default="frontal", help="имя ракурса или 'all'")
    parser.add_argument("--archive", type=Path,
                        default=ROOT / "selected_photos_7x9x3_data.tar.gz")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="только план, без запуска стадий")
    parser.add_argument("--list", action="store_true", help="показать сценарии и выйти")
    args = parser.parse_args()

    if args.list:
        for key, spec in SCENARIOS.items():
            print(f"{key}: {spec['question']}\n     цепочка={spec['pattern']} ожидание={spec['expect']}")
        return 0

    extracted: Path | None = None
    if args.archive and args.archive.is_file():
        extracted = Path(tempfile.mkdtemp(prefix="scenario_"))
        with tarfile.open(args.archive) as tar:
            tar.extractall(extracted)

    plan = build_plan(args.scenario, args.pose, extracted)
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    if not args.dry_run:
        print("\nПлан построен. Запуск стадий выполняется отдельно "
              "по лестнице AGENTS.md: 1 кадр → 10 → 100 → полный набор.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
