#!/usr/bin/env python3
"""🚪 ENTRY POINT → Stage 2: попарный анализ (evidence, chronology, metrics).
🔗 DEPENDS ON: stage2.engine.run() — весь пайплайн анализа
💡 NOTE: читает вывод Stage 1 (stage1_output/), сам inference не выполняет.
"""
from __future__ import annotations
import argparse,os,sys
from pathlib import Path
APP_DIR=Path(__file__).resolve().parent
DEFAULT_ROOT=APP_DIR.parent
if str(DEFAULT_ROOT) not in sys.path: sys.path.insert(0,str(DEFAULT_ROOT))

def build_parser()->argparse.ArgumentParser:
 p=argparse.ArgumentParser(description='DEEPUTIN app6 stage 2')
 p.add_argument('--project-root',type=Path,default=DEFAULT_ROOT)
 p.add_argument('--stage1',required=True,type=Path)
 p.add_argument('--calibration',required=True,type=Path)
 p.add_argument('--output',required=True,type=Path)
 p.add_argument('--overwrite',action='store_true')
 p.add_argument('--checkpoint-every',type=int,default=0,help='Persist an atomic checkpoint every N completed pairs')
 p.add_argument('--resume',action='store_true',help='Resume from stage2_checkpoint.pkl in the output directory')
 p.add_argument('--lead-archive',type=Path,help='Prior final_inference/add archive; used for coverage auditing only')
 return p

# 🚪 ENTRY POINT Stage 2 → stage2.engine.run()
def main():
 a=build_parser().parse_args()
 root=a.project_root.resolve()
 if str(root) not in sys.path:sys.path.insert(0,str(root))
 os.chdir(root)
 from app6.stage2 import Stage2Config,Stage2Engine
 Stage2Engine(Stage2Config(a.stage1.resolve(),a.calibration.resolve(),a.output.resolve(),a.overwrite,lead_archive=a.lead_archive.resolve() if a.lead_archive else None,checkpoint_every=a.checkpoint_every,resume=a.resume)).run()
 return 0
if __name__=='__main__':raise SystemExit(main())
