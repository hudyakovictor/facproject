"""Robustly scaled experimental zone-level texture comparison."""
import numpy as np


def compare_texture(a, b, min_support=100):
    with a.npz('features/texture.npz') as A, b.npz('features/texture.npz') as B:
        if not np.array_equal(A['columns'],B['columns']) or not np.array_equal(A['zone_id'],B['zone_id']):
            raise ValueError('feature contract mismatch')
        av=np.asarray(A['values'],float); bv=np.asarray(B['values'],float)
        # Scale each heterogeneous feature in its own units. This is only a
        # pair-local fallback; production must use frozen same-person calibration scales.
        joined=np.concatenate([av,bv],axis=0)
        med=np.nanmedian(joined,axis=0)
        scale=1.4826*np.nanmedian(np.abs(joined-med),axis=0)
        finite_positive=scale[np.isfinite(scale)&(scale>1e-8)]
        fallback=float(np.median(finite_positive)) if finite_positive.size else 1.0
        scale=np.where(np.isfinite(scale)&(scale>1e-8),scale,fallback)
        rows=[]
        for i,c in enumerate(A['zone_id']):
            ok=np.isfinite(av[i])&np.isfinite(bv[i])&np.isfinite(scale)&(scale>0)
            use=bool(A['effective_support'][i]>=min_support and B['effective_support'][i]>=min_support and ok.any())
            raw=np.abs(av[i]-bv[i]); scaled=raw/scale
            idx=np.flatnonzero(ok)
            rows.append({'zone':str(c),'status':'measured' if use else 'insufficient_evidence',
              'distance':float(np.median(scaled[ok])) if use else None,
              'feature_deltas':{str(A['columns'][j]):float(raw[j]) for j in idx} if use else {},
              'feature_deltas_scaled':{str(A['columns'][j]):float(scaled[j]) for j in idx} if use else {},
              'provenance_a':str(A['provenance_ref'][i]) if 'provenance_ref' in A else None,
              'provenance_b':str(B['provenance_ref'][i]) if 'provenance_ref' in B else None})
    return {'schema':'skin-texture-pair-v1','implementation_status':'experimental_zone_aggregate',
      'production_evidence_allowed':False,'scale_semantics':'pair-local robust MAD; replace with frozen calibration MAD',
      'zones':rows,'warning':'requires patch-distribution and quality calibration'}
