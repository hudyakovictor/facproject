from __future__ import annotations
import cv2,numpy as np
def degradation_family(image,target_blur,target_noise,target_scale,jpeg_qualities=(95,80,60),seed=0):
 """Controlled variants only; never replaces raw evidence."""
 rng=np.random.default_rng(seed);x=np.asarray(image);out=[]
 for sigma in sorted(set([0.,max(0.,float(target_blur))])):
  y=cv2.GaussianBlur(x,(0,0),sigma) if sigma else x.copy()
  if target_scale<.999:
   h,w=y.shape[:2];small=cv2.resize(y,(max(1,int(w*target_scale)),max(1,int(h*target_scale))),interpolation=cv2.INTER_AREA);y=cv2.resize(small,(w,h),interpolation=cv2.INTER_LINEAR)
  if target_noise>0:y=np.clip(y.astype(float)+rng.normal(0,target_noise,y.shape),0,255).astype(np.uint8)
  for q in jpeg_qualities:
   ok,b=cv2.imencode('.jpg',y,[cv2.IMWRITE_JPEG_QUALITY,int(q)])
   if ok:out.append({'image':cv2.imdecode(b,cv2.IMREAD_COLOR),'params':{'blur_sigma':sigma,'noise_sigma':target_noise,'scale':target_scale,'jpeg_quality':q}})
 return out

def compare_sensitivity_packages(a,b):
 import numpy as np
 A=a.json('sensitivity/degradation.json')['rows'];B=b.json('sensitivity/degradation.json')['rows'];av={x['variant']:x.get('value') for x in A if x.get('status')=='measured'};bv={x['variant']:x.get('value') for x in B if x.get('status')=='measured'}
 raw_a=av.get('raw');raw_b=bv.get('raw')
 if raw_a is None or raw_b is None:return {'status':'insufficient_evidence'}
 da=[abs(v-raw_b) for k,v in av.items() if k!='raw' and v is not None];db=[abs(raw_a-v) for k,v in bv.items() if k!='raw' and v is not None];raw=abs(raw_a-raw_b);best=min(da+db) if da or db else raw;return {'status':'measured','implementation_status':'experimental_focus_only','production_evidence_allowed':False,'raw_focus_difference':raw,'best_degradation_matched_difference':best,'degradation_explained_fraction':(None if raw<1e-9 else float(np.clip(1-best/raw,0,1))),'warning':'focus-only sensitivity is not full feature-family quality matching'}
