import json,math
from pathlib import Path
def evaluate_material(evidence,calibration_artifact=None):
 if calibration_artifact is None:return {**evidence,'probability':None,'status':'uncalibrated','reason':'material calibration absent'}
 c=json.loads(Path(calibration_artifact).read_text())
 if not c.get('frozen') or c.get('task')!='material_consistency':return {**evidence,'probability':None,'status':'out_of_validated_domain','reason':'not a frozen material artifact'}
 features=[]
 for name in c.get('feature_order',[]):
  family,key=name.split('.',1);v=evidence.get('families',{}).get(family,{}).get(key)
  if v is None:return {**evidence,'probability':None,'status':'insufficient_evidence','reason':f'missing {name}'}
  features.append(float(v))
 z=c.get('intercept',0)+sum(w*x for w,x in zip(c['weights'],features));p=1/(1+math.exp(-z));return {**evidence,'probability':p,'status':'calibrated_estimate','calibration_sha256':c['artifact_sha256'],'warning':'material consistency estimate, not identity proof'}
