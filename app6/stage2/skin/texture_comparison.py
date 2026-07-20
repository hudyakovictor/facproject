import numpy as np
def compare_texture(a,b,min_support=100):
 with a.npz('features/texture.npz') as A,b.npz('features/texture.npz') as B:
  if not np.array_equal(A['columns'],B['columns']) or not np.array_equal(A['zone_id'],B['zone_id']):raise ValueError('feature contract mismatch')
  av,bv=A['values'],B['values'];rows=[]
  for i,c in enumerate(A['zone_id']):
   ok=np.isfinite(av[i])&np.isfinite(bv[i]);use=A['effective_support'][i]>=min_support and B['effective_support'][i]>=min_support and ok.any();rows.append({'zone':str(c),'status':'measured' if use else 'insufficient_evidence','distance':float(np.mean(abs(av[i,ok]-bv[i,ok]))) if use else None,'feature_deltas':{str(A['columns'][j]):float(abs(av[i,j]-bv[i,j])) for j in np.flatnonzero(ok)} if use else {},'provenance_a':str(A['provenance_ref'][i]) if 'provenance_ref' in A else None,'provenance_b':str(B['provenance_ref'][i]) if 'provenance_ref' in B else None})
 return {'schema':'skin-texture-pair-v1','implementation_status':'experimental_zone_aggregate','production_evidence_allowed':False,'zones':rows,'warning':'requires patch-distribution and quality calibration'}
