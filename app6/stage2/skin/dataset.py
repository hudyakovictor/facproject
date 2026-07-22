"""🎯 CRITICAL → Dataset-gate: валидация полноты skin-датасета перед анализом.
🚪 API: validate_skin_dataset()
🚨 WARNING: неполный датасет = отказ запуска stage2 skin (by design).
"""
import csv,hashlib
from pathlib import Path
REQUIRED=('photo_id','relative_path','input_sha256','capture_event_id','date_start','source_group','expression_bin','yaw_bin','duplicate_cluster','split')
# 🚨 Dataset-gate: неполный датасет = отказ
def validate_skin_dataset(root,csv_path,min_photos=180):

 with open(csv_path,encoding='utf8') as fh:rows=list(csv.DictReader(fh))
 errors=[];clusters={};events={}
 if rows and set(REQUIRED)-set(rows[0]):errors.append('missing columns: '+str(sorted(set(REQUIRED)-set(rows[0]))))
 for i,r in enumerate(rows,2):
  p=Path(root)/r.get('relative_path','')
  if not p.is_file():errors.append(f'row {i} missing');continue
  h=hashlib.sha256(p.read_bytes()).hexdigest()
  if h!=r.get('input_sha256'):errors.append(f'row {i} SHA mismatch')
  clusters.setdefault(r.get('duplicate_cluster') or h,set()).add(r.get('split'));events.setdefault(r.get('capture_event_id'),set()).add(r.get('split'))
 for k,v in {**clusters,**events}.items():
  if k and len(v)>1:errors.append(f'group leakage {k}: {sorted(v)}')
 return {'schema':'skin-dataset-validation-v1','ok':not errors,'photo_count':len(rows),'errors':errors,'warnings':[f'below planned count {min_photos}'] if len(rows)<min_photos else [],'metadata_sha256':hashlib.sha256(Path(csv_path).read_bytes()).hexdigest()}
