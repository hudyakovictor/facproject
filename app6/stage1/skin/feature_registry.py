from __future__ import annotations
from dataclasses import asdict,dataclass
@dataclass(frozen=True)
class FeatureSpec:
 name:str;version:int;family:str;input_branch:str;zone_levels:tuple[str,...];units:str;expected_range:tuple[float|None,float|None];required_quality:str;scale_definition:str;missing_policy:str;aggregation:str;confounders:tuple[str,...];determinism_tolerance:float;storage_column:str
REGISTRY={}
def register(spec:FeatureSpec):
 key=f'{spec.name}@{spec.version}'
 if key in REGISTRY:raise ValueError(f'duplicate feature {key}')
 if spec.missing_policy!='null_with_state_and_reasons':raise ValueError('unsupported missing policy')
 REGISTRY[key]=spec;return spec
for s in [
 FeatureSpec('zone_luminance_median',1,'macro_texture','raw',('A20','S40'),'normalized_0_1',(0,1),'macro_texture','native pixels','null_with_state_and_reasons','weighted_median+MAD+IQR',('illumination','exposure'),1e-6,'luminance_median'),
 FeatureSpec('zone_luminance_mad',1,'macro_texture','raw',('A20','S40'),'normalized_0_1',(0,.5),'macro_texture','native pixels','null_with_state_and_reasons','weighted_median+MAD+IQR',('noise','illumination'),1e-6,'luminance_mad'),
 FeatureSpec('ridge_density',1,'wrinkles','low_frequency_normalized',('W14',),'surface_units_per_area',(0,None),'wrinkles','multiscale','null_with_state_and_reasons','weighted_median+support',('expression','shadow','hair'),1e-5,'ridge_density')]:register(s)
def export_registry():return [asdict(REGISTRY[k]) for k in sorted(REGISTRY)]
for _name,_family in [('lbp_entropy','LBP'),('lbp_uniform_fraction','LBP'),('glcm_contrast','GLCM'),('glcm_homogeneity','GLCM'),('glcm_energy','GLCM'),('gabor_energy','Gabor'),('gabor_anisotropy','Gabor'),('spectral_entropy','spectrum'),('spectral_high_ratio','spectrum'),('structure_coherence','structure_tensor'),('log_blob_density','microrelief'),('local_mad','microrelief')]:
 register(FeatureSpec(_name,1,_family,'raw',('A20','S40'),'dimensionless',(0,None),'meso_texture','native pixels / effective-resolution gated','null_with_state_and_reasons','weighted zone summary',('blur','noise','JPEG','illumination'),1e-5,_name))
for _name in ('lab_L_median','lab_a_median','lab_b_median','lab_a_mad','chroma_mad','color_entropy'):
 register(FeatureSpec(_name,1,'pigmentation','raw',('A20','S40'),'normalized_Lab',(None,None),'pigmentation','native pixels','null_with_state_and_reasons','weighted zone summary',('illumination','white_balance','makeup'),1e-5,_name))
