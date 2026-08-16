#!/usr/bin/env python3
"""Канонический запуск Stage 1 для калибровочного набора.

Пишет тот же полный контракт, что и ``run_stage1.py``: manifest, timeline,
provenance и артефакты по каждому кадру.  Ручной вызов ``_one`` здесь
запрещён: он оставляет каталог без индекса и не годится для Stage 2.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

DEFAULT_INPUT = ROOT / "calibration_dataset" / "photos"
DEFAULT_OUTPUT = Path("/Volumes/SDCARD/storage/calibration_stage1")

def main() -> int:
    from app6.stage1.config import Stage1Config
    from app6.stage1.engine import Stage1Engine

    parser = argparse.ArgumentParser(description="DEEPUTIN calibration Stage 1")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="каталог исходных калибровочных фото")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="каталог результата на съёмном диске")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--limit", type=int, default=0, help="обработать только первые N кадров (тестовый запуск)")
    parser.add_argument("--fail-fast", action="store_true", help="остановиться при первой ошибке кадра")
    args = parser.parse_args()

    cfg = Stage1Config(
        project_root=ROOT,
        input_dir=args.input.resolve(),
        output_dir=args.output.resolve(),
        device=args.device,
        limit=args.limit,
        overwrite=True,
        continue_on_error=not args.fail_fast,
        require_filename_date=False,
    )
    manifest = Stage1Engine(cfg).run()
    return 0 if manifest["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
