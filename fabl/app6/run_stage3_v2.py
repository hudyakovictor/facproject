#!/usr/bin/env python3
"""🚪 ENTRY POINT → Stage 3 v2: аналитический движок поверх Stage 2.

Usage:
  python run_stage3_v2.py --stage2 <path> --output <path>

Пример:
  python run_stage3_v2.py \\
    --stage2 /data/stage2_output \\
    --output /data/stage3_v2_output \\
    --overwrite
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_ROOT = APP_DIR.parent

if str(DEFAULT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_ROOT))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DEEPUTIN app6 stage 3 v2")
    p.add_argument("--project-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--stage2", required=True, type=Path, help="Path to Stage 2 output")
    p.add_argument("--output", required=True, type=Path, help="Output directory")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing output")
    
    # Optional overrides
    p.add_argument("--fast-pass", action="store_true", default=True, help="Enable Fast Pass")
    p.add_argument("--no-fast-pass", action="store_true", help="Disable Fast Pass")
    p.add_argument("--workers", type=int, default=8, help="Number of parallel workers")
    p.add_argument("--bootstrap-iter", type=int, default=1000, help="Bootstrap iterations")
    
    return p


def main():
    args = build_parser().parse_args()
    root = args.project_root.resolve()
    
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    
    import os
    os.chdir(root)
    
    from app6.stage3_v2 import Stage3V2Config, Stage3V2Engine
    
    # Build config
    config = Stage3V2Config(
        stage2_root=args.stage2.resolve(),
        output_dir=args.output.resolve(),
        overwrite=args.overwrite,
        fast_pass_enabled=not args.no_fast_pass,
        max_workers=args.workers,
        bootstrap_iterations=args.bootstrap_iter,
    )
    
    # Run engine
    engine = Stage3V2Engine(config)
    report = engine.run()
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total pairs:     {report.total_pairs}")
    print(f"Analyzed:        {report.pairs_analyzed}")
    print(f"With changes:    {report.pairs_with_changes}")
    print(f"Processing time: {report.processing_time_seconds:.1f}s")
    print(f"\n📰 {report.narrative.headline_ru}")
    print("\n🔑 Key findings:")
    for finding in report.narrative.key_findings:
        print(f"  • {finding}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
