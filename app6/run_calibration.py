#!/usr/bin/env python3
"""Run stage1 + skin sequentially per photo — single Python process, no model reload.

🚪 CONVENTIONS v2 → ENTRY POINT калибровки; статус: ✅ VERIFIED
"""
import argparse,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)

# 🔧 FIX (D13): пути к данным больше не зашиты в код. Раньше здесь стояли
# абсолютные пути к съёмному носителю конкретной машины, из-за чего даже
# `--help` падал с FileNotFoundError и скрипт был непереносим.
# 🔥 ВАЖНО: pre-extracted данные в calibration_dataset/person_*/frame_*/
# признаны неактуальными. Используются ТОЛЬКО сырые фото из photos/.
DEFAULT_INPUT=Path('calibration_dataset/photos')
DEFAULT_OUTPUT=Path('/Volumes/SDCARD/project_data/calibration_stage1')

# 🚪 ENTRY POINT → см. модульный docstring
def main():
 from app6.stage1.config import Stage1Config
 from app6.stage1.engine import Stage1Engine

 parser=argparse.ArgumentParser(description='DEEPUTIN calibration stage1 run')
 parser.add_argument('--input',type=Path,default=DEFAULT_INPUT,help='каталог калибровочных фото')
 parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT,help='каталог вывода Stage 1')
 args=parser.parse_args()
 inp=args.input.resolve()
 out=args.output.resolve()

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
