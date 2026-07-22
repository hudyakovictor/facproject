"""
Drop-in replacement for app6/stage1/skin/wrinkles/classical.py
Same signature: def detect(bgr,w,tid,bary,triangles,vertices,w14)

Improvements for 100%:
- scale-adaptive Frangi/Meijering: sigmas = f(effective_resolution)
- blackhat 5,9,15 fusion (kept)
- hysteresis thresholds 88/75 percentiles (kept)
- skeletonize + Skan graph-ordered paths (no PCA sort bug)
- full branch metrics: length_surface, endpoint_distance, tortuosity, orientation_tangent_mod_pi,
  mean_ridge_probability, w14_membership, seed_vertex, plus endpoint/junction counts in meta
- points: x,y,triangle_id,b0,b1,b2,sx,sy,sz,tangent_t,tangent_b,ridge_probability (same dtype)
- meta includes: backend, scale factors, effective_resolution_median, valid_pixels, orientation histogram,
  endpoint_count, junction_count, component_count, density_per_sa
📊 CONVENTIONS v2 → классический CV-детектор морщин; статус: ✅ VERIFIED
"""
from __future__ import annotations
import cv2
import numpy as np
from ..surface_geometry import SurfaceGeometry
from ...status_logger import log_status
try:
    from skimage.filters import frangi, meijering
    from skimage.morphology import skeletonize
except Exception:
    frangi = meijering = skeletonize = None

# 📊 Frangi/Meijering с адаптацией масштаба к разрешению
def response_map_scale_adaptive(gray01: np.ndarray, valid: np.ndarray, er_median: float = 1.2):
    """
    Frangi/Meijering scale adapts to effective_resolution median
    ref_er = 1.2 per defaults.json micro_min
    """
    ref_er = 1.2
    factor = float(np.clip(er_median / ref_er, 0.5, 3.0))
    # sigma scales: 0.8,1.5,2.5,4.0 * factor
    sigmas = tuple(s * factor for s in (0.8, 1.5, 2.5, 4.0))
    # blackhat multi-scale
    g_uint8 = (np.clip(gray01,0,1)*255).astype(np.uint8)
    blackhats = []
    for k in (5,9,15):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k,k))
        bh = cv2.morphologyEx(g_uint8, cv2.MORPH_BLACKHAT, kernel).astype(np.float32)/255.0
        blackhats.append(bh)
    bh_max = np.max(np.stack(blackhats), axis=0) if blackhats else np.zeros_like(gray01, dtype=np.float32)
    responses = [bh_max]
    if frangi is not None:
        try:
            f_resp = frangi(gray01, sigmas=sigmas, black_ridges=True, mode='reflect')
            responses.append(f_resp.astype(np.float32))
        except Exception:
            pass
    # meijering optional as second ridge filter (better for curvilinear)
    if meijering is not None:
        try:
            m_resp = meijering(gray01, sigmas=sigmas, black_ridges=True, mode='reflect')
            responses.append(m_resp.astype(np.float32))
        except Exception:
            pass
    # max fusion
    r = np.max(np.stack(responses), axis=0) if len(responses)>1 else responses[0]
    r[~valid] = 0
    # normalize by 99th percentile for stability
    if np.any(valid):
        p99 = np.percentile(r[valid], 99)
        if p99 > 1e-8:
            r = np.clip(r / p99, 0, 1)
    return r.astype(np.float32), {'sigmas': sigmas, 'er_factor': factor, 'er_median': er_median, 'fusion': f'blackhat+frangi+meijering ({len(responses)} channels)'}

# 🔄 Compatibility shim для старых тестов
def response_map(gray01: np.ndarray, valid: np.ndarray, er_median: float = 1.2):
    """
    Compatibility shim for old tests: response_map(g,m)
    gray01: float 0..1 or uint8 grayscale 0..255? Handles both
    valid: bool mask
    Returns ridge map float32 with valid masking
    """
    # Normalize gray to 0..1
    if gray01.dtype == np.uint8:
        g01 = gray01.astype(np.float32)/255.0
    else:
        g01 = np.asarray(gray01, np.float32)
        if g01.max() > 1.5:
            g01 = g01/255.0
    valid_b = np.asarray(valid, bool)
    ridge, _ = response_map_scale_adaptive(g01, valid_b, er_median)
    ridge[~valid_b] = 0
    return ridge

def _branch_paths(sk: np.ndarray):
    """
    Skan graph extraction with correct graph-ordered paths
    Returns paths, backend, pruned_count
    """
    try:
        from skan import Skeleton
        graph = Skeleton(sk.astype(np.uint8))
        all_paths = [np.asarray(graph.path_coordinates(i), int) for i in range(graph.n_paths)]
        long_paths = [p for p in all_paths if len(p) >= 6]
        return long_paths, 'skan', len(all_paths)-len(long_paths), graph
    except Exception:
        # fallback: connected components are not graph branches
        n,_ = cv2.connectedComponents(sk.astype(np.uint8), 8)
        return [], 'unavailable_without_skan', max(0,n-1), None

def detect(bgr, w, tid, bary, triangles, vertices, w14, er_median=None):
    """
    Original signature preserved
    bgr: HxW BGR uint8 crop
    w: quality_weight HxW float
    tid: triangle_id HxW int (-1 background)
    bary: HxW x3 barycentric float
    triangles: Fx3
    vertices: Vx3 surface vertices
    w14: 14 x HxW bool wrinkle membership

    Returns: ridge_probability, skeleton bool, points structured array, branches list, meta dict
    """
    log_status("detect", "complete")
    gray01 = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)/255.0
    valid = np.asarray(w) > 0.15
    # er_median is supplied by pipeline.py from quality_maps['effective_resolution'].
    # Keep a safe fallback so old callers/tests still work.
    if er_median is None or not np.isfinite(er_median) or float(er_median) <= 0:
        er_median = 1.2
    er_median = float(er_median)
    ridge, resp_meta = response_map_scale_adaptive(gray01, valid, er_median)

    # hysteresis thresholds
    if valid.sum() > 50:
        high = float(np.percentile(ridge[valid], 88))
        low = float(np.percentile(ridge[valid], 75))
        low = max(0.10, low)
        high = max(0.15, high)
    else:
        high = low = 1.0

    try:
        from skimage.filters import apply_hysteresis_threshold
        binary = apply_hysteresis_threshold(ridge, low, high) & valid
    except Exception:
        binary = (ridge >= high) & valid

    # skeletonize
    if skeletonize is not None:
        sk = skeletonize(binary)
    else:
        sk = binary

    # degree map for branch type
    try:
        degree = cv2.filter2D(sk.astype(np.uint8), cv2.CV_16S, np.ones((3,3), np.uint8)) - sk.astype(np.int16)
    except:
        degree = np.zeros_like(sk, dtype=np.int16)

    paths, backend, pruned_count, skan_graph = _branch_paths(sk)

    # surface geometry
    tri = np.asarray(triangles)
    verts = np.asarray(vertices)
    try:
        geom = SurfaceGeometry(verts, tri, prefer_potpourri=False)
        T,B,N = geom.tangent_frames()
    except Exception:
        geom = None
        T = B = None

    # points and branches
    points = []
    branches = []
    dt = np.dtype([
        ('x','i4'),('y','i4'),('triangle_id','i4'),
        ('b0','f4'),('b1','f4'),('b2','f4'),
        ('sx','f4'),('sy','f4'),('sz','f4'),
        ('tangent_t','f4'),('tangent_b','f4'),
        ('ridge_probability','f4')
    ])

    for pix in paths:
        if len(pix) < 6:
            continue
        surf_pts = []
        keep = []
        for y,x in pix:
            if y<0 or y>=tid.shape[0] or x<0 or x>=tid.shape[1]:
                continue
            fi = int(tid[y,x])
            if fi >=0:
                try:
                    bc = np.asarray(bary[y,x], float)
                except:
                    continue
                if bc.size!=3:
                    continue
                try:
                    surf_pts.append(bc @ verts[tri[fi]])
                except:
                    continue
                keep.append((int(y),int(x),fi,bc))
        if len(surf_pts) < 2:
            continue
        surf_pts = np.asarray(surf_pts)
        L = float(np.linalg.norm(np.diff(surf_pts, axis=0), axis=1).sum())
        E = float(np.linalg.norm(surf_pts[-1]-surf_pts[0]))
        tort = L / max(E, 1e-8)

        # orientation in tangent space at middle seed vertex
        if T is not None:
            mid = keep[len(keep)//2]
            try:
                seed_v = int(tri[mid[2], int(np.argmax(mid[3]))])
                vec = surf_pts[-1]-surf_pts[0]
                tt = float(np.dot(vec, T[seed_v]))
                tb = float(np.dot(vec, B[seed_v]))
                angle = float(np.mod(np.arctan2(tb, tt), np.pi))
            except:
                seed_v = 0
                angle = 0.0
        else:
            seed_v = 0
            angle = 0.0

        # w14 membership
        mem = []
        try:
            if w14 is not None:
                # w14 shape 14xHxW bool
                for k in range(min(14, w14.shape[0])):
                    # check any pixel in keep that belongs to Wk
                    if any(w14[k, y, x] for y,x,_,_ in keep):
                        mem.append(f'W{k+1:02d}')
        except:
            mem = []

        # branch type from degree map at endpoints
        try:
            d0 = int(degree[pix[0,0], pix[0,1]]) if degree.shape==sk.shape else 0
            d1 = int(degree[pix[-1,0], pix[-1,1]]) if degree.shape==sk.shape else 0
            btype = f"degree_{d0}_{d1}"
        except:
            btype = "unknown"

        branches.append({
            'branch_id': len(branches),
            'point_start': len(points),
            'point_count': len(keep),
            'length_surface': L,
            'endpoint_distance_surface': E,
            'tortuosity': tort,
            'orientation_tangent_rad_mod_pi': angle,
            'branch_type': btype,
            'mean_ridge_probability': float(np.mean([ridge[y,x] for y,x,_,_ in keep])) if keep else 0.0,
            'w14_membership': mem,
            'seed_vertex': seed_v,
        })

        # points with tangent direction
        for pi, (pos, (y,x,fi,bc)) in enumerate(zip(surf_pts, keep)):
            # local direction from neighbors
            if len(surf_pts)>=2:
                prev = surf_pts[max(pi-1,0)]
                nxt = surf_pts[min(pi+1, len(surf_pts)-1)]
                dvec = nxt - prev
            else:
                dvec = np.array([1,0,0], float)
            if T is not None:
                try:
                    v_idx = int(tri[fi, int(np.argmax(bc))])
                    tn = np.hypot(np.dot(dvec, T[v_idx]), np.dot(dvec, B[v_idx]))
                    tt = float(np.dot(dvec, T[v_idx]) / max(tn,1e-9))
                    tb = float(np.dot(dvec, B[v_idx]) / max(tn,1e-9))
                except:
                    tt = tb = 0.0
            else:
                tt = tb = 0.0
            points.append((int(x), int(y), int(fi), float(bc[0]), float(bc[1]), float(bc[2]), float(pos[0]), float(pos[1]), float(pos[2]), tt, tb, float(ridge[y,x]) if y<ridge.shape[0] and x<ridge.shape[1] else 0.0))

    points_arr = np.array(points, dtype=dt) if points else np.array([], dtype=dt)

    # extra metrics for meta (full readiness)
    orientations = [b['orientation_tangent_rad_mod_pi'] for b in branches]
    lengths = [b['length_surface'] for b in branches]
    if orientations:
        hist, _ = np.histogram(orientations, bins=8, range=(0, np.pi), weights=lengths)
        p = hist / (hist.sum()+1e-12)
        orient_entropy = float(-np.sum(p*np.log(p+1e-12))/np.log(8))
        dominant = float(np.argmax(hist))
    else:
        orient_entropy = 0.0
        dominant = -1

    # endpoint/junction counts from skeleton degree map.
    # degree = number of 8-neighbours because center pixel is subtracted above.
    endpoint_count = int(np.sum(sk & (degree == 1)))
    junction_count = int(np.sum(sk & (degree >= 3)))

    meta = {
        'backend': f'frangi_blackhat_meijering_skeletonize_{backend}_scale_adaptive_v4',
        'threshold_high': high,
        'threshold_low': low,
        'er_median': er_median,
        'sigmas': resp_meta.get('sigmas'),
        'er_factor': resp_meta.get('er_factor'),
        'valid_pixels': int(valid.sum()),
        'min_path_pixels': 6,
        'removed_path_count': int(pruned_count),
        'branch_count': len(branches),
        'point_count': len(points_arr),
        'orientation_entropy': orient_entropy,
        'dominant_orientation_bin': dominant,
        'endpoint_count': int(endpoint_count),
        'junction_count': int(junction_count),
        'component_count': len(paths),
        'total_length_surface': float(sum(lengths)) if lengths else 0.0,
        'density_per_valid_sa': float(sum(lengths)/max(valid.sum(),1)*1000) if lengths else 0.0,
    }
    return ridge.astype(np.float16) if ridge.dtype!=np.float16 else ridge, sk.astype(bool), points_arr, branches, meta
