"""📊 METRIC → Попарное сопоставление локальных skin-дескрипторов.
🚪 API: match_local_features()
🔗 DEPENDS ON: stage1.skin.local_features.detector
"""
import numpy as np
from app6.stage1.skin.surface_geometry import SurfaceGeometry
try:from scipy.optimize import linear_sum_assignment
except:linear_sum_assignment=None
# 📊 Попарное сопоставление локальных признаков
def match_local_features(a,b,gate=.08):
 with a.npz('features/local_candidates.npz') as x,b.npz('features/local_candidates.npz') as y,a.surface() as sa,b.surface() as sb:A=x['candidates'];B=y['candidates'];tri=sa['triangles'];geom=SurfaceGeometry((sa['surface_vertices']+sb['surface_vertices'])/2,tri,False)
 if not len(A) or not len(B):return {'status':'insufficient_evidence','matches':[]}
 p=np.c_[A['sx'],A['sy'],A['sz']];q=np.c_[B['sx'],B['sy'],B['sz']];E=np.linalg.norm(p[:,None]-q[None],axis=2);D=np.full(E.shape,np.inf)
 for i in range(len(A)):
  source=int(tri[int(A[i]['triangle_id']),int(np.argmax([A[i]['b0'],A[i]['b1'],A[i]['b2']]))]);dist=geom.distance(source)
  for j in np.argsort(E[i])[:min(5,len(B))]:target=int(tri[int(B[j]['triangle_id']),int(np.argmax([B[j]['b0'],B[j]['b1'],B[j]['b2']]))]);D[i,j]=dist[target]
 C=np.where(np.isfinite(D),D,1e6);ij=linear_sum_assignment(C) if linear_sum_assignment else (range(min(D.shape)),np.argmin(D,1));m=[{'a':int(i),'b':int(j),'geodesic_distance':float(D[i,j])} for i,j in zip(*ij) if D[i,j]<=gate];return {'status':'measured','implementation_status':'experimental_location_only','production_evidence_allowed':False,'matches':m,'match_fraction':len(m)/max(len(A),len(B)),'distance_semantics':'mesh graph geodesic','warning':'descriptor, persistence and quality calibration are not complete'}
