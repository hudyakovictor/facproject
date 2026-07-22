#!/usr/bin/env python3
"""🚪 ENTRY POINT → Skin Stage 3: рендер отчёта по skin-каналам.
🔗 DEPENDS ON: stage3.skin.engine
🔗 DEPENDS ON: stage3.skin.report.render_report() — валидация языка отчёта.
"""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from app6.stage3.skin.engine import SkinStage3Engine
p=argparse.ArgumentParser();p.add_argument('--stage2',required=True);p.add_argument('--output',required=True);a=p.parse_args();SkinStage3Engine(a.stage2,a.output).run()
