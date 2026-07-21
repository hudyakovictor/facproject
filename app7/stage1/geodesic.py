"""Geodesic distances between landmarks on the 3D mesh surface.

Geodesic distances are pose-invariant — they measure the shortest path
ALONG the mesh surface, not through 3D space. This makes them far more
reliable for bone structure comparison than Euclidean distances between
aligned landmarks, which still carry residual pose noise.

Uses potpourri3d (heat method, GPU-fast) if available, falls back to
scipy Dijkstra, then to a pure-Python Dijkstra.
"""

from __future__ import annotations

import numpy as np
from pathlib import Path


def compute_landmark_geodesic_matrix(
    vertices: np.ndarray,
    triangles: np.ndarray,
    landmark_indices: np.ndarray,
) -> np.ndarray:
    """Compute geodesic distance matrix between all landmark pairs.

    Args:
        vertices: (V, 3) mesh vertices
        triangles: (F, 3) triangle indices
        landmark_indices: (L,) vertex indices of landmarks

    Returns:
        (L, L) float64 geodesic distance matrix
    """
    vertices = np.asarray(vertices, np.float64)
    triangles = np.asarray(triangles, np.int64)
    ldm_idx = np.asarray(landmark_indices, np.int64)
    n_ldm = len(ldm_idx)

    # Build adjacency graph
    adj = _build_adjacency(vertices, triangles)

    # Try potpourri3d (fast heat method)
    solver = _try_potpourri3d(vertices, triangles)
    if solver is not None:
        dist_matrix = np.zeros((n_ldm, n_ldm), np.float64)
        for i, si in enumerate(ldm_idx):
            d = np.asarray(solver.compute_distance(int(si)), np.float64)
            for j, sj in enumerate(ldm_idx):
                dist_matrix[i, j] = d[int(sj)]
        return dist_matrix

    # Try scipy sparse Dijkstra
    sp_result = _try_scipy_dijkstra(adj, ldm_idx)
    if sp_result is not None:
        return sp_result

    # Fallback: pure Python Dijkstra
    dist_matrix = np.zeros((n_ldm, n_ldm), np.float64)
    for i, si in enumerate(ldm_idx):
        d = _dijkstra(adj, int(si))
        for j, sj in enumerate(ldm_idx):
            dist_matrix[i, j] = d[int(sj)]
    return dist_matrix


def geodesic_distance_vector(
    geodesic_matrix: np.ndarray,
    landmark_zones: dict | None = None,
) -> dict[str, np.ndarray]:
    """Extract structured distance vectors from geodesic matrix.

    Returns separate vectors for bone-bone, bone-skin, skin-skin pairs,
    plus the full upper-triangle vector for identity comparison.
    """
    n = geodesic_matrix.shape[0]
    upper_idx = np.triu_indices(n, k=1)
    full_vector = geodesic_matrix[upper_idx]

    result = {
        "full_vector": full_vector,
        "full_mean": float(np.mean(full_vector)) if len(full_vector) > 0 else 0.0,
        "full_std": float(np.std(full_vector)) if len(full_vector) > 0 else 0.0,
    }

    if landmark_zones is not None:
        bone_ids = landmark_zones.get("bone_landmark_ids", [])
        skin_ids = landmark_zones.get("skin_landmark_ids", [])

        if bone_ids:
            bone_upper = np.triu_indices(len(bone_ids), k=1)
            bone_sub = geodesic_matrix[np.ix_(bone_ids, bone_ids)]
            bone_vec = bone_sub[bone_upper]
            result["bone_bone_vector"] = bone_vec
            result["bone_bone_mean"] = float(np.mean(bone_vec)) if len(bone_vec) > 0 else 0.0
            result["bone_bone_std"] = float(np.std(bone_vec)) if len(bone_vec) > 0 else 0.0

        if skin_ids:
            skin_upper = np.triu_indices(len(skin_ids), k=1)
            skin_sub = geodesic_matrix[np.ix_(skin_ids, skin_ids)]
            skin_vec = skin_sub[skin_upper]
            result["skin_skin_vector"] = skin_vec
            result["skin_skin_mean"] = float(np.mean(skin_vec)) if len(skin_vec) > 0 else 0.0

        if bone_ids and skin_ids:
            cross_sub = geodesic_matrix[np.ix_(bone_ids, skin_ids)]
            result["bone_skin_vector"] = cross_sub.ravel()
            result["bone_skin_mean"] = float(np.mean(cross_sub))

    return result


def compare_geodesic_vectors(
    vec_a: dict[str, np.ndarray],
    vec_b: dict[str, np.ndarray],
) -> dict[str, float]:
    """Compare two geodesic distance vectors (same landmark ordering).

    Returns per-category relative differences and overall identity score.
    """
    results = {}

    for key in ("bone_bone", "skin_skin", "bone_skin", "full"):
        va = vec_a.get(f"{key}_vector")
        vb = vec_b.get(f"{key}_vector")
        if va is None or vb is None:
            continue
        va = np.asarray(va, np.float64)
        vb = np.asarray(vb, np.float64)
        if len(va) != len(vb) or len(va) == 0:
            continue

        # Relative difference: |a-b| / (|a| + |b| + eps)
        denom = np.abs(va) + np.abs(vb) + 1e-9
        rel_diff = np.abs(va - vb) / denom
        results[f"{key}_mean_rel_diff"] = float(np.mean(rel_diff))
        results[f"{key}_max_rel_diff"] = float(np.max(rel_diff))

        # Correlation
        if len(va) > 2:
            corr = float(np.corrcoef(va, vb)[0, 1])
            results[f"{key}_correlation"] = corr

    return results


# ─── Internal helpers ─────────────────────────────────────────────────

def _build_adjacency(vertices, triangles):
    """Build vertex adjacency list with edge weights."""
    n = len(vertices)
    adj = [dict() for _ in range(n)]
    for t in triangles:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            w = float(np.linalg.norm(vertices[a] - vertices[b]))
            a, b = int(a), int(b)
            adj[a][b] = min(adj[a].get(b, np.inf), w)
            adj[b][a] = min(adj[b].get(a, np.inf), w)
    return [list(d.items()) for d in adj]


def _try_potpourri3d(vertices, triangles):
    """Try to create a potpourri3d heat method solver."""
    try:
        import potpourri3d as pp3d
        return pp3d.MeshHeatMethodDistanceSolver(vertices, triangles)
    except Exception:
        return None


def _try_scipy_dijkstra(adj, landmark_indices):
    """Try scipy sparse Dijkstra for all landmark sources at once."""
    try:
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import dijkstra
        n = len(adj)
        rows, cols, data = [], [], []
        for i, nb in enumerate(adj):
            for j, w in nb:
                rows.append(i); cols.append(j); data.append(w)
        graph = csr_matrix((data, (rows, cols)), shape=(n, n))
        dist = dijkstra(graph, directed=False, indices=landmark_indices.astype(int))
        if dist.shape[0] == len(landmark_indices):
            return dist[:, landmark_indices.astype(int)]
    except Exception:
        pass
    return None


def _dijkstra(adj, source):
    """Pure Python Dijkstra from source vertex."""
    import heapq
    n = len(adj)
    d = np.full(n, np.inf, np.float64)
    d[source] = 0.0
    h = [(0.0, source)]
    while h:
        x, i = heapq.heappop(h)
        if x != d[i]:
            continue
        for j, w in adj[i]:
            if x + w < d[j]:
                d[j] = x + w
                heapq.heappush(h, (x + w, j))
    return d
