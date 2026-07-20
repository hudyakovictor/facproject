from __future__ import annotations
import cv2,numpy as np
def detect(bgr,w,tid,bary,triangles,vertices,max_candidates=500):
 L=cv2.cvtColor(bgr,cv2.COLOR_BGR2LAB)[...,0].astype(np.float32)/255.;r=abs(L-cv2.GaussianBlur(L,(0,0),5));valid=w>.2;thr=float(np.percentile(r[valid],98.5)) if valid.sum()>100 else 1.;n,lab,stats,cents=cv2.connectedComponentsWithStats(((r>=max(thr,.03))&valid).astype(np.uint8),8);tri=np.asarray(triangles);v=np.asarray(vertices);rows=[]
 for i in sorted(range(1,n),key=lambda j:float(r[lab==j].max()),reverse=True)[:max_candidates]:
  area=int(stats[i,cv2.CC_STAT_AREA]);x,y=map(int,np.round(cents[i]));x=np.clip(x,0,r.shape[1]-1);y=np.clip(y,0,r.shape[0]-1);fi=int(tid[y,x])
  if area<3 or area>500 or fi<0:continue
  bc=np.asarray(bary[y,x],float);pos=bc@v[tri[fi]];ys,xs=np.where(lab==i);ev=np.linalg.eigvalsh(np.cov(np.c_[xs,ys].T)) if len(xs)>2 else [1,1];ecc=float(np.sqrt(max(0,1-ev[0]/max(ev[-1],1e-8))));ring=cv2.dilate((lab==i).astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)&(lab!=i)&valid;contrast=float(L[lab==i].mean()-L[ring].mean()) if ring.any() else np.nan;rows.append((len(rows),x,y,fi,*bc,*pos,area,ecc,contrast,float(r[lab==i].max())))
 dt=np.dtype([('candidate_id','i4'),('x','i4'),('y','i4'),('triangle_id','i4'),('b0','f4'),('b1','f4'),('b2','f4'),('sx','f4'),('sy','f4'),('sz','f4'),('area_px','i4'),('eccentricity','f4'),('relative_luminance_contrast','f4'),('response_max','f4')]);return r,np.array(rows,dtype=dt),{'threshold':thr,'candidate_count':len(rows),'semantics':'independent candidates only'}
