"""Noise-anchored local skin feature detector; drop-in replacement.

📊 CONVENTIONS v2 → детектор локальных признаков; статус: 🔬 EXPERIMENTAL
"""
from __future__ import annotations
import cv2
import numpy as np
from ...status_logger import log_status, log_blocker, log_warning


def detect(bgr, w, tid, bary, triangles, vertices, max_candidates=500):
    log_status("detect", "complete")
    lab_img = cv2.cvtColor(np.asarray(bgr), cv2.COLOR_BGR2LAB)
    L = lab_img[..., 0].astype(np.float32) / 255.0
    r = np.abs(L - cv2.GaussianBlur(L, (0, 0), 5))
    valid = np.asarray(w, np.float32) > 0.2
    vals = r[valid]
    if vals.size > 100:
        med = float(np.median(vals))
        noise_sigma = max(float(1.4826*np.median(np.abs(vals-med))), 1e-6)
        thr = med + 4.0*noise_sigma
    else:
        med, noise_sigma, thr = 0.0, 1.0, 1.0
    binary = ((r >= max(thr, 0.02)) & valid).astype(np.uint8)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(binary, 8)
    tri, verts = np.asarray(triangles), np.asarray(vertices)
    rows = []
    order = sorted(range(1, n), key=lambda j: float(r[labels == j].max()), reverse=True)
    for i in order[:max_candidates]:
        area = int(stats[i, cv2.CC_STAT_AREA])
        x, y = map(int, np.round(cents[i])); x=np.clip(x,0,r.shape[1]-1); y=np.clip(y,0,r.shape[0]-1)
        fi = int(tid[y, x])
        if area < 3 or area > 500 or fi < 0: continue
        bc = np.asarray(bary[y, x], float)
        pos = bc @ verts[tri[fi]]
        ys, xs = np.where(labels == i)
        ev = np.linalg.eigvalsh(np.cov(np.c_[xs, ys].T)) if len(xs) > 2 else np.array([1.,1.])
        ecc = float(np.sqrt(max(0., 1.-ev[0]/max(ev[-1],1e-8))))
        region = labels == i
        ring = cv2.dilate(region.astype(np.uint8), np.ones((5,5),np.uint8)).astype(bool) & ~region & valid
        if ring.any():
            lin, lbg = float(L[region].mean()), float(L[ring].mean())
            contrast = (lin-lbg)/max(lbg, 0.05)  # Weber-relative, not absolute luminance
        else: contrast = np.nan
        response_sigma = float(r[region].max()/noise_sigma)
        rows.append((len(rows),x,y,fi,*bc,*pos,area,ecc,contrast,response_sigma))
    dt=np.dtype([('candidate_id','i4'),('x','i4'),('y','i4'),('triangle_id','i4'),
      ('b0','f4'),('b1','f4'),('b2','f4'),('sx','f4'),('sy','f4'),('sz','f4'),
      ('area_px','i4'),('eccentricity','f4'),('relative_luminance_contrast','f4'),('response_max','f4')])
    meta={'threshold':float(thr),'noise_sigma':float(noise_sigma),'candidate_count':len(rows),
      'threshold_semantics':'median+4*MAD_sigma (absolute, noise-anchored)',
      'contrast_semantics':'weber_relative','response_semantics':'sigma_above_local_background',
      'semantics':'independent candidates only'}
    return r, np.array(rows,dtype=dt), meta
