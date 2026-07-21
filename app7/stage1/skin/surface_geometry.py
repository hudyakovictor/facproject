"""Mesh-native distances and tangent frames."""

from __future__ import annotations

import heapq

import numpy as np


class SurfaceGeometry:
    """Compute geodesic distances and tangent frames on a triangle mesh."""

    def __init__(self, vertices: np.ndarray, triangles: np.ndarray, prefer_potpourri: bool = True):
        self.v = np.asarray(vertices, np.float64)
        self.f = np.asarray(triangles, np.int64)
        self.backend = "heap_graph_dijkstra_v1"
        self._solver = None
        self._csr = None
        if prefer_potpourri:
            try:
                import potpourri3d as pp3d
                self._solver = pp3d.MeshHeatMethodDistanceSolver(self.v, self.f)
                self.backend = f"potpourri3d_heat:{getattr(pp3d, '__version__', 'unknown')}"
            except Exception:
                pass
        self._adj = None

    @property
    def adjacency(self):
        if self._adj is None:
            d = [{} for _ in self.v]
            for t in self.f:
                for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                    w = float(np.linalg.norm(self.v[a] - self.v[b]))
                    d[a][int(b)] = min(d[a].get(int(b), np.inf), w)
                    d[b][int(a)] = min(d[b].get(int(a), np.inf), w)
            self._adj = [list(q.items()) for q in d]
        return self._adj

    def distance(self, source: int) -> np.ndarray:
        if self._solver is not None:
            return np.asarray(self._solver.compute_distance(int(source)), np.float64)
        try:
            from scipy.sparse import csr_matrix
            from scipy.sparse.csgraph import dijkstra
            if self._csr is None:
                rows, cols, data = [], [], []
                for i, nb in enumerate(self.adjacency):
                    for j, w in nb:
                        rows.append(i); cols.append(j); data.append(w)
                self._csr = csr_matrix((data, (rows, cols)), shape=(len(self.v), len(self.v)))
                self.backend = "scipy_sparse_dijkstra_v1"
            return np.asarray(dijkstra(self._csr, directed=False, indices=int(source)), np.float64)
        except Exception:
            pass
        d = np.full(len(self.v), np.inf)
        d[int(source)] = 0.0
        h = [(0.0, int(source))]
        while h:
            x, i = heapq.heappop(h)
            if x != d[i]:
                continue
            for j, w in self.adjacency[i]:
                if x + w < d[j]:
                    d[j] = x + w
                    heapq.heappush(h, (x + w, j))
        return d

    def vertex_normals(self) -> np.ndarray:
        n = np.zeros_like(self.v)
        fn = np.cross(self.v[self.f[:, 1]] - self.v[self.f[:, 0]],
                       self.v[self.f[:, 2]] - self.v[self.f[:, 0]])
        for k in range(3):
            np.add.at(n, self.f[:, k], fn)
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    def tangent_frames(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        N = self.vertex_normals()
        axis = np.tile([0.0, 1.0, 0.0], (len(N), 1))
        bad = np.abs((axis * N).sum(1)) > 0.95
        axis[bad] = [1, 0, 0]
        T = axis - (axis * N).sum(1, keepdims=True) * N
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
        B = np.cross(N, T)
        return T.astype(np.float32), B.astype(np.float32), N.astype(np.float32)

    def metadata(self) -> dict:
        return {
            "backend": self.backend,
            "transport_backend": "tangent_projection_fallback_v1",
            "units": "canonical_surface_units_not_mm",
        }
