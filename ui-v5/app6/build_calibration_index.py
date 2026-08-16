#!/usr/bin/env python3
"""CLI: собрать индекс только из полного результата калибровочного Stage 1."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app6.calibration_index import build_calibration_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build verified calibration index from completed Stage 1")
    parser.add_argument("--stage1-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(build_calibration_index(args.stage1_root, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
