#!/usr/bin/env python3
"""🚪 ENTRY POINT → Stage 2B: пост-обработка и сводные таблицы после Stage 2.
🔗 DEPENDS ON: stage2b.engine.run()
⚠️ IN PROGRESS: часть реестров пост-отчётов ещё наполняется.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
APP_DIR=Path(__file__).resolve().parent
DEFAULT_ROOT=APP_DIR.parent

# 🚪 ENTRY POINT Stage 2B → stage2b.engine.run()
def main()->int:
    p=argparse.ArgumentParser(description='DEEPUTIN app6 stage 2B private prior corroboration')
    p.add_argument('--project-root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--stage2',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-root',type=Path,default=None)
    p.add_argument('--overwrite',action='store_true')
    a=p.parse_args();root=a.project_root.resolve()
    if str(root) not in sys.path:sys.path.insert(0,str(root))
    from app6.stage2b import Stage2BConfig,Stage2BEngine
    Stage2BEngine(Stage2BConfig(a.stage2.resolve(),a.output.resolve(),a.prior_root.resolve() if a.prior_root else None,a.overwrite)).run();return 0
if __name__=='__main__':raise SystemExit(main())
