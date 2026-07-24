"""Read-only adapter over app6/test_module scientific scenarios."""
from __future__ import annotations
import ast,hashlib,json
from pathlib import Path
from typing import Any
PEOPLE=tuple(f"person_{i:02d}" for i in range(1,8));POSES={1:'left_profile',2:'left_deep',3:'left_mid',4:'left_light',5:'frontal',6:'right_light',7:'right_mid',8:'right_deep',9:'right_profile'}
class ScenarioLab:
 def __init__(self,app6:Path):self.app6=app6;self.root=app6/'test_module'
 def scenarios(self)->list[dict]:
  out=[]
  for p in sorted((self.root/'scenarios').glob('S*.json')):
   x=json.loads(p.read_text());out.append({k:x.get(k) for k in ('id','block','priority','mode','description','expect')}|{'frame_count':len(x.get('frames',[])),'source':str(p.relative_to(self.app6))})
  return out
 def role_map(self,variant:int)->dict[str,str]:
  if not 0<=variant<7:raise ValueError('variant must be 0..6')
  a=PEOPLE[variant];b=PEOPLE[(variant+1)%7];c=PEOPLE[(variant+2)%7];d=PEOPLE[(variant+3)%7];return {'A':a,'A2':b,'B':b,'C':c,'D':d}
 def plan(self,scenario_id:str,pose:str='frontal',combinations:int=1)->dict:
  if combinations not in (1,3,7):raise ValueError('combinations must be 1, 3, or 7')
  ids={x['id'] for x in self.scenarios()};base=scenario_id.removesuffix('.json')
  if base not in ids:raise ValueError('unknown scenario')
  pose_nos=list(POSES) if pose=='all' else [5] if pose=='frontal' else [int(pose)]
  if any(x not in POSES for x in pose_nos):raise ValueError('pose must be frontal, all, or 1..9')
  combos=[{'combo_no':i,'roles':self.role_map(i)} for i in range(combinations)]
  return {'schema':'dpo-scenario-plan-v1','scenario_id':base,'pose':pose,'poses':[{'pose_no':x,'pose_bin':POSES[x]} for x in pose_nos],'combinations':combos,'case_count':len(pose_nos)*len(combos),'generator':'app6.test_module.scenarios','synthetic_disclaimer':'Synthetic validates contracts/regressions, not forensic accuracy or thresholds.'}
 def function_matrix(self)->list[dict]:
  tree=ast.parse((self.root/'registry.py').read_text());rows=[]
  for n in tree.body:
   if isinstance(n,ast.AnnAssign) and getattr(n.target,'id',None)=='FUNCTION_MAP':rows=ast.literal_eval(n.value)
  return [{'code':x['code'],'status':x['status'],'scenarios':x['scenarios'],'blocks':x['blocks'],'what':x['what']} for x in rows]
 def synthetic(self)->dict:
  asset=self.app6/'assets'/'face_model.npy';return {'runner':'app6.test_module.runner synthetic','asset':str(asset.relative_to(self.app6)),'asset_exists':asset.is_file(),'asset_hash':hashlib.sha256(asset.read_bytes()).hexdigest() if asset.is_file() else None,'claim_boundary':'contracts/regressions only; not accuracy or identity proof'}
 def fresh5(self,trusted_rows:list[dict],person:str,pose_bin:str)->dict:
  rows=[r for r in trusted_rows if r.get('dataset_id')==person and r.get('pose_bin')==pose_bin]
  rows=sorted(rows,key=lambda r:(float(r.get('yaw',0)),str(r.get('calibration_photo_id') or r.get('record_id') or '')))
  if len(rows)<5:raise ValueError('Fresh-5 requires five trusted rows')
  picks=[rows[round(i*(len(rows)-1)/4)] for i in range(5)]
  safe=[{k:r.get(k) for k in ('dataset_id','main_photo_id','calibration_photo_id','record_id','yaw','pitch','roll','pose_bin') if k in r} for r in picks]
  return {'profile':'Fresh-5','person':person,'pose_bin':pose_bin,'photos':safe,'coordinates_used':False,'reextract_stage1':True}
