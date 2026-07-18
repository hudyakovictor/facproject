from __future__ import annotations
import argparse,json
from pathlib import Path
from uv_module.chronology import analyze_records,load_stage1_records
p=argparse.ArgumentParser(description="Pose-aware chronological Skan analysis")
p.add_argument("--stage1",type=Path,required=True); p.add_argument("--output",type=Path,required=True)
p.add_argument("--profile",type=Path,help="calibration_profile.json")
a=p.parse_args(); records=load_stage1_records(a.stage1)
profile=None
if a.profile:
    from uv_module.calibration import load_profile
    profile=load_profile(a.profile)
report=analyze_records(records,profile)
a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"records":len(records),"pairs":len(report["pairs"]),"output":str(a.output)},ensure_ascii=False))
