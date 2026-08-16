#!/usr/bin/env python3
"""🚪 ENTRY POINT → Stage 2: попарный анализ (evidence, chronology, metrics).
🔗 DEPENDS ON: stage2.engine.run() — весь пайплайн анализа
💡 NOTE: читает вывод Stage 1 (stage1_output/), сам inference не выполняет.
"""
from __future__ import annotations
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app6.stage2 import Stage2Config,Stage2Engine

# 🚪 ENTRY POINT Stage 2 → stage2.engine.run()
def main():
 p=argparse.ArgumentParser(description='DEEPUTIN app6 stage 2')
 p.add_argument('--stage1',required=True,type=Path)
 p.add_argument('--calibration',required=True,type=Path)
 p.add_argument('--output',required=True,type=Path)
 p.add_argument('--overwrite',action='store_true')
 p.add_argument('--lead-archive',type=Path,help='Prior final_inference/add archive; used for coverage auditing only')
 a=p.parse_args()
 Stage2Engine(Stage2Config(a.stage1.resolve(),a.calibration.resolve(),a.output.resolve(),a.overwrite,lead_archive=a.lead_archive.resolve() if a.lead_archive else None)).run()
 return 0
if __name__=='__main__':raise SystemExit(main())
