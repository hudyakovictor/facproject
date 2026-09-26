"""CLI Утилита для просмотра хронологии по группам ракурсов (app8).

Пример использования:
python3 -m app8.chronology --dir results/app8_stage1
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from .chronology import load_chronology_dataset, print_chronology_summary


def main() -> int:
    p = argparse.ArgumentParser(description="app8 Chronology Viewer: группировка фото по ракурсам во времени")
    p.add_argument("--dir", type=Path, required=True, help="Путь к результатам Stage 1 (где лежат папки с npz)")
    args = p.parse_args()
    
    if not args.dir.is_dir():
        print(f"Error: directory {args.dir} does not exist", file=sys.stderr)
        return 1
        
    records_by_bin = load_chronology_dataset(args.dir)
    print_chronology_summary(records_by_bin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
