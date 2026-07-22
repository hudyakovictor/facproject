#!/usr/bin/env python3
"""🚪 ENTRY POINT → Skin Stage 1: извлечение skin-пакета из фото.
🔗 DEPENDS ON: stage1.skin.pipeline.build_skin_package()
💡 NOTE: отдельный от run_stage1.py вход — skin-слой опционален к основному.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from app6.stage1.skin.batch import SkinStage1Batch
p=argparse.ArgumentParser(description='Build/retry native skin packages without 3DDFA inference');p.add_argument('--stage1',required=True);p.add_argument('--atlas',default='app6/atlas/texture_zones_bfm35709_v3.npz');p.add_argument('--overwrite',action='store_true');a=p.parse_args();print(json.dumps(SkinStage1Batch(a.stage1,a.atlas,a.overwrite).run(),indent=2))
