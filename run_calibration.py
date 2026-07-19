#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
IMAGE_EXT={'.jpg','.jpeg','.png','.webp','.bmp','.tif','.tiff'}

def _prepare(raw:Path,staged:Path,cal_date:str)->int:
    d=date.fromisoformat(cal_date); staged.mkdir(parents=True,exist_ok=True)
    files=sorted(p for p in raw.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_EXT)
    if not files: raise ValueError(f'no images found in {raw}')
    # Копируем, если исходник на другом устройстве (SDCARD/внешний диск) —
    # symlink на смонтированный том ломается, если том отвалится во время прогона.
    try: staged_dev=os.stat(staged).st_dev
    except OSError: staged_dev=None
    for i,p in enumerate(files,1):
        target=staged/f'{d.year:04d}_{d.month:02d}_{d.day:02d}_{i}{p.suffix.lower()}'
        if target.exists(): continue
        same_dev = staged_dev is not None and os.stat(p).st_dev==staged_dev
        if same_dev:
            try: os.symlink(p.resolve(),target); continue
            except OSError: pass
        shutil.copy2(p,target)
    return len(files)

def _run(cmd:list[str]):
    print('+',' '.join(cmd),flush=True); subprocess.run(cmd,check=True,cwd=ROOT)

def main()->int:
    p=argparse.ArgumentParser(description='One-command same-day calibration')
    p.add_argument('--input',required=True,type=Path,help='folder with same-person, same-day calibration photos')
    p.add_argument('--output',required=True,type=Path,help='calibration run directory')
    p.add_argument('--date',default='2000-01-01',help='real or neutral calibration date YYYY-MM-DD')
    p.add_argument('--project-root',type=Path,default=ROOT/'3ddfav3')
    p.add_argument('--device',default='cpu',choices=['cpu','auto','cuda']); p.add_argument('--backbone',default='resnet50',choices=['resnet50','mbnetv3'])
    p.add_argument('--uv-size',type=int,default=768); p.add_argument('--target-false-anomaly',type=float,default=.01)
    p.add_argument('--overwrite',action='store_true'); p.add_argument('--limit',type=int,default=0)
    a=p.parse_args(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    staged=out/'staged_input'; count=_prepare(a.input.resolve(),staged,a.date)
    stage1=out/'stage1'
    cmd=[sys.executable,str(ROOT/'app6/run_stage1.py'),'--project-root',str(a.project_root.resolve()),'--input',str(staged),'--output',str(stage1),'--device',a.device,'--backbone',a.backbone,'--uv-size',str(a.uv_size)]
    if a.limit: cmd += ['--limit',str(a.limit)]
    if a.overwrite: cmd += ['--overwrite']
    _run(cmd)
    from uv_module.calibration import calibrate
    profile,report=calibrate(stage1,out,a.target_false_anomaly)
    summary={'input_images':count,'stage1':str(stage1),'profile':str(out/'calibration_profile.json'),'report':str(out/'calibration_report.json'),'acceptance':report['acceptance'],'coverage':report['coverage']}
    (out/'RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if not report['acceptance']['test_pass']:
        print('CALIBRATION DID NOT PASS held-out same-day acceptance. Inspect calibration_report.json.',file=sys.stderr); return 3
    print('CALIBRATION PASSED. Use this output directory with run_main_analysis.py.')
    return 0
if __name__=='__main__': raise SystemExit(main())
