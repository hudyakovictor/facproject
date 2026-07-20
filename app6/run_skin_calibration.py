#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from app6.stage2.skin.dataset import validate_skin_dataset
from app6.stage2.skin.package_calibration import build_package_calibration
p=argparse.ArgumentParser();p.add_argument('--stage1',required=True);p.add_argument('--dataset-root',required=True);p.add_argument('--metadata',required=True);p.add_argument('--output',required=True);p.add_argument('--target-false-anomaly',type=float,default=.01);a=p.parse_args();v=validate_skin_dataset(a.dataset_root,a.metadata)
if not v['ok']:raise SystemExit(json.dumps(v,ensure_ascii=False,indent=2))
r=build_package_calibration(a.stage1,a.metadata,a.output,a.target_false_anomaly);print(json.dumps(r,ensure_ascii=False,indent=2))
