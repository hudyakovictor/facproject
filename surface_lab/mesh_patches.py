from __future__ import annotations
import numpy as np
from .config import PATCH_TARGETS


def _edge_graph(vertices: np.ndarray, faces: np.ndarray):
    from scipy.sparse import coo_matrix
    edges=np.vstack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]])
    edges=np.vstack([edges,edges[:,::-1]])
    w=np.linalg.norm(vertices[edges[:,0]]-vertices[edges[:,1]],axis=1)
    return coo_matrix((w,(edges[:,0],edges[:,1])),shape=(len(vertices),len(vertices))).tocsr()


def geodesic_distance(vertices: np.ndarray, faces: np.ndarray, anchor: int) -> tuple[np.ndarray,str]:
    try:
        import potpourri3d as pp3d
        solver=pp3d.MeshHeatMethodDistanceSolver(vertices.astype(np.float64),faces.astype(np.int32))
        return np.asarray(solver.compute_distance(int(anchor)),np.float32),"potpourri3d-heat"
    except Exception:
        try:
            from scipy.sparse.csgraph import dijkstra
            return np.asarray(dijkstra(_edge_graph(vertices,faces),indices=int(anchor)),np.float32),"scipy-edge-dijkstra"
        except Exception:
            import heapq
            adjacency=[{} for _ in range(len(vertices))]
            for a,b,c in np.asarray(faces,np.int64):
                for i,j in ((a,b),(b,c),(c,a)):
                    w=float(np.linalg.norm(vertices[i]-vertices[j]))
                    adjacency[i][j]=min(w,adjacency[i].get(j,float("inf")))
                    adjacency[j][i]=min(w,adjacency[j].get(i,float("inf")))
            dist=np.full(len(vertices),np.inf,np.float64); dist[int(anchor)]=0; heap=[(0.0,int(anchor))]
            while heap:
                d,i=heapq.heappop(heap)
                if d!=dist[i]: continue
                for j,w in adjacency[i].items():
                    nd=d+w
                    if nd<dist[j]: dist[j]=nd; heapq.heappush(heap,(nd,j))
            return dist.astype(np.float32),"python-edge-dijkstra-fallback"


def build_vertex_patches(vertices: np.ndarray, faces: np.ndarray, radius: float) -> tuple[dict[str,np.ndarray],dict]:
    v=np.asarray(vertices,np.float32); f=np.asarray(faces,np.int64)
    patches={}; meta={}
    for name,target in PATCH_TARGETS.items():
        target=np.asarray(target,np.float32)
        anchor=int(np.argmin(np.linalg.norm(v-target,axis=1)))
        dist,backend=geodesic_distance(v,f,anchor)
        mask=dist<=float(radius)
        patches[name]=mask
        meta[name]={"anchor_vertex":anchor,"anchor_position":v[anchor].tolist(),"radius":float(radius),"distance_backend":backend,"vertex_count":int(mask.sum())}
    return patches,meta


def vertex_patch_to_uv(vertex_mask: np.ndarray, faces: np.ndarray, triangle_id: np.ndarray) -> np.ndarray:
    f=np.asarray(faces,np.int64); tid=np.asarray(triangle_id,np.int64)
    face_ok=np.count_nonzero(vertex_mask[f],axis=1)>=2
    out=np.zeros(tid.shape,bool); valid=(tid>=0)&(tid<len(face_ok)); out[valid]=face_ok[tid[valid]]
    return out


def uv_mask_to_image(uv_mask: np.ndarray, source_x: np.ndarray, source_y: np.ndarray,
                     observed: np.ndarray, image_shape: tuple[int,int]) -> np.ndarray:
    import cv2
    h,w=image_shape; use=uv_mask&observed&(source_x>=0)&(source_y>=0)
    x=np.rint(source_x[use]).astype(np.int32); y=np.rint(source_y[use]).astype(np.int32)
    good=(x>=0)&(x<w)&(y>=0)&(y<h); out=np.zeros((h,w),np.uint8); out[y[good],x[good]]=255
    out=cv2.morphologyEx(out,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8),iterations=2)
    out=cv2.dilate(out,np.ones((3,3),np.uint8),iterations=1)
    return out.astype(bool)
