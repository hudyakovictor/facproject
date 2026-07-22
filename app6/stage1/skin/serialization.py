"""Atomic, checksum-addressed serialization; object arrays and pickle are forbidden.

🔄 CONVENTIONS v2 → сериализация skin-пакета; статус: ✅ VERIFIED
"""
from __future__ import annotations
import hashlib,json,os,tempfile
from pathlib import Path
from typing import Mapping
import numpy as np

# 📊 sha256 файла (контроль целостности)
# 💡 NOTE: автономная локальная реализация (осознанно; без делегирования в utils).
def sha256_file(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
class _SafeEncoder(json.JSONEncoder):
 # 🔄 JSON fallback-сериализатор (numpy→python)
 def default(self,o):
  if isinstance(o,np.integer):return int(o)
  if isinstance(o,np.floating):
   if np.isnan(o) or np.isinf(o):return None
   return float(o)
  if isinstance(o,np.ndarray):return o.tolist()
  return super().default(o)
# 📊 Детерминированный хэш структуры данных
def canonical_hash(payload)->str:return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False,cls=_SafeEncoder).encode()).hexdigest()
# 🎯 CRITICAL → атомарная запись json (tmp→rename)
def atomic_json(path,payload):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.',suffix='.tmp')
 try:
  with os.fdopen(fd,'w',encoding='utf8') as f:json.dump(payload,f,ensure_ascii=False,indent=2,allow_nan=False,cls=_SafeEncoder);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
# 🎯 CRITICAL → атомарная запись npz
def atomic_npz(path,**arrays):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 for k,v in arrays.items():
  a=np.asarray(v)
  if a.dtype.hasobject:raise TypeError(f'{k}: object dtype/pickle forbidden')
 fd,tmp=tempfile.mkstemp(dir=p.parent,prefix=p.name+'.',suffix='.npz');os.close(fd)
 try:np.savez_compressed(tmp,**arrays);os.replace(tmp,p)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
# 📤 Инвентаризация содержимого пакета
def inventory(root:Path)->dict:
 return {str(p.relative_to(root)):{'sha256':sha256_file(p),'bytes':p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file() and p.name not in {'manifest.json','SUCCESS'}}
# 🚨 SECURITY → отклонить npz с pickle-объектами
def validate_npz_no_pickle(path):
 with np.load(path,allow_pickle=False) as z:
  for k in z.files:
   if z[k].dtype.hasobject:raise TypeError(f'{path}:{k} object dtype')
 return True
