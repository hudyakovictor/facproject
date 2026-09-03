"""Validated persistent UI settings; diagnostic thresholds are never evidence."""
from __future__ import annotations
import json,os
from copy import deepcopy
from pathlib import Path
from typing import Any
from pydantic import BaseModel,Field,model_validator
SETTINGS_SCHEMA="deeputin-api-settings-v1.1"
DEFAULT_SETTINGS={"schema":SETTINGS_SCHEMA,"threshold_mode":"diagnostic_only","heatmap":{"stop_blue_cyan":.25,"stop_cyan_green":.50,"stop_green_red":.75,"stop_saturated_red":1.0,"max_residual_reference":.12},"landmark_shift":{"tolerance":.02,"suspect":.05,"calibrated":False},"thresholds":{"confidence_min":.5,"quality_min":.35,"geometry_zone_delta_limit":.018,"texture_zone_delta_limit":.04,"expression_smile":.92,"expression_jaw_open":.28},"detail_level":"standard","language":"ru"}
class Thresholds(BaseModel):
 confidence_min:float=Field(.5,ge=0,le=1);quality_min:float=Field(.35,ge=0,le=1);geometry_zone_delta_limit:float=Field(.018,gt=0);texture_zone_delta_limit:float=Field(.04,gt=0);expression_smile:float=Field(.92,ge=0,le=1);expression_jaw_open:float=Field(.28,ge=0,le=1)
class SettingsPayload(BaseModel):
 schema:str=SETTINGS_SCHEMA;threshold_mode:str="diagnostic_only";thresholds:Thresholds=Thresholds();heatmap:dict[str,Any]=DEFAULT_SETTINGS["heatmap"];landmark_shift:dict[str,Any]=DEFAULT_SETTINGS["landmark_shift"];detail_level:str="standard";language:str="ru"
 @model_validator(mode="after")
 def guard(self):
  if self.threshold_mode not in {"diagnostic_only","calibrated"}:raise ValueError("invalid threshold_mode")
  if self.threshold_mode=="calibrated" and not bool(self.landmark_shift.get("calibrated")):raise ValueError("calibrated mode requires a signed calibration bundle")
  return self
def _deep_merge(base,patch):
 out=deepcopy(base)
 for k,v in patch.items():out[k]=_deep_merge(out[k],v) if isinstance(v,dict) and isinstance(out.get(k),dict) else deepcopy(v)
 return out
def _settings_path(project_root:Path)->Path:
 root=Path(os.environ.get("DEEPUTIN_STATE_ROOT",str(project_root/"runs")));root.mkdir(parents=True,exist_ok=True);return root/"api_settings.json"
def load_settings(project_root:Path)->dict[str,Any]:
 p=_settings_path(project_root);stored={}
 if p.is_file():
  try:stored=json.loads(p.read_text(encoding="utf-8"))
  except (OSError,json.JSONDecodeError):stored={}
 return SettingsPayload.model_validate(_deep_merge(DEFAULT_SETTINGS,stored if isinstance(stored,dict) else {})).model_dump()
def save_settings(project_root:Path,payload:dict[str,Any])->dict[str,Any]:
 merged=_deep_merge(load_settings(project_root),payload);merged["schema"]=SETTINGS_SCHEMA;validated=SettingsPayload.model_validate(merged).model_dump();p=_settings_path(project_root);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(validated,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p);return validated
