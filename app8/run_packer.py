"""CLI Утилита для упаковки результатов Stage 1 в 9 унифицированных NPZ-пакетов по ракурсам.

Пример использования:
python3 -m app8.run_packer --input results/stage1 --output results/packed_9bins
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
if __name__ == "__main__" and __package__ is None:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app8.packer import pack_pose_bins
else:
    from .packer import pack_pose_bins


def main() -> int:
    p = argparse.ArgumentParser(description="app8 Packer: объединение Stage 1 в 9 NPZ-пакетов по ракурсам")
    p.add_argument("--input", "--stage1-dir", dest="input", type=Path, required=True, help="Путь к результатам Stage 1")
    p.add_argument("--output", "--output-dir", dest="output", type=Path, required=True, help="Целевая папка для 9 упакованных ракурсов")
    args = p.parse_args()
    
    if not args.input.is_dir():
        print(f"Error: input directory {args.input} does not exist", file=sys.stderr)
        return 1
        
    try:
        report = pack_pose_bins(args.input, args.output)
        print(f"Active pose bins packaged: {report['active_bins_count']}/9")
        return 0
    except Exception as exc:
        print(f"Packer Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
