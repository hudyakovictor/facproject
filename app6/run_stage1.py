#!/usr/bin/env python3
"""
🚪 ENTRY POINT → Stage 1: Извлечение данных из фото (3DDFA inference + skin analysis)

🎯 CRITICAL — Это САМЫЙ ВАЖНЫЙ этап. Все последующие анализы зависят от качества
данных, извлечённых здесь. Если Stage 1 работает некорректно — ВСЕ результаты
Stage 2 и Stage 3 будут недостоверны.

🔗 DEPENDS ON:
  - app6/stage1/engine.py → Stage1Engine (оркестрация)
  - app6/stage1/reconstruction.py → ReconstructionEngine (3DDFA inference)
  - app6/stage1/skin/pipeline.py → build_skin_package (skin feature extraction)

⚠️ IN PROGRESS:
  - Canonical alignment корректирует только YAW (pitch/roll игнорируются)
  - Нет валидации качества 3DDFA реконструкции (reprojection error)
  - Нет фильтрации фото с сильной мимикой (открытый рот, улыбка)

💡 NOTE:
  - Один запуск ≈ 5 часов для 1700 фото
  - Результаты сохраняются в output_dir/photo_id/
  - Для перезапуска используйте --overwrite или удалите папки в output_dir
  - Калибровочные фото обрабатываются ТЕМ ЖЕ скриптом (просто положите в другую папку)

🚨 WARNING:
  - НЕ запускайте параллельные копии на одних и тех же данных!
  - При device='cuda' может закончиться VRAM — используйте --limit для тестов
  - При ошибке проверьте output_dir/_failures/ для диагностики

ПАЙПЛАЙН ПОЛНОГО АНАЛИЗА:
  1. python run_stage1.py --input /path/to/photos --output /path/to/stage1_output
  2. python run_stage2.py --stage1 /path/to/stage1_output --calibration /path/to/calibration --output /path/to/stage2_output
  3. python run_stage3.py --analysis /path/to/stage2_output --output /path/to/report

См. app6/CONVENTIONS.py для полной системы символов и правил комментирования.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = APP_DIR.parent
if str(APP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(APP_DIR.parent))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DEEPUTIN app6 — deterministic 3DDFA_V3 stage-1 extraction")
    p.add_argument("--project-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--input", type=Path, required=True, help="Directory of YYYY_MM_DD[_N].ext photos")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--detector", default="retinaface")
    p.add_argument("--backbone", default="resnet50", choices=["resnet50", "mbnetv3"])
    p.add_argument("--uv-size", type=int, default=1000, choices=range(64, 1001), metavar="64..1000")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--fail-fast", action="store_true")
    p.add_argument("--no-original-copy", action="store_true")
    p.add_argument("--no-mesh", action="store_true", help="Skip mesh.obj/mesh.mtl output (keeps uv_texture.png)")
    return p


def main() -> int:
    a = build_parser().parse_args()
    root = a.project_root.resolve()
    if str(root) not in sys.path: sys.path.insert(0, str(root))
    os.chdir(root)
    from app6.stage1.config import Stage1Config
    from app6.stage1.engine import Stage1Engine
    cfg = Stage1Config(
        project_root=root, input_dir=a.input.resolve(), output_dir=a.output.resolve(),
        device=a.device, detector=a.detector, backbone=a.backbone, uv_size=a.uv_size,
        limit=a.limit, overwrite=a.overwrite, continue_on_error=not a.fail_fast,
        save_original=not a.no_original_copy, save_mesh=not a.no_mesh,
    )
    Stage1Engine(cfg).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
