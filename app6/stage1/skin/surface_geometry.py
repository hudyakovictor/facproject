"""Mesh-native distances and tangent frames with explicit backend identity.

📊 CONVENTIONS v2 → кривизны/нормали поверхности; статус: 🔬 EXPERIMENTAL
"""
from __future__ import annotations
import heapq,hashlib
import numpy as np
from ..status_logger import log_status, log_blocker, log_warning
class SurfaceGeometry:
 def __init__(self,vertices,triangles,prefer_potpourri=True):
  self.v=np.asarray(vertices,np.float64);self.f=np.asarray(triangles,np.int64);self.backend='heap_graph_dijkstra_v1';self._solver=None;self._csr=None
  if prefer_potpourri:
   try:
    import potpourri3d as pp3d;self._solver=pp3d.MeshHeatMethodDistanceSolver(self.v,self.f);self.backend=f'potpourri3d_heat:{getattr(pp3d,"__version__","unknown")}'
   except Exception:pass
  self._adj=None
 # 🔢 Матрица смежности треугольной сетки
 @property
 def adjacency(self):
  if self._adj is None:
   d=[{} for _ in self.v]
   for t in self.f:
    for a,b in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0])):
     w=float(np.linalg.norm(self.v[a]-self.v[b]));d[a][int(b)]=min(d[a].get(int(b),np.inf),w);d[b][int(a)]=min(d[b].get(int(a),np.inf),w)
   self._adj=[list(q.items()) for q in d]
  return self._adj
 # 🔢 Геодезическое/евклидово расстояние по поверхности
 def distance(self,source):
  if self._solver is not None:return np.asarray(self._solver.compute_distance(int(source)),np.float64)
  try:
   from scipy.sparse import csr_matrix
   from scipy.sparse.csgraph import dijkstra
   if self._csr is None:
    rows=[];cols=[];data=[]
    for i,nb in enumerate(self.adjacency):
     for j,w in nb:rows.append(i);cols.append(j);data.append(w)
    self._csr=csr_matrix((data,(rows,cols)),shape=(len(self.v),len(self.v)));self.backend='scipy_sparse_dijkstra_v1'
   return np.asarray(dijkstra(self._csr,directed=False,indices=int(source)),np.float64)
  except Exception:pass
  d=np.full(len(self.v),np.inf);d[int(source)]=0.;h=[(0.,int(source))]
  while h:
   x,i=heapq.heappop(h)
   if x!=d[i]:continue
   for j,w in self.adjacency[i]:
    if x+w<d[j]:d[j]=x+w;heapq.heappush(h,(x+w,j))
  return d
 # 🔢 Нормали вершин (усреднение граней)
 def vertex_normals(self):
  n=np.zeros_like(self.v);fn=np.cross(self.v[self.f[:,1]]-self.v[self.f[:,0]],self.v[self.f[:,2]]-self.v[self.f[:,0]])
  for k in range(3):np.add.at(n,self.f[:,k],fn)
  return n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)
 # 🔢 Касательные базисы для transport
 def tangent_frames(self):
  N=self.vertex_normals();axis=np.tile([0.,1.,0.],(len(N),1));bad=np.abs((axis*N).sum(1))>.95;axis[bad]=[1,0,0];T=axis-(axis*N).sum(1,keepdims=True)*N;T/=np.maximum(np.linalg.norm(T,axis=1,keepdims=True),1e-12);B=np.cross(N,T);return T.astype(np.float32),B.astype(np.float32),N.astype(np.float32)
 # 🔬 EXPERIMENTAL → fallback-транспорт касательного вектора (approx)
 def transport_local(self,source,target,vector_tb):
  """Fallback tangent-vector transport; explicit approximate backend."""
  T,B,N=self.tangent_frames();g=float(vector_tb[0])*T[int(source)]+float(vector_tb[1])*B[int(source)];q=np.array([np.dot(g,T[int(target)]),np.dot(g,B[int(target)])],np.float32);return q
 # 📊 Диагностическая ошибка round-trip транспорта
 def transport_roundtrip_error(self,source,target,vector_tb=(1.,0.)):
  a=np.asarray(vector_tb,np.float32);b=self.transport_local(source,target,a);c=self.transport_local(target,source,b);return float(np.linalg.norm(c-a))
 # 📤 Метаданные backend'а геометрии
 def metadata(self):return {'backend':self.backend,'transport_backend':'tangent_projection_fallback_v1','units':'canonical_surface_units_not_mm','topology_sha256':hashlib.sha256(self.f.astype('<i4').tobytes()).hexdigest()}
