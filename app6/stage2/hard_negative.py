"""Hard-negative/look-alike holdout validation. Never tunes thresholds."""
from __future__ import annotations
from collections import defaultdict
import numpy as np
def evaluate(rows:list[dict], *, score_key:str="primary_robust_z", threshold:float)->dict:
 grouped=defaultdict(list)
 for r in rows:
  if r.get("subject_a")==r.get("subject_b"):continue
  grouped[(r.get("subject_a"),r.get("subject_b"))].append(float(r[score_key]))
 units=[float(np.median(v)) for v in grouped.values() if v]
 fmr=float(np.mean(np.asarray(units)<=threshold)) if units else None
 return {"schema":"deeputin-hard-negative-v1","status":"complete" if units else "insufficient","independent_person_pairs":len(units),"false_match_rate":fmr,"threshold_source":"external_calibration_only"}
