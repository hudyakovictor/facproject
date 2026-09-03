#!/usr/bin/env python3
"""🚪 ENTRY POINT → Stage 2B: пост-обработка и сводные таблицы после Stage 2.
🔗 DEPENDS ON: stage2b.engine.run()
⚠️ IN PROGRESS: часть реестров пост-отчётов ещё наполняется.
"""
from __future__ import annotations
import argparse, sys
import os
from pathlib import Path
APP_DIR=Path(__file__).resolve().parent
DEFAULT_ROOT=APP_DIR.parent

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description='DEEPUTIN app6 stage 2B private prior corroboration')
    p.add_argument('--project-root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--stage2',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-root',type=Path,default=None)
    p.add_argument('--overwrite',action='store_true')
    return p

# 🚪 ENTRY POINT Stage 2B → stage2b.engine.run()
def main()->int:
    a=build_parser().parse_args();root=a.project_root.resolve()
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    os.chdir(root)
    from app6.stage2b import Stage2BConfig,Stage2BEngine
    Stage2BEngine(Stage2BConfig(
        stage2_root=a.stage2.resolve(),
        output_dir=a.output.resolve(),
        prior_root=a.prior_root.resolve() if a.prior_root else None,
        overwrite=a.overwrite,
        project_root=root,
    )).run();return 0
if __name__=='__main__':raise SystemExit(main())
