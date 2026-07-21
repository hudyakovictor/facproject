"""Deterministic native-pixel robust macro texture baseline."""
from __future__ import annotations
import cv2,numpy as np
from ..contracts import EvidenceState
def _weighted_quantile(x, w, q):
    o = np.argsort(x)
    x = x[o]
    w = w[o]
    s = w.sum()
    if s <= 0:
        return np.nan
    idx = min(int(np.searchsorted(np.cumsum(w), q * s, side='left')), x.size - 1)
    return float(x[idx])
def extract_basic(bgr,weight,A,S,min_support=50.):
 gray=cv2.cvtColor(np.asarray(bgr),cv2.COLOR_BGR2GRAY).astype(np.float32)/255.;records=[];arrays=[]
 for level,zmap,count,prefix in [('A20',A,20,'A'),('S40',S,40,'S')]:
  for i in range(count):
   mask=zmap==i;x=gray[mask];w=np.asarray(weight,np.float32)[mask];support=float(w.sum());state=EvidenceState.USABLE.value if support>=min_support else EvidenceState.NOT_MEASURABLE.value
   if state==EvidenceState.USABLE.value:
    med=_weighted_quantile(x,w,.5);p25=_weighted_quantile(x,w,.25);p75=_weighted_quantile(x,w,.75);mad=_weighted_quantile(np.abs(x-med),w,.5)
   else:med=mad=p25=p75=np.nan
   records.append({'zone_level':level,'zone_id':f'{prefix}{i+1:02d}','state':state,'effective_support':support,'luminance_median':med,'luminance_mad':mad,'luminance_iqr':p75-p25 if np.isfinite(p25) else np.nan})
 return records
