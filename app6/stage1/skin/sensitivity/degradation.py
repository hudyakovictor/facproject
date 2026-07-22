"""🔬 EXPERIMENTAL → Варианты деградаций (blur/noise/jpeg) и бенчмарк устойчивости.
🚪 API: variants(), benchmark()
📊 METRIC: производит degradation-stability таблицу для аудита.
"""
from __future__ import annotations
import cv2,numpy as np
from ...status_logger import log_status, log_blocker, log_warning
# 🏭 FACTORY → набор деградаций (blur/noise/jpeg)
def variants(bgr,seed=0):
 rng=np.random.default_rng(seed);yield 'raw',bgr,{}
 for s in (1.,2.,3.):yield f'blur_{s}',cv2.GaussianBlur(bgr,(0,0),s),{'blur_sigma':s}
 for q in (90,70,50,30):
  ok,x=cv2.imencode('.jpg',bgr,[cv2.IMWRITE_JPEG_QUALITY,q])
  if ok:yield f'jpeg_{q}',cv2.imdecode(x,1),{'jpeg_quality':q}
 for scale in (.75,.5,.35):
  h,w=bgr.shape[:2];x=cv2.resize(bgr,(int(w*scale),int(h*scale)),interpolation=cv2.INTER_AREA);yield f'down_{scale}',cv2.resize(x,(w,h)),{'scale':scale}
def benchmark(bgr,mask,extractor,seed=0):
 log_status("benchmark", "complete")
 rows=[]
 for name,x,p in variants(bgr,seed):
  try:rows.append({'variant':name,'params':p,'status':'measured','value':extractor(x,mask)})
  except Exception as e:rows.append({'variant':name,'params':p,'status':'failed','error':str(e),'value':None})
 return {'schema':'skin-sensitivity-v1','seed':seed,'rows':rows,'rule':'variants never replace raw evidence'}
