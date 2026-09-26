"""CLI Точка входа для запуска Stage 1 (app8):

Пример использования:
python3 -m app8.run_stage1 --input dataset_realtest --output results/app8_stage1 --device cpu
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

from .config import Stage1Config
from .engine import run_stage1


def main() -> int:
    p = argparse.ArgumentParser(description="app8 Stage 1: 3D-реконструкция и хронологическое выравнивание")
    p.add_argument("--input", type=Path, required=True, help="Путь к папке с исходными фотографиями")
    p.add_argument("--output", type=Path, required=True, help="Путь к целевой папке вывода")
    p.add_argument("--project-root", type=Path, default=Path("."), help="Корень проекта")
    p.add_argument("--device", choices=["cpu", "cuda", "auto"], default="cpu", help="Устройство для инференса")
    p.add_argument("--limit", type=int, default=0, help="Ограничение количества фото (0 = все)")
    p.add_argument("--group-by-pose", action="store_true", help="Раскладывать результаты по подпапкам ракурсов (frontal, left_mid, ...)")
    p.add_argument("--overwrite", action="store_true", help="Перезаписывать существующие записи")
    p.add_argument("--fail-fast", action="store_true", help="Останавливать при первой ошибке")
    
    args = p.parse_args()
    
    cfg = Stage1Config(
        project_root=args.project_root.resolve(),
        input_dir=args.input.resolve(),
        output_dir=args.output.resolve(),
        device=args.device,
        limit=args.limit,
        group_by_pose=args.group_by_pose,
        overwrite=args.overwrite,
        continue_on_error=not args.fail_fast,
    )
    
    try:
        manifest = run_stage1(cfg)
        return 0 if manifest["processed_success"] > 0 else 1
    except Exception as exc:
        print(f"[app8 Stage 1 Fatal Error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
