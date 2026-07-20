from __future__ import annotations
import numpy as np
from app6.stage1.skin.contracts import PairStatus,SCHEMAS
from .applicability import common_surface
from .texture_comparison import compare_texture
from .wrinkle_matching import match_wrinkle_packages
from .local_feature_matching import match_local_features
from .quality_matching import compare_sensitivity_packages
def compare_packages(a,b,min_common=.35):
 with a.surface() as sa,a.atlas() as aa,b.surface() as sb,b.atlas() as ab:
  zones=[]
  for z in range(20):
   c=common_surface(sa,sb,aa,ab,'A',z);status=PairStatus.INSUFFICIENT_EVIDENCE.value if c['coverage_sym']<min_common else PairStatus.PARTIAL_MATCH.value;zones.append({'zone':f'A{z+1:02d}','status':status,**{k:v for k,v in c.items() if k!='triangle_ids'},'common_triangle_ids':c['triangle_ids'].tolist()})
 out={'schema':SCHEMAS['pair'],'implementation_status':'experimental_foundation','production_evidence_allowed':False,'photo_a':a.manifest['photo_id'],'photo_b':b.manifest['photo_id'],'zones':zones,'rule':'no common observed surface => insufficient evidence; never zero difference'}
 for key,fn in [('quality_matching',compare_sensitivity_packages),('texture',compare_texture),('wrinkles',match_wrinkle_packages),('local_features',match_local_features)]:
  try:out[key]=fn(a,b)
  except Exception as e:out[key]={'status':'insufficient_evidence','error':str(e)}
 return out
