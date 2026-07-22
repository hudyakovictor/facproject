"""🏭 FACTORY → Сэмплирование связных патчей внутри зон атласа.
🚪 API: connected_components(), sample_zone_patches()
💡 NOTE: связность — 8-neighbour на UV-маске зоны.
"""
from __future__ import annotations
import numpy as np
from ..status_logger import log_status
# 🔢 Связные компоненты UV-маски (8-neighbour)
def connected_components(mask):
 import cv2
 n,lab=cv2.connectedComponents(np.asarray(mask,np.uint8),connectivity=8);return [lab==i for i in range(1,n)]
def sample_zone_patches(zone_map,zone_id,valid_weight,min_pixels=64,max_patches=16):
 log_status("sample_zone_patches", "complete")
 mask=(np.asarray(zone_map)==zone_id)&(np.asarray(valid_weight)>0)
 comps=connected_components(mask);out=[]
 for i,c in enumerate(sorted(comps,key=lambda q:int(q.sum()),reverse=True)[:max_patches]):
  yy,xx=np.where(c);w=np.asarray(valid_weight)[c]
  if len(xx)<min_pixels:continue
  out.append({'patch_id':f'z{zone_id:02d}-c{i:02d}','bbox_xyxy':[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)],'pixel_count':int(len(xx)),'effective_support':float(w.sum()),'valid_fraction':float(np.mean(w>0))})
 return out
