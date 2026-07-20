import hashlib,json
from pathlib import Path
import numpy as np
def build_morph_contract(photo_a,photo_b,reconstruction_a,reconstruction_b,uv_a,uv_b,out):
 with np.load(reconstruction_a,allow_pickle=False) as A,np.load(reconstruction_b,allow_pickle=False) as B:
  if not np.array_equal(A['triangles'],B['triangles']):raise ValueError('morphing requires identical ordered topology')
  topo=hashlib.sha256(A['triangles'].astype('<i4').tobytes()).hexdigest()
 for p in (uv_a,uv_b):
  with np.load(p,allow_pickle=False) as z:
   forbidden={'analysis_bgr','synthetic_bgr','beauty_bgr'}&set(z.files)
   if forbidden or 'texture_bgr' not in z:raise ValueError('single UV render contract violated')
 q={'schema':'skin-morph-contract-v1','photo_a':photo_a,'photo_b':photo_b,'topology_sha256':topo,'geometry_inputs':[str(reconstruction_a),str(reconstruction_b)],'texture_inputs':[str(uv_a),str(uv_b)],'texture_field':'texture_bgr','interpolation':'not_executed_contract_only','evidence_policy':'morph output visualization only; never skin evidence'};Path(out).write_text(json.dumps(q,indent=2));return q
