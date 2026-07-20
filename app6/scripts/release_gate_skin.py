#!/usr/bin/env python3
import argparse,json,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app6.stage2.skin.dataset import validate_skin_dataset
def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=('engineering','calibration','main'),default='engineering');p.add_argument('--dataset-root');p.add_argument('--metadata');p.add_argument('--calibration-artifact');a=p.parse_args();checks=[]
 def add(n,ok,d=''):checks.append({'name':n,'ok':bool(ok),'detail':str(d)})
 t=subprocess.run([sys.executable,'-m','unittest','discover','-s','app6/tests'],cwd=ROOT,capture_output=True,text=True);add('unit_tests',t.returncode==0,(t.stdout+t.stderr)[-1000:]);gen=(ROOT/'uv_module/hd_uv_generator.py').read_text();assets=(ROOT/'app6/stage1/assets.py').read_text();add('single_uv_contract','uv_tex_analysis' not in gen and 'uv_tex_beauty' not in gen and 'analysis_bgr=' not in assets and 'synthetic_bgr=' not in assets);add('atlas_v3',(ROOT/'app6/atlas/texture_zones_bfm35709_v3.npz').is_file())
 fm=ROOT/'assets/face_model.npy'
 if fm.is_file():
  sm=subprocess.run([sys.executable,'app6/scripts/smoke_skin_without_inference.py','--face-model',str(fm)],cwd=ROOT,capture_output=True,text=True);add('skin_package_smoke',sm.returncode==0,(sm.stdout+sm.stderr)[-1000:])
 if a.phase in {'calibration','main'}:
  for rel in ('assets/face_model.npy','assets/net_recon.pth','assets/large_base_net.pth','FFHQ-detect-face-wrinkles/res/cp/face_segmentation.pth'):
   add('asset:'+rel,(ROOT/rel).is_file(),'present' if (ROOT/rel).is_file() else 'missing')
  wc=[ROOT/'FFHQ-detect-face-wrinkles/res/cp/wrinkle_model.pth',ROOT/'FFHQ-detect-face-wrinkles/res/cp/best_checkpoint_iou032.pth'];add('asset:FFHQ-wrinkle-checkpoint',any(x.is_file() for x in wc),'present' if any(x.is_file() for x in wc) else 'missing')
  if a.dataset_root and a.metadata:d=validate_skin_dataset(a.dataset_root,a.metadata);add('skin_dataset',d['ok'],d)
  else:add('skin_dataset',False,'--dataset-root and --metadata required')
 if a.phase=='main':
  try:c=json.loads(Path(a.calibration_artifact).read_text());add('frozen_calibration',c.get('frozen') is True and bool(c.get('artifact_sha256')),c.get('artifact_sha256'))
  except Exception as e:add('frozen_calibration',False,e)
 report={'schema':'skin-release-gate-v1','phase':a.phase,'ready':all(x['ok'] for x in checks),'checks':checks};print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['ready'] else 2
if __name__=='__main__':raise SystemExit(main())
