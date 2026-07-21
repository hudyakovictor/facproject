#!/usr/bin/env python3
"""Run stage1 + skin sequentially per photo — single Python process, no model reload."""
import sys,os,json,shutil,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)

def main():
 from app6.stage1.config import Stage1Config
 from app6.stage1.engine import Stage1Engine
 from app6.stage1.naming import parse_photo_name,sha256_file as sf
 from app6.stage1.geometry import unpack_mask,to_original_image
 from app6.stage1.skin.pipeline import build_skin_package
 from app6.stage1.skin.input_provenance import decode_oriented
 from app6.stage1.skin.batch import _to_original
 from app6.stage1.serialization import atomic_json

 inp=Path('/Volumes/SDCARD/storage/calibration_input')
 out=Path('/Volumes/SDCARD/storage/stage1')
 atlas=ROOT/'app6/atlas/texture_zones_bfm35709_v3.npz'

 cfg=Stage1Config(project_root=ROOT,input_dir=inp,output_dir=out,device='auto',overwrite=True)
 engine=Stage1Engine(cfg)

 photos=sorted(p for p in inp.rglob('*') if p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png') and not p.name.startswith('._'))
 total=len(photos);ok=fail=0

 for i,path in enumerate(photos,1):
  base=path.name
  print(f'[{i}/{total}] {base}',flush=True)
  try:
   parsed=parse_photo_name(path)
   source_hash=sf(path)
   from app6.stage1.naming import make_photo_id
   pid=make_photo_id(parsed,source_hash)
   final=out/pid

   # ---- stage1 ----
   bgr,decode_meta=engine._decode_oriented(path)
   rec=engine.recon.process(path,cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))
   engine._save_output(final,path,bgr,rec,decode_meta)
   # _save_output also saves info.json

   # ---- skin ----
   bgr2,_=decode_oriented(path)
   with np.load(final/'reconstruction.npz',allow_pickle=False) as z:
    tri=z['triangles'];vis=unpack_mask(z['full_mesh_visible_packbits'],len(z['vertices_object'])).astype(bool)
    kwargs={'triangles':tri,'vertices_original_xy':_to_original(z['vertices_image_224'],z['trans_params']),
            'vertices_depth':z['vertices_camera'][:,2],'normals':z['normals_posed'],
            'surface_vertices':z['vertices_object_normalized'],'vertex_visibility':vis}
   with open(final/'info.json') as f:info=json.load(f)
   tmp=Path(tempfile.mkdtemp(prefix='.skin-',dir=final))
   build_skin_package(photo_id=pid,input_path=path,bgr=bgr2,out_dir=tmp,
    face_mask_data_path=final/'face_mask.npz',atlas_path=atlas,
    coordinate_chain={'retry_from_reconstruction':True,'original_info':info.get('crop')},
    models={'model_hash':info.get('model_hash')},config={'retry_skin_only':True},
    pose=info.get('pose',{}),**kwargs)
   sk=final/'skin'
   if sk.exists():shutil.rmtree(sk)
   (tmp/'skin').replace(sk);shutil.rmtree(tmp,ignore_errors=True)
   info['skin']={'state':'success'};info.setdefault('files',{})['skin_manifest']='skin/manifest.json'
   atomic_json(final/'info.json',info)
   ok+=1
   print(f'  OK',flush=True)
  except Exception as e:
   import traceback;traceback.print_exc();print(f'  FAIL: {e}',flush=True)
   fail+=1

 print(f'DONE ok={ok} fail={fail} total={total}',flush=True)

if __name__=='__main__':
 import numpy as np,cv2;main()
