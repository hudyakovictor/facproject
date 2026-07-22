"""🎯 CRITICAL → Загрузчик skin-пакета: npz/json/атлас/surface/quality в один объект.
🚪 API: npz(), json(), atlas(), surface(), quality()
🚨 WARNING: бросает на нефинализированном manifest (см. stage1.skin.manifest).
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from app6.stage1.skin.contracts import SCHEMAS,require_schema
from app6.stage1.skin.serialization import sha256_file
class SkinPackage:
 def __init__(self,root):
  self.root=Path(root);self.manifest=json.loads((self.root/'manifest.json').read_text());require_schema(self.manifest,SCHEMAS['manifest'])
  if not (self.root/'SUCCESS').is_file():raise ValueError('package not successful/frozen')
  for rel,meta in self.manifest['products'].items():
   p=self.root/rel
   if not p.is_file() or sha256_file(p)!=meta['sha256']:raise ValueError(f'checksum mismatch: {rel}')
  sm=self.manifest.get('source_mask') or {};mask=(self.root/sm.get('path','')).resolve()
  if not mask.is_file() or sha256_file(mask)!=sm.get('sha256') or sm.get('array')!='mask_original':raise ValueError('source face_mask provenance unavailable/mismatched')
 # 🔄 Доступ к npz пакета
 def npz(self,name):return np.load(self.root/name,allow_pickle=False)
 # 🔄 Доступ к json-полям пакета
 def json(self,name):return json.loads((self.root/name).read_text())
 # 🔄 Атлас пакета
 def atlas(self):return self.npz('atlas_projection.npz')
 # 🔄 Surface-геометрия пакета
 def surface(self):return self.npz('surface_observations.npz')
 # 🔄 Quality-слои пакета
 def quality(self):return self.json('quality.json')
