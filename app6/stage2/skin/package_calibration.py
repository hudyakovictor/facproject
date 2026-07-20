import csv,json,hashlib
from pathlib import Path
import numpy as np
from .loader import SkinPackage
from app6.stage1.skin.serialization import atomic_json
def _records(root,metadata):
 
 with open(metadata,encoding='utf8') as fh:rows=list(csv.DictReader(fh))
 out=[]
 for r in rows:
  d=Path(root)/r['photo_id'];p=SkinPackage(d/'skin')
  with p.npz('features/texture.npz') as z:
   for i,zone in enumerate(z['zone_id']):
    for j,name in enumerate(z['columns']):
     v=float(z['values'][i,j])
     if np.isfinite(v) and z['state'][i]=='usable':out.append({**r,'key':'|'.join((r['yaw_bin'],str(zone),str(name))),'value':v})
 return rows,out
def build_package_calibration(stage1_root,metadata_csv,output,target_false_anomaly=.01,min_heldout_checks=30):
 rows,obs=_records(stage1_root,metadata_csv);train=[x for x in obs if x['split'] in {'development','calibration'}];test=[x for x in obs if x['split']=='test'];by={}
 for x in train:by.setdefault(x['key'],[]).append(x['value'])
 models={}
 for k,x in by.items():
  if len(x)>=8:a=np.asarray(x);m=np.median(a);models[k]={'n':len(a),'median':float(m),'mad':float(1.4826*np.median(abs(a-m))+1e-9),'p01':float(np.quantile(a,.01)),'p99':float(np.quantile(a,.99))}
 flags=[]
 for x in test:
  if x['key'] in models:flags.append(abs(x['value']-models[x['key']]['median'])/models[x['key']]['mad']>3.5)
 rate=float(np.mean(flags)) if flags else None;passed=bool(models and len(flags)>=min_heldout_checks and rate<=target_false_anomaly);artifact={'schema':'skin-package-calibration-v1','task':'same_person_skin_repeatability','frozen':passed,'target_false_anomaly':target_false_anomaly,'minimum_heldout_checks':min_heldout_checks,'heldout_false_anomaly_rate':rate,'heldout_checks':len(flags),'models':models,'metadata_sha256':hashlib.sha256(Path(metadata_csv).read_bytes()).hexdigest()};artifact['artifact_sha256']=hashlib.sha256(json.dumps(artifact,sort_keys=True).encode()).hexdigest();atomic_json(output,artifact);return artifact
