"""🎯 CRITICAL → Менеджер skin-run'а: initialize/finalize + guard на мутабельность.
🚪 API: initialize(), finalize(), assert_mutable()
🚨 WARNING: после finalize() пакет read-only — assert_mutable() бросает.
"""
from __future__ import annotations
import hashlib,json,os,platform,sys,time
from pathlib import Path
from .serialization import atomic_json,sha256_file
class SkinRunManager:
 def __init__(self,root):self.root=Path(root)
 # 🏭 Инициализация mutable run'а
 def initialize(self,config,assets,atlas,calibration=None):
  if self.root.exists() and any(self.root.iterdir()):raise FileExistsError(f'run root not empty: {self.root}')
  for d in ('frozen_config','logs','failures','photo_results','stage2','chronology','reports','audit'): (self.root/d).mkdir(parents=True,exist_ok=True)
  asset_rows={str(p):{'sha256':sha256_file(p),'bytes':Path(p).stat().st_size} for p in map(Path,assets)}
  payload={'schema':'skin-run-manifest-v1','state':'initialized','created_unix':time.time(),'python':sys.version,'platform':platform.platform(),'config':config,'assets':asset_rows,'atlas':{'path':str(atlas),'sha256':sha256_file(atlas)},'calibration':({'path':str(calibration),'sha256':sha256_file(calibration)} if calibration else None),'paths':{'photo_results':'photo_results','stage2':'stage2','reports':'reports'}};payload['run_contract_sha256']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest();atomic_json(self.root/'frozen_config/config.json',config);atomic_json(self.root/'run_manifest.json',payload);return payload
 # 🔒 Финализация run'а (дальше read-only)
 def finalize(self):
  m=json.loads((self.root/'run_manifest.json').read_text());files={}
  for p in sorted(self.root.rglob('*')):
   if p.is_file() and p.name not in {'run_manifest.json','IMMUTABLE'}:files[str(p.relative_to(self.root))]={'sha256':sha256_file(p),'bytes':p.stat().st_size}
  m['state']='immutable_complete';m['finalized_unix']=time.time();m['files']=files;atomic_json(self.root/'run_manifest.json',m);(self.root/'IMMUTABLE').write_text(m['run_contract_sha256']+'\n');return m
 # 🚨 Guard: бросает если run уже финализирован
 def assert_mutable(self):
  if (self.root/'IMMUTABLE').exists():raise PermissionError('run is immutable; create a new versioned run root')
