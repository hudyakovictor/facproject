from __future__ import annotations
import numpy as np
from .surface_geometry import SurfaceGeometry
def build_patch_registry(vertices,triangles,uv,atlas):
 v=np.asarray(vertices);f=np.asarray(triangles);uv=np.asarray(uv);g=SurfaceGeometry(v,f);T,B,N=g.tangent_frames();rows=[];cent=[]
 for i,code in enumerate(atlas.S_codes):
  faces=np.flatnonzero(atlas.S==i);verts=np.unique(f[faces]);c=uv[verts].mean(0);seed=int(verts[np.argmin(((uv[verts]-c)**2).sum(1))]);d=g.distance(seed)[verts];cent.append(c);rows.append({'patch_id':code,'seed_vertex':seed,'triangle_count':len(faces),'geodesic_radius_p95':float(np.percentile(d[np.isfinite(d)],95)),'T':T[seed].tolist(),'B':B[seed].tolist(),'N':N[seed].tolist()})
 cent=np.asarray(cent)
 for i,r in enumerate(rows):j=int(np.argmin(((cent-[1-cent[i,0],cent[i,1]])**2).sum(1)));r['mirror_partner']=atlas.S_codes[j]
 return {'schema':'skin-canonical-patches-v1','backend':g.metadata(),'patches':rows}
