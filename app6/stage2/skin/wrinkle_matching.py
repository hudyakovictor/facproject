import math,numpy as np
from app6.stage1.skin.surface_geometry import SurfaceGeometry
try:from scipy.optimize import linear_sum_assignment
except:linear_sum_assignment=None
def _poly(p,b):
 q=p[int(b['point_start']):int(b['point_start'])+int(b['point_count'])];return q,np.c_[q['sx'],q['sy'],q['sz']]
def _res(q,n=24):
 d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(q,axis=0),axis=1))];t=np.linspace(0,d[-1],n);return np.stack([np.interp(t,d,q[:,k]) for k in range(3)],1)
def match_wrinkle_packages(a,b,gate=.55):
 sa=a.json('wrinkles/summary.json');sb=b.json('wrinkles/summary.json');A=sa.get('branches',[]);B=sb.get('branches',[])
 if not A or not B:return {'status':'insufficient_evidence','matches':[]}
 with a.npz('wrinkles/classical.npz') as x,b.npz('wrinkles/classical.npz') as y,a.surface() as ga,b.surface() as gb:pa=x['points'];pb=y['points'];tri=ga['triangles'];geom=SurfaceGeometry((ga['surface_vertices']+gb['surface_vertices'])/2,tri,False)
 C=np.full((len(A),len(B)),1e6);parts={};cache={}
 for i,u in enumerate(A):
  qu,su=_poly(pa,u);mid=qu[len(qu)//2];sv=int(tri[int(mid['triangle_id']),int(np.argmax([mid['b0'],mid['b1'],mid['b2']]))]);cache[sv]=geom.distance(sv)
  for j,v in enumerate(B):
   if set(u.get('w14_membership',[])) and set(v.get('w14_membership',[])) and not set(u['w14_membership'])&set(v['w14_membership']):continue
   qv,sv3=_poly(pb,v);mj=qv[len(qv)//2];tv=int(tri[int(mj['triangle_id']),int(np.argmax([mj['b0'],mj['b1'],mj['b2']]))]);loc=float(cache[sv][tv]);q,r=_res(su),_res(sv3);length=abs(math.log(max(u['length_surface'],1e-8)/max(v['length_surface'],1e-8)));shape=min(np.linalg.norm(q-r,axis=1).mean(),np.linalg.norm(q-r[::-1],axis=1).mean());od=abs(float(u.get('orientation_tangent_rad_mod_pi',0))-float(v.get('orientation_tangent_rad_mod_pi',0)))%np.pi;orientation=min(od,np.pi-od)/(np.pi/2);C[i,j]=loc+.2*length+shape+.15*orientation;parts[i,j]={'geodesic_location':loc,'orientation_mod_pi':orientation,'length_log':length,'shape':float(shape)}
 ij=linear_sum_assignment(C) if linear_sum_assignment else (range(min(C.shape)),np.argmin(C,1));m=[{'branch_a':int(i),'branch_b':int(j),'cost':float(C[i,j]),'components':parts[i,j]} for i,j in zip(*ij) if C[i,j]<=gate];return {'status':'measured','implementation_status':'experimental_uncalibrated_cost','production_evidence_allowed':False,'matches':m,'match_fraction':len(m)/max(len(A),len(B)),'distance_semantics':'mesh graph geodesic + canonical surface shape','warning':'cost scale/gate require calibration and common-branch observability'}
