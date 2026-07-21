from __future__ import annotations
import cv2,numpy as np
from ..surface_geometry import SurfaceGeometry
try:from skimage.filters import frangi;from skimage.morphology import skeletonize
except Exception:frangi=skeletonize=None
def response_map(g,valid):
 r=[cv2.morphologyEx(g,cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k))) for k in (5,9,15)]
 if frangi is not None:
  try:r.append(np.asarray(frangi(g,sigmas=(1,2,3),black_ridges=True),np.float32))
  except:pass
 x=np.max(np.stack(r),0);x[~valid]=0;s=np.percentile(x[valid],99) if np.any(valid) else 0;return np.clip(x/(s+1e-8),0,1).astype(np.float32)
def _branch_paths(sk):
 try:
  from skan import Skeleton
  graph=Skeleton(sk.astype(np.uint8));all_paths=[np.asarray(graph.path_coordinates(i),int) for i in range(graph.n_paths)];return [p for p in all_paths if len(p)>=6],'skan',sum(len(p)<6 for p in all_paths)
 except Exception:
  # Connected components are not graph branches and cannot preserve path order.
  n,_=cv2.connectedComponents(sk.astype(np.uint8),8);return [],'unavailable_without_skan',max(0,n-1)
def detect(bgr,w,tid,bary,triangles,vertices,w14):
 g=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY).astype(np.float32)/255.;valid=w>.15;r=response_map(g,valid);thr=float(np.percentile(r[valid],88)) if valid.sum()>50 else 1.;low=max(.10,float(np.percentile(r[valid],75))) if valid.sum()>50 else 1.
 try:
  from skimage.filters import apply_hysteresis_threshold
  binary=apply_hysteresis_threshold(r,low,max(.15,thr))&valid
 except Exception:binary=(r>=max(.15,thr))&valid
 sk=skeletonize(binary) if skeletonize else binary;degree=cv2.filter2D(sk.astype(np.uint8),cv2.CV_16S,np.ones((3,3),np.uint8))-sk.astype(np.int16);paths,graph_backend,pruned_count=_branch_paths(sk);tri=np.asarray(triangles);v=np.asarray(vertices);T,B,_=SurfaceGeometry(v,tri,False).tangent_frames();points=[];branches=[]
 for pix in paths:
  if len(pix)<6:continue
  # Skan path_coordinates are already graph-ordered; PCA sorting corrupts curves.
  surf=[];keep=[]
  for y,x in pix:
   fi=int(tid[y,x])
   if fi>=0:bc=np.asarray(bary[y,x],float);surf.append(bc@v[tri[fi]]);keep.append((int(y),int(x),fi,bc))
  if len(surf)<2:continue
  surf=np.asarray(surf);L=float(np.linalg.norm(np.diff(surf,axis=0),axis=1).sum());E=float(np.linalg.norm(surf[-1]-surf[0]));mid=keep[len(keep)//2];seed=int(tri[mid[2],int(np.argmax(mid[3]))]);vec=surf[-1]-surf[0];angle=float(np.mod(np.arctan2(np.dot(vec,B[seed]),np.dot(vec,T[seed])),np.pi));mem=[f'W{k+1:02d}' for k in range(14) if any(w14[k,y,x] for y,x,_,_ in keep)];branches.append({'branch_id':len(branches),'point_start':len(points),'point_count':len(keep),'length_surface':L,'endpoint_distance_surface':E,'tortuosity':L/max(E,1e-8),'orientation_tangent_rad_mod_pi':angle,'branch_type':f"degree_{int(degree[pix[0,0],pix[0,1]])}_{int(degree[pix[-1,0],pix[-1,1]])}",'mean_ridge_probability':float(np.mean([r[y,x] for y,x,_,_ in keep])),'w14_membership':mem})
  for pi,(pos,(y,x,fi,bc)) in enumerate(zip(surf,keep)):
   direction=surf[min(pi+1,len(surf)-1)]-surf[max(pi-1,0)];vertex=int(tri[fi,int(np.argmax(bc))]);tn=np.hypot(np.dot(direction,T[vertex]),np.dot(direction,B[vertex]));tt=float(np.dot(direction,T[vertex])/max(tn,1e-9));tb=float(np.dot(direction,B[vertex])/max(tn,1e-9));points.append((x,y,fi,*bc,*pos,tt,tb,r[y,x]))
 dt=np.dtype([('x','i4'),('y','i4'),('triangle_id','i4'),('b0','f4'),('b1','f4'),('b2','f4'),('sx','f4'),('sy','f4'),('sz','f4'),('tangent_t','f4'),('tangent_b','f4'),('ridge_probability','f4')]);return r,sk.astype(bool),np.array(points,dtype=dt),branches,{'backend':f'frangi+blackhat+skeletonize+{graph_backend}','threshold':thr,'spur_pruning':{'min_path_pixels':6,'removed_path_count':int(pruned_count)},'valid_pixels':int(valid.sum())}
