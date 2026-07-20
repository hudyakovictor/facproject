from __future__ import annotations
import json,shutil,tempfile
from pathlib import Path
import cv2,numpy as np
from .pipeline import build_skin_package
from ..geometry import unpack_mask
class SkinStage1Batch:
 def __init__(self,stage1_root,atlas_path,overwrite=False):self.root=Path(stage1_root);self.atlas=Path(atlas_path);self.overwrite=overwrite
 def run(self):
  ok=skip=fail=0;errors=[]
  for d in sorted(self.root.iterdir()):
   if not (d/'info.json').is_file():continue
   final=d/'skin'
   if (final/'SUCCESS').is_file() and not self.overwrite:skip+=1;continue
   try:
    info=json.loads((d/'info.json').read_text());original=next((p for p in d.glob('original.*') if p.is_file()),None)
    if original is None:raise FileNotFoundError('saved original absent')
    from .input_provenance import decode_oriented
    bgr,_=decode_oriented(original)
    with np.load(d/'reconstruction.npz',allow_pickle=False) as z:
     tri=z['triangles'];vis=unpack_mask(z['full_mesh_visible_packbits'],len(z['vertices_object'])).astype(bool);kwargs={'triangles':tri,'vertices_original_xy':_to_original(z['vertices_image_224'],z['trans_params']),'vertices_depth':z['vertices_camera'][:,2],'normals':z['normals_posed'],'surface_vertices':z['vertices_object_normalized'],'vertex_visibility':vis}
    temp=Path(tempfile.mkdtemp(prefix='.skin-retry-',dir=d))
    build_skin_package(photo_id=info['photo_id'],input_path=original,bgr=bgr,out_dir=temp,face_mask_data_path=d/'face_mask.npz',atlas_path=self.atlas,coordinate_chain={'retry_from_reconstruction':True,'original_info':info.get('crop')},models={'model_hash':info.get('model_hash')},config={'retry_skin_only':True},pose=info.get('pose',{}),**kwargs)
    if final.exists():shutil.rmtree(final)
    (temp/'skin').replace(final);shutil.rmtree(temp,ignore_errors=True);info['skin']={'state':'success_retry_without_reconstruction'};info.setdefault('files',{})['skin_manifest']='skin/manifest.json';info['files'].pop('skin_failure',None);from .serialization import atomic_json;atomic_json(d/'info.json',info);(d/'skin_failure.json').unlink(missing_ok=True);from ..validator import validate_photo;result=validate_photo(d,write_result=True)
    if result['status']!='complete':raise RuntimeError('post-retry validation failed: '+str(result['errors']))
    ok+=1
   except Exception as e:fail+=1;errors.append({'directory':str(d),'error':str(e)})
  return {'schema':'skin-stage1-batch-v1','complete':ok,'skipped':skip,'failed':fail,'errors':errors,'reconstruction_calls':0}
def _to_original(points,trans):
 from ..geometry import to_original_image
 return to_original_image(points,trans)
