#!/usr/bin/env python3
"""Main analysis pipeline for the Putin face dataset (1999-2026).

Usage on MacBook M1:
    python run_main_analysis.py \
        --input /path/to/putin_dataset \
        --output /path/to/analysis_output \
        --project-root 3ddfav3 \
        --calibration /path/to/calibration_dir

Pipeline:
1. Stage1: 3DDFA_V3 reconstruction + UV extraction + skin analysis
2. Stage2: Chronological comparison with calibration thresholds
3. Stage3: HTML report generation

The calibration directory (from run_calibration.py) provides same-person
variability thresholds. Without it, Stage2 will fail (it requires calibration).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description='Main forensic face analysis pipeline')
    parser.add_argument('--input', required=True, type=Path, help='Input directory with photos')
    parser.add_argument('--output', required=True, type=Path, help='Output directory for analysis')
    parser.add_argument('--project-root', type=Path, default=ROOT / '3ddfav3', help='3DDFA-V3 root')
    parser.add_argument('--device', default='cpu', choices=['cpu', 'auto', 'cuda'])
    parser.add_argument('--backbone', default='resnet50', choices=['resnet50', 'mbnetv3'])
    parser.add_argument('--uv-size', type=int, default=1000)
    parser.add_argument('--calibration', type=Path, default=None, help='Path to calibration Stage-1 output directory')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of photos (0=all)')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--fail-fast', action='store_true')
    args = parser.parse_args()

    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: 3DDFA_V3 reconstruction + UV extraction ──────────────
    stage1_dir = out / 'stage1'
    print(f"\n{'='*60}")
    print(f"STAGE 1: 3DDFA_V3 reconstruction + UV extraction")
    print(f"{'='*60}")

    from app6.stage1.config import Stage1Config
    from app6.stage1.engine import Stage1Engine

    stage1_cfg = Stage1Config(
        project_root=args.project_root.resolve(),
        input_dir=args.input.resolve(),
        output_dir=stage1_dir,
        device=args.device,
        backbone=args.backbone,
        uv_size=args.uv_size,
        limit=args.limit,
        overwrite=args.overwrite,
        continue_on_error=not args.fail_fast,
        save_original=True,
    )
    stage1_manifest = Stage1Engine(stage1_cfg).run()
    print(f"[Main] Stage1 complete: {stage1_manifest.get('success_count', 0)} photos, "
          f"{stage1_manifest.get('error_count', 0)} errors")

    # ── Stage 2: Chronological pair comparison ────────────────────────
    if not args.calibration:
        print("\n[Main] WARNING: No --calibration provided. Stage2 requires calibration data.")
        print("[Main] Run run_calibration.py first, then pass its output directory here.")
        return 1

    stage2_dir = out / 'stage2'
    print(f"\n{'='*60}")
    print(f"STAGE 2: Chronological pair comparison with calibration")
    print(f"{'='*60}")

    from app6.stage2 import Stage2Config, Stage2Engine

    stage2_cfg = Stage2Config(
        stage1_root=stage1_dir,
        calibration_root=args.calibration.resolve(),
        output_dir=stage2_dir,
        overwrite=args.overwrite,
    )
    stage2_manifest = Stage2Engine(stage2_cfg).run()
    print(f"[Main] Stage2 complete: {stage2_manifest.get('pair_count', 0)} pairs, "
          f"{stage2_manifest.get('change_point_count', 0)} change points")

    # ── Stage 2B: Private prior corroboration (optional) ──────────────
    stage2b_dir = out / 'stage2b'
    try:
        from app6.stage2b import Stage2BConfig, Stage2BEngine
        Stage2BEngine(Stage2BConfig(stage2_dir, stage2b_dir, overwrite=args.overwrite)).run()
        print(f"[Main] Stage2B complete")
    except Exception as e:
        print(f"[Main] Stage2B skipped: {e}")

    # ── Stage 3: HTML report ──────────────────────────────────────────
    stage3_dir = out / 'stage3'
    print(f"\n{'='*60}")
    print(f"STAGE 3: Report generation")
    print(f"{'='*60}")

    from app6.stage3 import Stage3Config, Stage3Engine
    Stage3Engine(Stage3Config(stage2_dir, stage3_dir, overwrite=args.overwrite)).run()
    print(f"[Main] Stage3 complete: {stage3_dir / 'index.html'}")

    # ── Summary ────────────────────────────────────────────────────────
    summary = {
        'input': str(args.input.resolve()),
        'output': str(out),
        'calibration': str(args.calibration) if args.calibration else None,
        'stage1_success': stage1_manifest.get('success_count', 0),
        'stage2_pairs': stage2_manifest.get('pair_count', 0),
        'stage2_change_points': stage2_manifest.get('change_point_count', 0),
    }
    (out / 'ANALYSIS_SUMMARY.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )

    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
