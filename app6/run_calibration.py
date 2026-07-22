#!/usr/bin/env python3
"""Run stage1 + skin sequentially per photo — single Python process, no model reload.

🚪 CONVENTIONS v2 → ENTRY POINT калибровки; статус: ✅ VERIFIED
"""
import sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)

# 🚪 ENTRY POINT → см. модульный docstring
def main():
 from app6.stage1.config import Stage1Config
 from app6.stage1.engine import Stage1Engine

 inp=Path('/Volumes/SDCARD/storage/calibration_input')
 out=Path('/Volumes/SDCARD/storage/stage1')

 cfg=Stage1Config(project_root=ROOT,input_dir=inp,output_dir=out,device='auto',overwrite=True)
 engine=Stage1Engine(cfg)

 photos=sorted(p for p in inp.rglob('*') if p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png') and not p.name.startswith('._'))
 total=len(photos);ok=fail=0

 for i,path in enumerate(photos,1):
  base=path.name
  print(f'[{i}/{total}] {base}',flush=True)
  try:
   # ---- stage1 + skin via the single fixed pipeline (audit fix A2) ----
   # Stage1Engine._one performs: decode/orient, 3DDFA reconstruction with
   # full chronology pose correction, NaN/Inf validation, asset writing and a
   # skin-package attempt (reusing the same reconstruction — no double inference).
   info, was_skipped = engine._one(path)
   ok+=1
   print(f'  OK',flush=True)
  except Exception as e:
   import traceback;traceback.print_exc();print(f'  FAIL: {e}',flush=True)
   fail+=1

 print(f'DONE ok={ok} fail={fail} total={total}',flush=True)

if __name__=='__main__':
 main()
