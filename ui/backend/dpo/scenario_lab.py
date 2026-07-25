"""Read-only adapter over app6/test_module scientific scenarios."""
from __future__ import annotations
import ast,hashlib,json,re
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
 def maximum_plan(self)->dict:
  scenarios=self.scenarios();per_scenario=len(POSES)*7
  return {'schema':'dpo-scenario-maximum-plan-v1','profile':'MAXIMUM','scenario_count':len(scenarios),'pose_count':len(POSES),'combination_count':7,'case_count':len(scenarios)*per_scenario,'scenarios':[{'id':x['id'],'block':x['block'],'priority':x['priority'],'description':x['description'],'case_count':per_scenario} for x in scenarios],'poses':[{'pose_no':n,'pose_bin':POSES[n]} for n in POSES],'claim_boundary':'A generated plan is not a passed test. PASS requires a check_result.json for every expected case.'}
 def maximum_results(self)->dict:
  bases=[x['id'] for x in self.scenarios()]
  expected=[f'{base}_p{pose:02d}_v{variant:02d}' for base in bases for pose in POSES for variant in range(7)]
  found={}
  for path in sorted((self.root/'runs').glob('**/check_result.json')) if (self.root/'runs').is_dir() else ():
   try:
    payload=json.loads(path.read_text(encoding='utf-8'));sid=str(payload.get('scenario_id') or '')
    if not sid:continue
    stat=path.stat();row={'scenario_id':sid,'passed':bool(payload.get('passed')),'failed_checks':[str(x.get('check') or 'unknown') for x in payload.get('checks',[]) if not x.get('ok')],'path':str(path.relative_to(self.app6)),'modified_ns':stat.st_mtime_ns}
    if sid not in found or row['modified_ns']>found[sid]['modified_ns']:found[sid]=row
   except (OSError,ValueError,TypeError,json.JSONDecodeError):continue
  expected_set=set(expected);matched={k:v for k,v in found.items() if k in expected_set};passed=sum(bool(x['passed']) for x in matched.values());failed=sum(not bool(x['passed']) for x in matched.values());not_run=len(expected)-len(matched)
  if failed:state='failed'
  elif passed==len(expected):state='passed'
  elif not matched:state='not_run'
  else:state='incomplete'
  groups=[]
  for base in bases:
   ids=[x for x in expected if x.startswith(base+'_p')];rows=[matched[x] for x in ids if x in matched];gp=sum(bool(x['passed']) for x in rows);gf=sum(not bool(x['passed']) for x in rows);groups.append({'scenario_id':base,'expected':len(ids),'passed':gp,'failed':gf,'not_run':len(ids)-len(rows),'state':'failed' if gf else 'passed' if gp==len(ids) else 'not_run' if not rows else 'incomplete'})
  failures=[x for x in matched.values() if not x['passed']]
  return {'schema':'dpo-scenario-maximum-results-v1','profile':'MAXIMUM','overall_state':state,'expected_total':len(expected),'passed':passed,'failed':failed,'not_run':not_run,'groups':groups,'failed_cases':failures[:100],'extra_result_count':len([x for x in found if x not in expected_set]),'pass_definition':'passed == expected_total and failed == 0; plan creation alone never counts as PASS'}
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
