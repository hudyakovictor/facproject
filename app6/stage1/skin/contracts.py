"""Versioned, dependency-light contracts shared by skin Stage 1/2/3.

📜 CONVENTIONS v2 → контракты skin-пакета; статус: ✅ VERIFIED
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

SCHEMAS={
 "manifest":"skin-manifest-v1","surface":"skin-surface-observations-v1",
 "atlas":"skin-atlas-projection-v1","quality":"skin-quality-v1",
 "features":"skin-features-v1","wrinkles":"skin-wrinkles-v1",
 "material":"skin-material-evidence-v1","pair":"skin-pair-v1","temporal":"skin-temporal-v1"}

class EvidenceState(str,Enum):
 USABLE="usable";COARSE_ONLY="coarse_only";NOT_MEASURABLE="not_measurable";NOT_OBSERVED="not_observed";NOT_COMPARABLE="not_comparable";OUT_OF_DOMAIN="out_of_validated_domain";FAILED="failed"
class PairStatus(str,Enum):
 MATCHED_STABLE_STRUCTURE="matched_stable_structure";PARTIAL_MATCH="partial_match";COARSE_DIRECTION_MATCH="coarse_direction_match";QUALITY_EXPLAINED_DIFFERENCE="quality_explained_difference";DEGRADATION_ROBUST_DIFFERENCE="degradation_robust_difference";INSUFFICIENT_EVIDENCE="insufficient_evidence"
class ReasonCode(str,Enum):
 LOW_EFFECTIVE_RESOLUTION="LOW_EFFECTIVE_RESOLUTION";EXCESSIVE_BLUR="EXCESSIVE_BLUR";EXCESSIVE_NOISE="EXCESSIVE_NOISE";JPEG_DAMAGE="JPEG_DAMAGE";INSUFFICIENT_COMMON_COVERAGE="INSUFFICIENT_COMMON_COVERAGE";HIGH_INCIDENCE_ANGLE="HIGH_INCIDENCE_ANGLE";SELF_OCCLUDED="SELF_OCCLUDED";EXTERNAL_OCCLUSION="EXTERNAL_OCCLUSION";HAIR_OR_STUBBLE="HAIR_OR_STUBBLE";SPECULAR_CONTAMINATION="SPECULAR_CONTAMINATION";DEEP_SHADOW="DEEP_SHADOW";PROJECTION_UNSTABLE="PROJECTION_UNSTABLE";MODEL_FAILURE="MODEL_FAILURE";OUTSIDE_ATLAS="OUTSIDE_ATLAS";SOURCE_PROCESSING_UNKNOWN="SOURCE_PROCESSING_UNKNOWN";OUT_OF_CALIBRATION_ENVELOPE="OUT_OF_CALIBRATION_ENVELOPE"

@dataclass(frozen=True)
class Applicability:
 family:str;state:EvidenceState;effective_support:float;reasons:tuple[str,...]=();components:dict[str,float]=field(default_factory=dict)
 # 📤 Сериализация контракта в dict
 def to_dict(self):
  d=asdict(self);d['state']=self.state.value;d['reasons']=list(self.reasons);return d
@dataclass(frozen=True)
class FeatureRecord:
 feature:str;version:int;zone_level:str;zone_id:str;patch_id:str|None;value:float|None;units:str;state:EvidenceState;support:dict[str,Any];quality:dict[str,Any];confounders:tuple[str,...];input_branch:str;extractor_config_sha256:str
 # 📤 Сериализация контракта в dict
 def to_dict(self):
  d=asdict(self);d['state']=self.state.value;d['confounders']=list(self.confounders);return d

# 🚨 Проверка версии схемы; mismatch = исключение
def require_schema(payload:dict[str,Any],expected:str)->None:
 if payload.get('schema')!=expected:raise ValueError(f"schema mismatch: expected {expected}, got {payload.get('schema')}")

# ✅ Проверка обязательных ключей пакета
def validate_missing(value:Any,state:EvidenceState)->None:
 if state is EvidenceState.USABLE and value is None:raise ValueError('usable evidence cannot have null value')
 if state is not EvidenceState.USABLE and value==0:raise ValueError('zero sentinel forbidden for missing evidence')
