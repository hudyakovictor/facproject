#!/usr/bin/env python3
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from app6.stage2.skin.engine import SkinStage2Engine
p=argparse.ArgumentParser();p.add_argument('--stage1',required=True);p.add_argument('--output',required=True);p.add_argument('--calibration');a=p.parse_args();SkinStage2Engine(a.stage1,a.output,a.calibration).run()
