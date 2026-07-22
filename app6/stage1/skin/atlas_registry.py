from __future__ import annotations
import hashlib,json
from pathlib import Path
import numpy as np
from ..status_logger import log_status, log_blocker, log_warning
class AtlasRegistry:
 def __init__(self,path,triangles=None):
  self.path=Path(path);z=np.load(self.path,allow_pickle=False);self.schema=int(z['schema_version']);self.A=z['triangle_main_label'].astype(np.int8);self.S=z['triangle_subzone_label'].astype(np.int8);self.W=z['triangle_focus_mask'].astype(bool);self.skin=z['triangle_skin_mask'].astype(bool);self.boundary=z['triangle_boundary_distance'].astype(np.uint8);self.cores={k:z[f'triangle_{k}_mask'].astype(bool) for k in ('core0','core3','core5')};self.A_codes=tuple(map(str,z['main_codes']));self.S_codes=tuple(map(str,z['subzone_codes']));self.W_codes=tuple(map(str,z['focus_codes']));self.S_parent=z['subzone_parent_main'].astype(np.int8);self.topology_hash=str(z['topology_tri_sha256']);self.file_hash=self._sha(self.path);self.validate();
  if triangles is not None:self.verify_topology(triangles)
 @staticmethod
 def _sha(p):
  h=hashlib.sha256();h.update(Path(p).read_bytes());return h.hexdigest()
 def verify_topology(self,triangles):
  t=np.asarray(triangles,dtype='<i4');got=hashlib.sha256(t.tobytes(order='C')).hexdigest()
  if t.shape!=(70789,3) or got!=self.topology_hash:raise ValueError('atlas/topology mismatch (shape or ordered tri SHA-256)')
  return True
 def validate(self):
  if self.schema!=3:raise ValueError('only additive atlas v3 accepted')
  if self.A.shape!=(70789,) or self.S.shape!=(70789,) or self.W.shape!=(14,70789):raise ValueError('atlas array shape')
  if np.any(self.A[self.skin]<0) or np.any(self.S[self.skin]<0):raise ValueError('unassigned skin')
  if np.any(self.A[~self.skin]!=-1) or np.any(self.S[~self.skin]!=-1) or np.any(self.W[:,~self.skin]):raise ValueError('atlas leaves skin domain')
  if np.any(self.S_parent[self.S[self.skin]]!=self.A[self.skin]):raise ValueError('S parent containment')
  if not(np.all(self.cores['core5']<=self.cores['core3']) and np.all(self.cores['core3']<=self.cores['core0'])):raise ValueError('Q nesting')
 def describe(self):return {'version':self.schema,'sha256':self.file_hash,'topology_tri_sha256':self.topology_hash,'laterality':'anatomical; subject-left is UV x>0.5; never image-left','A':20,'S':40,'W':14,'Q':['core0','core3','core5','boundary_distance']}
