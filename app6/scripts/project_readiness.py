#!/usr/bin/env python3
"""Детерминированный отчёт готовности: код/UI против внешних входов исследования.

DEV_FIX_TZ B2 / P1.12 / P2 (13.5): раньше отчёт печатал `research_run_ready:
false` и голый список отсутствующих путей, не объясняя, что это ОЖИДАЕМОЕ
состояние свежего клона, а не поломка. `dataset/main/` и веса моделей —
внешние входы исследования: они намеренно не хранятся в git (`.gitignore`),
потому что это большие бинарные данные и исходные фотографии, неизменяемость
которых требует `app6/AGENTS.md`.

Поэтому отчёт теперь различает три вещи:
  * `code_ready`   — цел ли исполняемый код (нарушение = настоящий дефект);
  * `ui_ready`     — собран ли интерфейс (лечится `npm ci && npm run build`);
  * `research_run_ready` — подложены ли внешние данные и веса.

Пустая директория-заглушка НЕ создаётся: она сделала бы отчёт зелёным, не дав
ни одного кадра для анализа, что прямо противоречит запрету AGENTS.md на
имитацию наличия данных.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

#: Исполняемые точки входа пайплайна — обязаны присутствовать всегда.
CODE_ENTRY_POINTS = [
    "app6/run_stage1.py",
    "app6/run_stage2.py",
    "app6/run_stage2b.py",
    "app6/run_stage3.py",
    "app6/run_preflight.py",
]

#: Артефакты собранного интерфейса.
UI_ARTIFACTS = [
    "ui/dist/index.html",
    "ui/START_UI.sh",
    "ui/scripts/smoke_ui.py",
]

#: Веса моделей: внешние бинарные входы, вне git.
MODEL_WEIGHTS = [
    "assets/face_model.npy",
    "assets/net_recon.pth",
    "assets/large_base_net.pth",
    "assets/retinaface_resnet50_2020-07-20_old_torch.pth",
    "assets/similarity_Lm3D_all.mat",
]

#: Датасеты: исходные фотографии, вне git и неизменяемы.
DATASET_PATHS = [
    "dataset/main",
    "calibration_dataset/photos",
]

#: Как получить каждый отсутствующий внешний вход — вместо голого «missing».
REMEDIATION = {
    "dataset/main": (
        "основной исследовательский фотонабор (YYYY_MM_DD[_N].jpg). Не хранится в git "
        "и не создаётся автоматически: пустая директория дала бы зелёный отчёт без "
        "единого кадра. Смонтируйте/скопируйте набор в dataset/main или укажите путь "
        "явно через --input у app6/run_stage1.py."
    ),
    "calibration_dataset/photos": (
        "сырые калибровочные фото. AGENTS.md: единственный допустимый вход калибровки — "
        "calibration_dataset/photos/ (Stage 1 запускается заново) либо готовый "
        "calibration_dataset/main_timeline.csv от run_calibration.py. Набор "
        "calibration_dataset/person_*/frame_*/ устарел и не подходит."
    ),
    "assets/face_model.npy": "веса/геометрия 3DDFA_V3 — см. app6/scripts/fetch_external_assets.py",
    "assets/net_recon.pth": "веса 3DDFA_V3 — см. app6/scripts/fetch_external_assets.py",
    "assets/large_base_net.pth": "веса детектора landmarks — см. app6/scripts/fetch_external_assets.py",
    "assets/retinaface_resnet50_2020-07-20_old_torch.pth": "веса RetinaFace — см. app6/scripts/fetch_external_assets.py",
    "assets/similarity_Lm3D_all.mat": "матрица подобия 3DMM — см. app6/scripts/fetch_external_assets.py",
    "ui/dist/index.html": "сборка UI отсутствует: cd ui && npm ci && npm run build",
    "ui/START_UI.sh": "скрипт запуска UI отсутствует в дереве репозитория",
    "ui/scripts/smoke_ui.py": "smoke-проверка UI отсутствует в дереве репозитория",
}


def _missing(root: Path, entries: list[str], *, must_be_file: bool = True) -> list[str]:
    """🔍 QUERY → Список отсутствующих путей из набора."""
    result = []
    for entry in entries:
        target = root / entry
        present = target.is_file() if must_be_file else target.exists()
        if not present:
            result.append(entry)
    return result


def build_report(root: Path) -> dict:
    """🏭 FACTORY → Отчёт готовности с объяснением каждого пробела."""
    missing_code = _missing(root, CODE_ENTRY_POINTS)
    missing_ui = _missing(root, UI_ARTIFACTS)
    missing_weights = _missing(root, MODEL_WEIGHTS)
    missing_data = _missing(root, DATASET_PATHS, must_be_file=False)

    blockers = missing_weights + missing_data
    return {
        "schema": "deeputin-project-readiness-v2",
        "code_ready": not missing_code,
        "ui_ready": not missing_ui,
        "research_run_ready": not (missing_code or blockers),
        "missing_code": missing_code,
        "missing_ui": missing_ui,
        "external_inputs": {
            "missing_model_assets": missing_weights,
            "missing_dataset_paths": missing_data,
            # Ключевое отличие от v1: внешние входы вне git — это ожидаемое
            # состояние свежего клона, а не дефект кода.
            "expected_absent_in_fresh_clone": True,
            "note": (
                "Веса и датасеты намеренно не версионируются (.gitignore): это большие "
                "бинарные данные и неизменяемые исходные фотографии (app6/AGENTS.md). "
                "research_run_ready=false в чистом клоне — норма, а не поломка."
            ),
        },
        "remediation": {
            path: REMEDIATION.get(path, "нет инструкции — уточните у владельца данных")
            for path in missing_code + missing_ui + blockers
        },
        "launch": {
            "ui": "./RUN_PROJECT.sh ui",
            "check": "./RUN_PROJECT.sh check",
            "research": "./RUN_PROJECT.sh preflight --calibration-root calibration_dataset",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--strict-research", action="store_true",
                        help="ненулевой код возврата, если внешние входы исследования отсутствуют")
    args = parser.parse_args()

    report = build_report(args.project_root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Отсутствие внешних данных само по себе НЕ ошибка: она объявляется только
    # при явном --strict-research (например, перед исследовательским прогоном).
    if report["missing_code"] or report["missing_ui"]:
        return 1
    if args.strict_research and not report["research_run_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
