#!/usr/bin/env python3
"""✅ VERIFIED → Pre-flight проверка готовности каталога к skin v3 (атлас, ассеты).
🔗 DEPENDS ON: stage1.skin.atlas_registry.validate()
🚪 ENTRY POINT: main() (helper add() — 🔄 CALLBACK для чек-листа).
"""
from __future__ import annotations
import argparse,importlib.util,json,shutil,subprocess,sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
import numpy as np
from app6.stage1.skin.atlas_registry import AtlasRegistry
from app6.stage1.skin.serialization import sha256_file

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',default='.');p.add_argument('--skip-tests',action='store_true');a=p.parse_args();r=Path(a.project_root).resolve();checks=[]
 def add(name,ok,detail,block=True):checks.append({'name':name,'ok':bool(ok),'blocking':block,'detail':str(detail)})
 for rel in ('assets/face_model.npy','assets/net_recon.pth','assets/large_base_net.pth'):
  q=r/rel;add('asset:'+rel,q.is_file(),sha256_file(q) if q.is_file() else 'missing')
 atlas=r/'app6/atlas/texture_zones_bfm35709_v3.npz'
 try:
  z=AtlasRegistry(atlas);add('atlas_v3',True,z.describe())
 except Exception as e:add('atlas_v3',False,e)
 for mod,required in [('numpy',True),('cv2',True),('scipy',True),('skimage',True),('torch',True),('skan',False),('potpourri3d',False)]:add('python:'+mod,importlib.util.find_spec(mod) is not None,'installed' if importlib.util.find_spec(mod) else 'missing',required)
 usage=shutil.disk_usage(r);add('disk_free_20GB',usage.free>=20*1024**3,f'{usage.free/1024**3:.1f} GiB free')
 if not a.skip_tests:
  x=subprocess.run([sys.executable,'-m','unittest','discover','-s','app6/tests'],cwd=r,capture_output=True,text=True);add('unit_tests',x.returncode==0,(x.stdout+x.stderr)[-2000:])
 report={'schema':'skin-preflight-v1','python':sys.version,'project_root':str(r),'checks':checks,'ready':all(c['ok'] for c in checks if c['blocking'])};print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['ready'] else 2
if __name__=='__main__':raise SystemExit(main())
