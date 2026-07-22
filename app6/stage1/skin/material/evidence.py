"""📊 METRIC → Evidence для материальной модели: медианные статистики по зонам.
🚪 API: build()
🔗 DEPENDS ON: surface_geometry + photometric branches.
"""
from __future__ import annotations
import numpy as np
from ...status_logger import log_status, log_blocker, log_warning
def _between(v):
 if len(v)<2:return None
 out=[]
 for j in range(v.shape[1]):
  x=v[:,j];x=x[np.isfinite(x)]
  if len(x)>1:out.append(float(np.var(x)))
 return float(np.median(out)) if out else None
def _median(v,j):
 if not len(v) or j>=v.shape[1]:return None
 x=v[:,j];x=x[np.isfinite(x)];return float(np.median(x)) if len(x) else None
def build(rows,q,app):
 log_status("build", "experimental", "No verdict, experimental foundation")
 u=[r for r in rows if r['state']=='usable'];v=np.stack([r['values'] for r in u]) if u else np.empty((0,0));domain=q['quality_weight']>0;families={'microtexture':{'state':app['micro_texture']['state'],'between_zone_variance':_between(v)},'homogeneity':{'state':'usable' if len(v)>2 else 'not_measurable','median_local_mad':_median(v,11)},'repetition':{'state':'usable' if len(v)>2 else 'not_measurable','median_spectral_entropy':_median(v,7)},'specular':{'state':app['material_optics']['state'],'specular_fraction':float(q['specular_mask'][domain].mean()) if domain.any() else None},'processing':{'state':'usable','jpeg_block_score':float(q['global_jpeg_block_score']),'noise_level':float(q['global_noise_level']),'sharpening_halo_score':float(q['global_sharpening_halo_score']),'denoise_flat_fraction':float(q['global_denoise_flat_fraction']),'resize_periodicity_score':float(q['global_resize_periodicity_score'])}};n=sum(x['state'] in {'usable','coarse_only'} for x in families.values());return {'schema':'skin-material-evidence-v1','implementation_status':'experimental_foundation','production_evidence_allowed':False,'status':'mixed_uncertain' if n else 'insufficient_evidence','evidence_sufficiency':n/len(families),'domain_shift_risk':None,'degradation_explained_fraction':None,'families':families,'supporting':[],'contradicting':[],'unusable':[k for k,x in families.items() if x['state'] not in {'usable','coarse_only'}],'probability':None,'warning':'separate PAD calibration required; no verdict'}
