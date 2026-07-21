"""Scale-adaptive wrinkle detection: Frangi + Meijering + blackhat + Skan."""

from __future__ import annotations

import cv2
import numpy as np

from ..surface_geometry import SurfaceGeometry

try:
    from skimage.filters import frangi, meijering, apply_hysteresis_threshold
    from skimage.morphology import skeletonize
except Exception:
    frangi = meijering = apply_hysteresis_threshold = skeletonize = None


def response_map_scale_adaptive(gray01, valid, er_median=1.2):
    """Multi-scale ridge response with sigma adaptation to effective resolution."""
    ref_er = 1.2
    factor = float(np.clip(er_median / ref_er, 0.5, 3.0))
    sigmas = tuple(s * factor for s in (0.8, 1.5, 2.5, 4.0))

    g_uint8 = (np.clip(gray01, 0, 1) * 255).astype(np.uint8)
    blackhats = []
    for k in (5, 9, 15):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        bh = cv2.morphologyEx(g_uint8, cv2.MORPH_BLACKHAT, kernel).astype(np.float32) / 255.0
        blackhats.append(bh)
    bh_max = np.max(np.stack(blackhats), axis=0)
    responses = [bh_max]

    if frangi is not None:
        try:
            f_resp = frangi(gray01, sigmas=sigmas, black_ridges=True, mode="reflect")
            responses.append(f_resp.astype(np.float32))
        except Exception:
            pass
    if meijering is not None:
        try:
            m_resp = meijering(gray01, sigmas=sigmas, black_ridges=True, mode="reflect")
            responses.append(m_resp.astype(np.float32))
        except Exception:
            pass

    r = np.max(np.stack(responses), axis=0) if len(responses) > 1 else responses[0]
    r[~valid] = 0
    if np.any(valid):
        p99 = float(np.percentile(r[valid], 99))
        if p99 > 1e-8:
            r = np.clip(r / p99, 0, 1)
    return r.astype(np.float32), {"sigmas": sigmas, "er_factor": factor, "er_median": er_median}


def _branch_paths(sk):
    """Extract graph-ordered branch paths via Skan."""
    try:
        from skan import Skeleton
        graph = Skeleton(sk.astype(np.uint8))
        all_paths = [np.asarray(graph.path_coordinates(i), int) for i in range(graph.n_paths)]
        long_paths = [p for p in all_paths if len(p) >= 6]
        return long_paths, "skan", len(all_paths) - len(long_paths), graph
    except Exception:
        return [], "unavailable", 0, None


def detect(bgr, w, tid, bary, triangles, vertices, w14, er_median=None):
    """Detect wrinkles via multi-scale ridge filters + Skan skeleton analysis.

    Returns: ridge_probability, skeleton, points, branches, meta
    """
    gray01 = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    valid = np.asarray(w) > 0.15
    er_median = float(er_median) if er_median is not None and np.isfinite(er_median) and er_median > 0 else 1.2

    ridge, resp_meta = response_map_scale_adaptive(gray01, valid, er_median)

    # Hysteresis thresholds
    if valid.sum() > 50:
        high = max(0.15, float(np.percentile(ridge[valid], 88)))
        low = max(0.10, float(np.percentile(ridge[valid], 75)))
    else:
        high = low = 1.0

    try:
        binary = apply_hysteresis_threshold(ridge, low, high) & valid if apply_hysteresis_threshold is not None else (ridge >= high) & valid
    except Exception:
        binary = (ridge >= high) & valid

    sk = skeletonize(binary) if skeletonize is not None else binary
    degree = cv2.filter2D(sk.astype(np.uint8), cv2.CV_16S, np.ones((3, 3), np.uint8)) - sk.astype(np.int16)

    paths, backend, pruned, skan_graph = _branch_paths(sk)

    # Surface geometry
    tri = np.asarray(triangles)
    verts = np.asarray(vertices)
    try:
        geom = SurfaceGeometry(verts, tri, prefer_potpourri=False)
        T, B, _ = geom.tangent_frames()
    except Exception:
        geom = None
        T = B = None

    dt = np.dtype([
        ("x", "i4"), ("y", "i4"), ("triangle_id", "i4"),
        ("b0", "f4"), ("b1", "f4"), ("b2", "f4"),
        ("sx", "f4"), ("sy", "f4"), ("sz", "f4"),
        ("tangent_t", "f4"), ("tangent_b", "f4"),
        ("ridge_probability", "f4"),
    ])

    points, branches = [], []
    for pix in paths:
        if len(pix) < 6:
            continue
        surf_pts, keep = [], []
        for y, x in pix:
            if y < 0 or y >= tid.shape[0] or x < 0 or x >= tid.shape[1]:
                continue
            fi = int(tid[y, x])
            if fi < 0:
                continue
            bc = np.asarray(bary[y, x], float)
            if bc.size != 3:
                continue
            try:
                surf_pts.append(bc @ verts[tri[fi]])
                keep.append((int(y), int(x), fi, bc))
            except Exception:
                continue
        if len(surf_pts) < 2:
            continue
        surf_pts = np.asarray(surf_pts)
        L = float(np.linalg.norm(np.diff(surf_pts, axis=0), axis=1).sum())
        E = float(np.linalg.norm(surf_pts[-1] - surf_pts[0]))
        tort = L / max(E, 1e-8)

        # Orientation in tangent space
        angle = 0.0
        seed_v = 0
        if T is not None:
            mid = keep[len(keep) // 2]
            try:
                seed_v = int(tri[mid[2], int(np.argmax(mid[3]))])
                vec = surf_pts[-1] - surf_pts[0]
                tt = float(np.dot(vec, T[seed_v]))
                tb = float(np.dot(vec, B[seed_v]))
                angle = float(np.mod(np.arctan2(tb, tt), np.pi))
            except Exception:
                pass

        # W14 membership
        mem = []
        if w14 is not None:
            for k in range(min(14, w14.shape[0])):
                if any(w14[k, y, x] for y, x, _, _ in keep):
                    mem.append(f"W{k + 1:02d}")

        branches.append({
            "branch_id": len(branches), "point_start": len(points),
            "point_count": len(keep), "length_surface": L,
            "endpoint_distance_surface": E, "tortuosity": tort,
            "orientation_tangent_rad_mod_pi": angle,
            "mean_ridge_probability": float(np.mean([ridge[y, x] for y, x, _, _ in keep])) if keep else 0.0,
            "w14_membership": mem, "seed_vertex": seed_v,
        })

        for pi, (pos, (y, x, fi, bc)) in enumerate(zip(surf_pts, keep)):
            if len(surf_pts) >= 2:
                dvec = surf_pts[min(pi + 1, len(surf_pts) - 1)] - surf_pts[max(pi - 1, 0)]
            else:
                dvec = np.array([1, 0, 0], float)
            tt = tb = 0.0
            if T is not None:
                try:
                    v_idx = int(tri[fi, int(np.argmax(bc))])
                    tn = np.hypot(np.dot(dvec, T[v_idx]), np.dot(dvec, B[v_idx]))
                    tt = float(np.dot(dvec, T[v_idx]) / max(tn, 1e-9))
                    tb = float(np.dot(dvec, B[v_idx]) / max(tn, 1e-9))
                except Exception:
                    pass
            points.append((int(x), int(y), int(fi), float(bc[0]), float(bc[1]), float(bc[2]),
                           float(pos[0]), float(pos[1]), float(pos[2]), tt, tb,
                           float(ridge[y, x]) if y < ridge.shape[0] and x < ridge.shape[1] else 0.0))

    points_arr = np.array(points, dtype=dt) if points else np.array([], dtype=dt)
    orientations = [b["orientation_tangent_rad_mod_pi"] for b in branches]
    lengths = [b["length_surface"] for b in branches]
    if orientations:
        hist, _ = np.histogram(orientations, bins=8, range=(0, np.pi), weights=lengths)
        p = hist / (hist.sum() + 1e-12)
        orient_entropy = float(-np.sum(p * np.log(p + 1e-12)) / np.log(8))
    else:
        orient_entropy = 0.0
    endpoint_count = int(np.sum(sk & (degree == 1)))
    junction_count = int(np.sum(sk & (degree >= 3)))

    meta = {
        "backend": f"frangi_blackhat_meijering_skan_scale_adaptive",
        "threshold_high": high, "threshold_low": low,
        "er_median": er_median, "branch_count": len(branches),
        "point_count": len(points_arr), "orientation_entropy": orient_entropy,
        "endpoint_count": endpoint_count, "junction_count": junction_count,
    }
    return ridge.astype(np.float16), sk.astype(bool), points_arr, branches, meta
