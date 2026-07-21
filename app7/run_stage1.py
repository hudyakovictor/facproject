#!/usr/bin/env python3
"""DEEPUTIN app7 — Stage 1: deterministic extraction.

Usage:
    python app7/run_stage1.py --input /path/to/photos --output /path/to/results
    python app7/run_stage1.py --input /path/to/photos --output /path/to/results --limit 5
    python app7/run_stage1.py --input /path/to/photos --output /path/to/results --preview-level full

Photo naming: YYYY_MM_DD[_suffix].ext  (date is required in filename)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = APP_DIR.parent
if str(APP_DIR.parent) not in sys.path:
    sys.path.insert(0, str(APP_DIR.parent))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="DEEPUTIN app7 — Stage 1: extract 3D geometry + skin evidence from photos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Process all photos:
    python app7/run_stage1.py --input ./photos --output ./results

  Process only 5 photos (for testing):
    python app7/run_stage1.py --input ./photos --output ./results --limit 5

  Skip preview generation (faster):
    python app7/run_stage1.py --input ./photos --output ./results --preview-level none
        """,
    )
    p.add_argument("--project-root", type=Path, default=DEFAULT_ROOT,
                   help="Root directory containing 3ddfa_v3/, assets/, etc.")
    p.add_argument("--input", type=Path, required=True,
                   help="Directory of YYYY_MM_DD[_N].ext photos")
    p.add_argument("--output", type=Path, required=True,
                   help="Output directory for extracted data")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                   help="Compute device (default: auto)")
    p.add_argument("--detector", default="retinaface",
                   help="Face detector (default: retinaface)")
    p.add_argument("--backbone", default="resnet50", choices=["resnet50", "mbnetv3"],
                   help="3DDFA backbone (default: resnet50)")
    p.add_argument("--uv-size", type=int, default=1000,
                   help="UV texture size (default: 1000)")
    p.add_argument("--limit", type=int, default=0,
                   help="Process only N photos (0 = all)")
    p.add_argument("--overwrite", action="store_true",
                   help="Overwrite existing photo directories")
    p.add_argument("--fail-fast", action="store_true",
                   help="Stop on first error instead of continuing")
    p.add_argument("--preview-level", default="minimal",
                   choices=["none", "minimal", "full"],
                   help="Preview verbosity: none=0, minimal=2, full=7 files per photo (default: minimal)")
    return p


def main() -> int:
    a = build_parser().parse_args()
    root = a.project_root.resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from app7.stage1.config import Stage1Config
    from app7.stage1.engine import Stage1Engine

    cfg = Stage1Config(
        project_root=root,
        input_dir=a.input.resolve(),
        output_dir=a.output.resolve(),
        device=a.device,
        detector=a.detector,
        backbone=a.backbone,
        uv_size=a.uv_size,
        limit=a.limit,
        overwrite=a.overwrite,
        continue_on_error=not a.fail_fast,
        preview_level=a.preview_level,
    )
    Stage1Engine(cfg).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
