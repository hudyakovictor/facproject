#!/usr/bin/env python3
"""🚪 ENTRY POINT → Управление жизненным циклом skin-run'а (lock/finalize/status).
🔗 DEPENDS ON: stage1.skin.run_manager — вся логика делегирована туда
💡 NOTE: тонкая CLI-обёртка; не содержит бизнес-логики сама по себе.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from app6.stage1.skin.run_manager import SkinRunManager
p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True);i=sub.add_parser('init');i.add_argument('--run-root',required=True);i.add_argument('--config',required=True);i.add_argument('--atlas',default='app6/atlas/texture_zones_bfm35709_v3.npz');i.add_argument('--asset',action='append',default=[]);i.add_argument('--calibration');f=sub.add_parser('finalize');f.add_argument('--run-root',required=True);a=p.parse_args();m=SkinRunManager(a.run_root)
if a.cmd=='init':print(json.dumps(m.initialize(json.loads(Path(a.config).read_text()),a.asset,a.atlas,a.calibration),indent=2))
else:print(json.dumps(m.finalize(),indent=2))
