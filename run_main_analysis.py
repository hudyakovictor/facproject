#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

def _run(cmd:list[str]): print('+',' '.join(cmd),flush=True); subprocess.run(cmd,check=True,cwd=ROOT)

def main()->int:
    p=argparse.ArgumentParser(description='One-command calibrated main dataset analysis')
    p.add_argument('--input',required=True,type=Path,help='main YYYY_MM_DD[_N] image tree')
    p.add_argument('--calibration',required=True,type=Path,help='successful run_calibration.py output directory')
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--project-root',type=Path,default=ROOT/'3ddfav3'); p.add_argument('--device',default='cpu',choices=['cpu','auto','cuda'])
    p.add_argument('--backbone',default='resnet50',choices=['resnet50','mbnetv3']); p.add_argument('--uv-size',type=int,default=768)
    p.add_argument('--overwrite',action='store_true'); p.add_argument('--limit',type=int,default=0); p.add_argument('--allow-failed-calibration',action='store_true')
    a=p.parse_args(); cal=a.calibration.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    profile=cal/'calibration_profile.json'; report_path=cal/'calibration_report.json'; cal_stage1=cal/'stage1'
    for x in (profile,report_path,cal_stage1):
        if not x.exists(): raise FileNotFoundError(f'incomplete calibration run: missing {x}')
    report=json.loads(report_path.read_text(encoding='utf-8'))
    if not report.get('acceptance',{}).get('test_pass') and not a.allow_failed_calibration:
        raise RuntimeError('calibration held-out test did not pass; refusing main analysis')
    stage1=out/'stage1'
    cmd=[sys.executable,str(ROOT/'app6/run_stage1.py'),'--project-root',str(a.project_root.resolve()),'--input',str(a.input.resolve()),'--output',str(stage1),'--device',a.device,'--backbone',a.backbone,'--uv-size',str(a.uv_size)]
    if a.limit: cmd += ['--limit',str(a.limit)]
    if a.overwrite: cmd += ['--overwrite']
    _run(cmd)
    chronology=out/'wrinkle_chronology.json'
    _run([sys.executable,str(ROOT/'scripts/run_wrinkle_chronology.py'),'--stage1',str(stage1),'--profile',str(profile),'--output',str(chronology)])
    stage2=out/'stage2'
    s2=[sys.executable,str(ROOT/'app6/run_stage2.py'),'--stage1',str(stage1),'--calibration',str(cal_stage1),'--output',str(stage2)]
    if a.overwrite: s2 += ['--overwrite']
    _run(s2)
    chron=json.loads(chronology.read_text(encoding='utf-8'))
    status_counts={}
    for row in chron.get('pairs',[]): status_counts[row['status']]=status_counts.get(row['status'],0)+1
    summary={'calibration_profile':str(profile),'main_stage1':str(stage1),'stage2':str(stage2),'wrinkle_chronology':str(chronology),'pair_status_counts':status_counts}
    (out/'RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
