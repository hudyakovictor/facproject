import numpy as np
def bootstrap_interval(values,n_boot=1000,seed=0):
 x=np.asarray(values,float);x=x[np.isfinite(x)]
 if len(x)<3:return {'status':'insufficient_evidence','estimate':None}
 rng=np.random.default_rng(seed);s=np.array([np.median(x[rng.integers(0,len(x),len(x))]) for _ in range(n_boot)]);return {'status':'measured','estimate':float(np.median(x)),'low':float(np.quantile(s,.025)),'high':float(np.quantile(s,.975)),'n':len(x),'seed':seed}
