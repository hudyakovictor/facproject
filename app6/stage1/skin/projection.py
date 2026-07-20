"""Full-resolution CPU triangle rasterizer with z-buffer and barycentric provenance."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
BACKGROUND_TRIANGLE=-1
@dataclass
class RasterResult:
 triangle_id:np.ndarray;barycentric:np.ndarray;depth:np.ndarray;normal:np.ndarray;incidence:np.ndarray;visibility:np.ndarray;projection_confidence:np.ndarray;source_xy:np.ndarray

def rasterize_surface(vertices_xy,vertices_z,normals,triangles,image_shape,vertex_visibility=None,near='min')->RasterResult:
 xy=np.asarray(vertices_xy,np.float32)[:,:2];z=np.asarray(vertices_z,np.float32).reshape(-1);n=np.asarray(normals,np.float32);f=np.asarray(triangles,np.int64);H,W=map(int,image_shape[:2])
 if xy.shape!=(len(z),2) or n.shape!=(len(z),3):raise ValueError('vertex array shape mismatch')
 tid=np.full((H,W),BACKGROUND_TRIANGLE,np.int32);depth=np.full((H,W),np.inf if near=='min' else -np.inf,np.float32);bar=np.zeros((H,W,3),np.float32);normal=np.zeros((H,W,3),np.float32)
 vv=np.ones(len(z),np.float32) if vertex_visibility is None else np.asarray(vertex_visibility,np.float32)
 for fi,t in enumerate(f):
  p=xy[t];xmin=max(0,int(np.floor(p[:,0].min())));xmax=min(W-1,int(np.ceil(p[:,0].max())));ymin=max(0,int(np.floor(p[:,1].min())));ymax=min(H-1,int(np.ceil(p[:,1].max())))
  if xmax<xmin or ymax<ymin:continue
  den=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
  if abs(float(den))<1e-10:continue
  yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1];px=xx+.5;py=yy+.5
  b0=((p[1,1]-p[2,1])*(px-p[2,0])+(p[2,0]-p[1,0])*(py-p[2,1]))/den;b1=((p[2,1]-p[0,1])*(px-p[2,0])+(p[0,0]-p[2,0])*(py-p[2,1]))/den;b2=1-b0-b1;inside=(b0>=-1e-5)&(b1>=-1e-5)&(b2>=-1e-5)
  if not inside.any():continue
  dz=b0*z[t[0]]+b1*z[t[1]]+b2*z[t[2]];old=depth[ymin:ymax+1,xmin:xmax+1];take=inside&((dz<old) if near=='min' else (dz>old))
  if not take.any():continue
  old[take]=dz[take];T=tid[ymin:ymax+1,xmin:xmax+1];T[take]=fi;B=bar[ymin:ymax+1,xmin:xmax+1];B[take]=np.stack((b0,b1,b2),-1)[take];N=normal[ymin:ymax+1,xmin:xmax+1];ni=b0[...,None]*n[t[0]]+b1[...,None]*n[t[1]]+b2[...,None]*n[t[2]];N[take]=ni[take]
 bg=tid<0;depth[bg]=np.nan;norm=np.linalg.norm(normal,axis=2,keepdims=True);normal=np.divide(normal,norm,out=np.zeros_like(normal),where=norm>1e-8)
 signed=normal[...,2];pol=-1 if np.nanmedian(signed[~bg])<0 else 1;inc=np.clip(pol*signed,0,1).astype(np.float32);inc[bg]=0
 vis=np.zeros((H,W),np.float32);valid=~bg;ft=f[np.clip(tid,0,len(f)-1)];vis[valid]=np.min(vv[ft[valid]],axis=1)
 edge=np.clip(3*np.min(bar,axis=2),0,1);conf=(vis*np.sqrt(inc)*edge).astype(np.float32);conf[bg]=0
 yy,xx=np.mgrid[:H,:W];source=np.stack((xx,yy),axis=2).astype(np.int32);source[bg]=-1
 return RasterResult(tid,bar,depth,normal,inc,vis,conf,source)

def project_atlas(raster,atlas,skin_segmentation=None):
 tid=raster.triangle_id;valid=tid>=0;safe=np.clip(tid,0,len(atlas.A)-1);seg=np.ones(tid.shape,bool) if skin_segmentation is None else np.asarray(skin_segmentation,bool)
 domain=valid&seg&atlas.skin[safe];A=np.full(tid.shape,-1,np.int8);S=np.full(tid.shape,-1,np.int8);A[domain]=atlas.A[safe[domain]];S[domain]=atlas.S[safe[domain]];W=np.zeros((14,*tid.shape),bool)
 for k in range(14):W[k]=domain&atlas.W[k,safe]
 bd=np.zeros(tid.shape,np.uint8);bd[domain]=atlas.boundary[safe[domain]]
 return {'zone_id_a20':A,'zone_id_s40':S,'wrinkle_bits_w14':np.packbits(W,axis=0,bitorder='little'),'wrinkle_membership_w14':W,'boundary_distance':bd,'domain_mask':domain}
