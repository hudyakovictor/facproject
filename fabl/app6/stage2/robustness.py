"""Robust landmark validation utilities for synthetic and calibration tests."""
from __future__ import annotations
import numpy as np


def validate_landmarks(points, ids=None, visibility=None, expected_count=None):
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1]!=3: raise ValueError('landmarks must have shape (N,3)')
    if expected_count is not None and len(p)!=int(expected_count): raise ValueError('unexpected landmark count')
    if not np.isfinite(p).all(): raise ValueError('landmarks contain NaN/Inf')
    if ids is not None:
        ids=np.asarray(ids)
        if ids.shape!=(len(p),): raise ValueError('landmark ids length mismatch')
        if len(np.unique(ids))!=len(ids): raise ValueError('duplicate landmark ids')
        if set(ids.tolist())!=set(range(len(p))): raise ValueError('missing or out-of-range landmark ids')
    if visibility is not None:
        v=np.asarray(visibility)
        if v.shape!=(len(p),): raise ValueError('visibility length mismatch')
    return True


def normalize_points(points):
    p=np.asarray(points,float); validate_landmarks(p)
    c=p.mean(axis=0); q=p-c
    s=float(np.sqrt(np.mean(np.sum(q*q,axis=1))))
    if not np.isfinite(s) or s<=1e-12: raise ValueError('degenerate landmarks')
    return q/s


def kabsch_rmse(a,b):
    a=np.asarray(a,float); b=np.asarray(b,float)
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=3 or len(a)<3: raise ValueError('incompatible landmarks')
    ac=a-a.mean(0); bc=b-b.mean(0); u,_,vt=np.linalg.svd(ac.T@bc); R=u@vt
    if np.linalg.det(R)<0: u[:,-1]*=-1; R=u@vt
    return float(np.sqrt(np.mean(np.sum((ac@R-bc)**2,axis=1))))


def robust_pair_distance(a,b,visibility_a=None,visibility_b=None,min_common=20,trim_fraction=0.10):
    a=np.asarray(a,float); b=np.asarray(b,float)
    validate_landmarks(a); validate_landmarks(b)
    if a.shape!=b.shape: raise ValueError('landmark shape mismatch')
    va=np.ones(len(a),bool) if visibility_a is None else np.asarray(visibility_a,bool)
    vb=np.ones(len(b),bool) if visibility_b is None else np.asarray(visibility_b,bool)
    if va.shape!=(len(a),) or vb.shape!=(len(b),): raise ValueError('visibility shape mismatch')
    mask=va&vb
    if int(mask.sum())<int(min_common): return {'status':'insufficient_visibility','common':int(mask.sum()),'rmse':None,'trimmed_rmse':None,'median':None}
    d=np.linalg.norm(a[mask]-b[mask],axis=1); k=max(3,int(np.ceil(len(d)*(1-float(trim_fraction)))))
    keep=np.partition(d,k-1)[:k]
    return {'status':'ok','common':int(mask.sum()),'rmse':float(np.sqrt(np.mean(d*d))),'trimmed_rmse':float(np.sqrt(np.mean(keep*keep))),'median':float(np.median(d))}


def robust_threshold(values,quantile=0.95,max_contamination=0.20):
    x=np.asarray(values,float); x=x[np.isfinite(x)]
    if len(x)<5: raise ValueError('at least five calibration values required')
    med=float(np.median(x)); mad=float(np.median(np.abs(x-med)))
    cap=med+6*1.4826*max(mad,1e-12); clean=x[x<=cap]
    if len(clean)<(1-max_contamination)*len(x): clean=np.sort(x)[:max(5,int(np.ceil((1-max_contamination)*len(x))))]
    return {'threshold':float(np.quantile(clean,quantile)),'median':med,'mad':mad,'input_n':len(x),'retained_n':len(clean)}


def classify_sequence(distances,threshold,min_regime_edges=2):
    flags=np.asarray(distances,float)>float(threshold)
    regimes=[]; start=None
    for i,v in enumerate(flags):
        if v and start is None: start=i
        if (not v or i==len(flags)-1) and start is not None:
            end=i if v and i==len(flags)-1 else i-1
            if end-start+1>=min_regime_edges: regimes.append((start,end))
            start=None
    return {'flags':flags.tolist(),'regimes':regimes,'isolated':int(flags.sum()-sum(e-s+1 for s,e in regimes))}


def effective_sample_size(cluster_ids):
    ids=np.asarray(cluster_ids)
    if ids.ndim!=1 or len(ids)==0: raise ValueError('cluster_ids must be non-empty vector')
    _,counts=np.unique(ids,return_counts=True); w=1/counts
    return float((w.sum()**2)/(np.sum(w*w)))


def ensure_same_pose(pose_a, pose_b):
    """Fail closed before scoring landmarks from different pose bins."""
    if not isinstance(pose_a,str) or not isinstance(pose_b,str): raise ValueError('pose bins must be strings')
    if pose_a != pose_b: raise ValueError(f'cross-pose comparison rejected: {pose_a} vs {pose_b}')
    return True


def balanced_person_threshold(values_by_person, quantile=0.95):
    """Equal-person threshold so prolific sessions cannot dominate calibration."""
    per=[]
    for _, values in values_by_person.items():
        x=np.asarray(values,float); x=x[np.isfinite(x)]
        if len(x)<2: continue
        per.append(float(np.quantile(x,quantile)))
    if len(per)<3: raise ValueError('at least three people with two values each required')
    return float(np.median(per))


MIN_REFERENCE_PERSONS = 3


def balanced_reference(values_by_person, min_persons: int = MIN_REFERENCE_PERSONS):
    """Build a robust reference with equal weight per calibration person.

    A participant with hundreds of adjacent video frames must not dominate a
    participant represented by a small independent session.  Quantiles are
    computed per person and aggregated by their median.

    D6: a reference derived from fewer than ``min_persons`` people is not a
    population reference at all — it is one person's noise.  Such a reference is
    returned with ``count=0`` and an explicit status so that ``calibrated_score``
    reports ``insufficient_calibration`` instead of silently trusting it.  This
    mirrors ``balanced_person_threshold``, which already required three people.
    """
    summaries=[]
    total=0
    for _, values in values_by_person.items():
        x=np.asarray(values,float); x=x[np.isfinite(x)]
        if len(x)<2: continue
        total += len(x)
        med=float(np.median(x)); mad=float(np.median(np.abs(x-med)))
        summaries.append((med,mad,float(np.quantile(x,.95)),float(np.quantile(x,.99))))
    if len(summaries) < int(min_persons):
        return {'count':0,'dataset_count':len(summaries),'median':0.0,'mad':0.0,'p95':0.0,'p99':0.0,
                'policy':'equal_person_median_of_quantiles_v1',
                'status':'insufficient_persons',
                'required_persons':int(min_persons),
                'observed_value_count':int(total)}
    a=np.asarray(summaries,float)
    return {'count':int(len(a)),'dataset_count':int(len(a)),'median':float(np.median(a[:,0])),
            'mad':float(np.median(a[:,1])),'p95':float(np.median(a[:,2])),
            'p99':float(np.median(a[:,3])),'policy':'equal_person_median_of_quantiles_v1',
            'observed_value_count':int(total)}


def validate_serialized_record(csv_points, npz_points, metadata_angles, npz_angles, atol=1e-6):
    """Reject divergence between CSV, NPZ and metadata representations."""
    a=np.asarray(csv_points,float); b=np.asarray(npz_points,float)
    validate_landmarks(a); validate_landmarks(b)
    if a.shape!=b.shape or not np.allclose(a,b,rtol=0,atol=atol): raise ValueError('CSV/NPZ landmark mismatch')
    ma=np.asarray(metadata_angles,float); na=np.asarray(npz_angles,float)
    if ma.shape!=(3,) or na.shape!=(3,) or not np.allclose(ma,na,rtol=0,atol=atol): raise ValueError('metadata/NPZ angle mismatch')
    return True


def noise_adjusted_threshold(base_threshold, coordinate_sigma, dimensions=3, safety_factor=1.25):
    """Increase an RMSE threshold for measured coordinate noise, explicitly and audibly."""
    base=float(base_threshold); sigma=float(coordinate_sigma)
    if not np.isfinite(base) or base<=0: raise ValueError('base_threshold must be positive')
    if not np.isfinite(sigma) or sigma<0: raise ValueError('coordinate_sigma must be non-negative')
    if int(dimensions)<=0 or float(safety_factor)<1: raise ValueError('invalid adjustment parameters')
    return float(np.sqrt(base*base + float(safety_factor)**2 * int(dimensions) * sigma*sigma))


def cluster_bootstrap_ci(values, cluster_ids, statistic=np.mean, *, n_boot=2000, alpha=0.05, seed=0):
    """Cluster bootstrap confidence interval for a dependent sample (patch 10).

    Pairs from the same photo/capture event are dependent observations; a naive
    per-observation bootstrap underestimates the CI width.  Here whole clusters
    are resampled with replacement, and the naive width is reported alongside so
    the underestimation factor is explicit, not hidden.

    Args:
        values: observations (1-D).
        cluster_ids: cluster label per observation (same length).
        statistic: function mapping a sample to a scalar (default np.mean).
        n_boot: number of bootstrap replicates.
        alpha: two-sided significance level (0.05 -> 95% CI).
        seed: RNG seed for reproducibility.

    Returns:
        dict with point estimate, cluster CI bounds, naive (per-observation)
        CI width, the width-underestimation factor, and sample sizes.

    Raises:
        ValueError: shape mismatch, empty input, or fewer than two clusters.
    """
    x = np.asarray(values, float)
    ids = np.asarray(cluster_ids)
    if x.ndim != 1 or ids.ndim != 1 or x.shape != ids.shape or len(x) == 0:
        raise ValueError("values and cluster_ids must be equal non-empty vectors")
    finite = np.isfinite(x)
    x = x[finite]; ids = ids[finite]
    clusters = np.unique(ids)
    if clusters.size < 2:
        raise ValueError("at least two clusters are required")
    n_boot = max(int(n_boot), 50)
    rng = np.random.default_rng(int(seed))
    point = float(statistic(x))
    naive = np.asarray([float(statistic(rng.choice(x, size=x.size, replace=True)))
                        for _ in range(n_boot)], dtype=np.float64)
    boot = []
    for _ in range(n_boot):
        picked = rng.choice(clusters, size=clusters.size, replace=True)
        sample = np.concatenate([x[ids == c] for c in picked])
        boot.append(float(statistic(sample)))
    boot = np.asarray(boot, dtype=np.float64)
    lo, hi = np.quantile(boot, [alpha / 2.0, 1.0 - alpha / 2.0])
    n_lo, n_hi = np.quantile(naive, [alpha / 2.0, 1.0 - alpha / 2.0])
    width = float(hi - lo)
    naive_width = float(n_hi - n_lo)
    return {"point": point,
            "ci_lo": float(lo), "ci_hi": float(hi),
            "width": width, "naive_width": naive_width,
            "width_underestimate_factor": float(naive_width / width) if width > 0 else float("nan"),
            "n_observations": int(len(x)), "n_clusters": int(clusters.size),
            "n_boot": n_boot, "alpha": float(alpha),
            "seed": int(seed), "method": "cluster_bootstrap_v1"}