import numpy as np
A_PAIRS=(('A01','A03'),('A04','A05'),('A06','A07'),('A09','A10'),('A11','A12'),('A13','A14'),('A15','A16'),('A17','A18'))
def texture_symmetry(package):
 with package.npz('features/texture.npz') as z:codes=list(map(str,z['zone_id']));vals=z['values'];states=z['state'];cols=list(map(str,z['columns']))
 rows=[]
 for a,b in A_PAIRS:
  i,j=codes.index(a),codes.index(b);ok=np.isfinite(vals[i])&np.isfinite(vals[j]);usable=states[i]=='usable' and states[j]=='usable' and ok.any();rows.append({'left_zone':a,'right_zone':b,'status':'measured' if usable else 'insufficient_evidence','mean_absolute_feature_difference':float(np.mean(abs(vals[i,ok]-vals[j,ok]))) if usable else None,'feature_deltas':{cols[k]:float(abs(vals[i,k]-vals[j,k])) for k in np.flatnonzero(ok)} if usable else {}})
 return {'schema':'skin-symmetry-v1','pairs':rows,'warning':'asymmetry is descriptive; pose/lighting/biology confounders remain'}
