"""
🎯 CRITICAL → Оркестратор Stage 2: формирование пар, фильтры, payload для отчёта.

ДЕТЕКЦИЯ ВЫРАЖЕНИЙ:
  Используется ТОЛЬКО геометрия ландмарок (106-точечная схема 3DDFA_V3):
  - corner_lift_ioc > EXPRESSION_CORNER_LIFT_THRESHOLD → улыбка
  - jaw_open_ratio > EXPRESSION_JAW_OPEN_THRESHOLD → открытый рот
  - Либо готовый флаг smile_detected / jaw_open_detected из info.json
  
  alpha_exp (BFM expression coefficients) НЕ ИСПОЛЬЗУЕТСЯ для QC.
  EXPRESSION_MAGNITUDE_THRESHOLD=12.0 сохранён только для обратной
  совместимости старых артефактов, но не применяется в _pair_qc_decision().

run(): load_main/load_calibration (хронология-выравненные данные), затем пары
(соседние по времени + не-соседние) с гейтами: expression (corner_lift/jaw)
и expression_pair_gate (jaw_state_mismatch → excluded внутри эпохи, страта
jaw_state_mismatch_cross_era между эпохами; порог по градусам приостановлен,
F5). alignment_quality с 2026-08-03 НЕ гейтит (D-003: некоррелирован).
Профильные бины — по 10° подбинам; pose_gap вызывается с pose_bin во всех
продакшн-путях (F1).
Далее: core-показатели, calibration, chronology rate flags, corroboration,
motion/dense-mesh/texture каналы, multiple_testing FDR, persistence результатов.
Calibration leave-one-dataset-out sensitivity и residual pose gate входят в runtime.
"""
from __future__ import annotations
import json,os,pickle,time,shutil
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from app6.stage1.utils import atomic_json,json_ready,digest_file,digest_json,write_csv
from app6.stage1.status_logger import log_status, status_warning
from .calibration import CalibrationModel
from .calibration_sensitivity import leave_one_dataset_sensitivity
from .angle_noise import build_calibration_pair_index, subtract_angle_noise
from .analysis_policy import ANALYSIS_COORDINATE_SPACE
from .expression_pair_gate import expression_gate
from .quality_stratification import quality_gate
from .visibility_gate import pair_visibility
from .space_selection import assert_analysis_space, space_manifest
from .run_manifest import build_manifest
from .core import build_coordinate_zone_map,calibrated_score,compare_landmarks
from .pair_row_patch import enrich_pair_row
from .loaders import load_calibration,load_main
from .mesh_calibration import MeshNoiseModel
from .multiple_testing import apply_pair_fdr, apply_zone_fdr
from .mesh_dense import dense_mesh_pair
from .motion import PointNoiseModel,aligned_point_motion
from .quality_integration import pair_quality_zone_overlap
from .texture_pair import summarize_texture_pairs
from .texture_image import texture_pair_deltas
from .technical_summary import build_technical_summary
from .postprocess_reports import write_postprocess_reports
from .descriptors import DescriptorNoiseModel,NAMES as DESCRIPTOR_NAMES
from .leads import load_leads,pair_leads
from .alpha_chronology import apply_alpha_chronology
from .baseline_return import apply_baseline_return
from .chronology import apply_chronology_rate_flags, apply_cumulative_drift_flags
from .temporal_axis import TEMPORAL_AXIS_SCHEMA, require_temporal_axis
from .corroboration import apply_cross_bin_corroboration, aggregate_events
from .pose_leakage import pose_leakage_diagnostic
from .metric_registry import build_metric_catalog
from .evidence import EVIDENCE_SCHEMA, evidence_state, packet_from_pair, is_reportable_change
from .validation import validate_analysis_contract
from .pair_planner import plan_pairs

SCHEMA='deeputin-stage2-v1.4-robustness'
CHECKPOINT_SCHEMA='deeputin-stage2-checkpoint-v1'
# D-003 (2026-08-03): alignment_quality некоррелирован с остатком (Spearman
# +0.096 на 212 кадрах vs −0.176 в атласе). Порог справочный, пары НЕ гейтит.
MIN_ALIGNMENT_QUALITY=0.5
# Геометрическая детекция выражений по ландмаркам (corner_lift_ioc, jaw_open_ratio).
# Пороги синхронизированы с stage1/config.py.
EXPRESSION_CORNER_LIFT_THRESHOLD=0.005
EXPRESSION_JAW_OPEN_THRESHOLD=0.28
PRIMARY_CALIBRATION_METRICS={'ldm134_rmse','ldm134_p95','identity_only_ldm134_rmse'}
PRIMARY_POSE_LEAKAGE_METRICS={'ldm134_rmse','p95_point_z','identity_only_motion_rmse'}

# 🔄 UTC-штамп для payload
def utc():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')

def _write_checkpoint(path:Path,payload:dict[str,Any])->None:
 """Atomically persist the in-progress pair accumulators."""
 tmp=path.with_name(f'{path.name}.tmp')
 with tmp.open('wb') as f:
  pickle.dump(payload,f,protocol=pickle.HIGHEST_PROTOCOL)
  f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)

def _atomic_npz(path:Path,**arrays:Any)->None:
 """Write a deterministic NPZ to a sibling temporary file, then replace."""
 tmp=path.with_name(f'{path.name}.tmp')
 with tmp.open('wb') as f:
  np.savez_compressed(f,**arrays)
  f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)

def _read_checkpoint(path:Path)->dict[str,Any]:
 with path.open('rb') as f:payload=pickle.load(f)
 if not isinstance(payload,dict) or payload.get('schema')!=CHECKPOINT_SCHEMA:raise RuntimeError(f'invalid Stage 2 checkpoint: {path}')
 return payload

def _record_qc(record)->dict[str,Any]:
 """Load mandatory Stage 1 QC (geometry-based expression detection)."""
 path=Path(record.record_dir)/'info.json' if record.record_dir else None
 result={'status':'missing_qc','alignment_quality':None,'reason':'info_json_missing'}
 result.update({'corner_lift_ioc':None,'jaw_open_ratio':None,'smile_detected':False,'jaw_open_detected':False,'jaw_open_degree':None,'detection_confidence':None,'face_area_ratio':None,'skin_quality_score':None})
 if path is None or not path.is_file():return result
 try:payload=json.loads(path.read_text(encoding='utf-8'))
 except (OSError,json.JSONDecodeError) as exc:
  result['reason']=f'info_json_invalid:{type(exc).__name__}';return result
 chronology=payload.get('chronology')
 if not isinstance(chronology,dict):result['reason']='chronology_missing';return result
 try:alignment=float(chronology['alignment_quality'])
 except (KeyError,TypeError,ValueError):result['reason']='alignment_quality_missing';return result
 if not np.isfinite(alignment):result['reason']='alignment_quality_nonfinite';return result
 if not 0.0<=alignment<=1.0:result['reason']='alignment_quality_out_of_range';return result
 # Геометрические метрики выражений (опционально — для новых фото)
 corner=chronology.get('corner_lift_ioc')
 jaw=chronology.get('jaw_open_ratio')
 smile_d=chronology.get('smile_detected',False)
 jaw_d=chronology.get('jaw_open_detected',False)
 result.update({
  'status':'available',
  'alignment_quality':alignment,
  'corner_lift_ioc':float(corner) if corner is not None else None,
  'jaw_open_ratio':float(jaw) if jaw is not None else None,
  'smile_detected':False if smile_d in (None,'') else (smile_d if isinstance(smile_d,bool) else str(smile_d).strip().lower() in {'true','1','yes'}),
  'jaw_open_detected':False if jaw_d in (None,'') else (jaw_d if isinstance(jaw_d,bool) else str(jaw_d).strip().lower() in {'true','1','yes'}),
  'jaw_open_degree':float(chronology['jaw_open_degree']) if chronology.get('jaw_open_degree') is not None else None,
  'detection_confidence':float(chronology['detection_confidence']) if chronology.get('detection_confidence') is not None else None,
  'face_area_ratio':float(chronology['face_area_ratio']) if chronology.get('face_area_ratio') is not None else None,
  'skin_quality_score':float(payload['skin_quality_score']) if payload.get('skin_quality_score') is not None else None,
  'reason':'',
 })
 return result

def _pair_qc_decision(a,b,qc_by_id:dict[str,dict[str,Any]],
                      corner_threshold:float|None=EXPRESSION_CORNER_LIFT_THRESHOLD,
                      jaw_threshold:float|None=EXPRESSION_JAW_OPEN_THRESHOLD)->dict[str,Any]:
 """Return a deterministic fail-closed applicability decision for one pair.
 
 ДЕТЕКЦИЯ ВЫРАЖЕНИЙ — только через геометрию ландмарок (не alpha_exp):
   1. smile_detected / jaw_open_detected — готовые флаги из info.json
   2. corner_lift_ioc > corner_threshold (0.005) — подъём уголков = улыбка
   3. jaw_open_ratio > jaw_threshold (0.28) — раскрытие рта
   
   Пара исключается (applicable=False), если ХОТЯ БЫ ОДНО фото в паре
   содержит выражение. Это fail-closed: сомнительные пары не анализируем.
   
   Если порог=None, соответствующая проверка отключена.
 """
 missing={'status':'missing_qc','alignment_quality':None,'corner_lift_ioc':None,'jaw_open_ratio':None,'reason':'qc_not_loaded'}
 qa=qc_by_id.get(a.record_id,missing);qb=qc_by_id.get(b.record_id,missing)
 base={
  'alignment_quality_a':qa.get('alignment_quality'),'alignment_quality_b':qb.get('alignment_quality'),
  'corner_lift_ioc_a':qa.get('corner_lift_ioc'),'corner_lift_ioc_b':qb.get('corner_lift_ioc'),
  'jaw_open_ratio_a':qa.get('jaw_open_ratio'),'jaw_open_ratio_b':qb.get('jaw_open_ratio'),
  'smile_detected_a':qa.get('smile_detected',False),'smile_detected_b':qb.get('smile_detected',False),
  'jaw_open_detected_a':qa.get('jaw_open_detected',False),'jaw_open_detected_b':qb.get('jaw_open_detected',False),
  }
 if qa.get('status')!='available' or qb.get('status')!='available':
  return {**base,'applicable':False,'skip_reason':'missing_mandatory_qc','qc_reason_a':qa.get('reason'),'qc_reason_b':qb.get('reason')}
 return {**base,'applicable':True,'skip_reason':'',
         'qc_reason_a':'','qc_reason_b':'',
         'corner_threshold':corner_threshold,'jaw_threshold':jaw_threshold}

@dataclass(frozen=True)
class Stage2Config:
 stage1_root:Path;calibration_root:Path;output_dir:Path;overwrite:bool=False;min_points106:int=24;min_points134:int=30;lead_archive:Path|None=None;checkpoint_every:int=0;resume:bool=False
 # 🏭 FACTORY → сборка итогового payload прогона
 def payload(self):return {'schema':SCHEMA,'min106':self.min_points106,'min134':self.min_points134,'calibration':'equal-person-balanced-reference-v1','visibility_policy':'intersection_fail_closed_v1','cross_pose_policy':'reject_before_score_v1','noise_policy':'explicit_sigma_only_v1','chronology_policy':'adjacent_plus_anchor_plus_cusum_v1','lead_policy':'coverage_only_not_threshold_tuning','descriptor_families':list(DESCRIPTOR_NAMES)}

 def __post_init__(self):
  if self.min_points106 < 8 or self.min_points134 < 8:raise ValueError('min_points must be >= 8')
  if self.checkpoint_every < 0:raise ValueError('checkpoint_every must be >= 0')
  output=Path(self.output_dir).resolve()
  for source,name in ((self.stage1_root,'stage1_root'),(self.calibration_root,'calibration_root')):
   source=Path(source).resolve()
   if output==source or source in output.parents:raise ValueError(f'output_dir must not equal or be inside {name}')

class Stage2Engine:
 def __init__(self,cfg):self.cfg=cfg
 def run(self):
  """🎯 CRITICAL → Полный анализ Stage 2 (сравнение пар, хронология, калибровка).

  Проходит по всем парам фото внутри pose bins:
  1. Сравнение ландмарков (compare_landmarks)
  2. Point motion analysis (aligned_point_motion)
  3. Descriptor analysis (shape families)
  4. Mesh comparison (dense_mesh_pair)
  5. Texture comparison (texture_pair_deltas)
  6. Chronology rate flags (apply_chronology_rate_flags)
  7. Cross-bin corroboration (apply_cross_bin_corroboration)
  8. Multiple testing correction (FDR)

  🔗 DEPENDS ON:
    - load_main() — загрузка Stage 1 данных
    - load_calibration() — калибровочная модель
    - compare_landmarks() — ядро сравнения

  APPLICABILITY:
    - Primary geometry использует raw object-normalized landmarks; chronology-aligned
      arrays остаются диагностическим каналом и не подменяют primary comparison.
    - Фильтрует по alignment quality, expression и residual pose distance.
    - Пишет leave-one-dataset-out sensitivity калибровки в runtime-артефакты.

  💡 NOTE:
    - Пары только внутри одного pose bin (adjacent + baseline)
    - Calibration noise из 7 same-person datasets
    - FDR correction для multiple testing

  🚨 WARNING:
    - При отсутствии калибровочных данных — ошибка
    - При большом количестве пар — медленно (FDR)
  """
  log_status("run", "complete")
  assert_analysis_space(ANALYSIS_COORDINATE_SPACE)
  t=time.time();o=self.cfg.output_dir
  checkpoint_path=o/'stage2_checkpoint.pkl'
  if o.exists() and any(o.iterdir()) and not self.cfg.overwrite and not self.cfg.resume:raise FileExistsError(f'output exists: {o}')
  if self.cfg.resume and not checkpoint_path.is_file():raise FileNotFoundError(f'Stage 2 checkpoint not found: {checkpoint_path}')
  # Load and construct every read-only dependency before destructive overwrite.
  main=load_main(self.cfg.stage1_root);cal=load_calibration(self.cfg.calibration_root);leads=load_leads(self.cfg.lead_archive)
  if not main:raise RuntimeError('no valid stage1 records')
  from .primary_zones import build_anatomical_landmark_zone_map as _build_anat_zones
  z106_coord,m106_coord=build_coordinate_zone_map(cal,106);z134_coord,m134_coord=build_coordinate_zone_map(cal,134)
  z106,m106=_build_anat_zones(list(cal)+list(main),106);z134,m134=_build_anat_zones(list(cal)+list(main),134)
  if m134.get('status')!='ok':z106,m106,z134,m134=z106_coord,m106_coord,z134_coord,m134_coord
  model=CalibrationModel(cal,z106,z134);point_model=PointNoiseModel(cal);descriptor_model=DescriptorNoiseModel(cal);mesh_model=MeshNoiseModel(cal)
  # Differential pose-angle noise is a production input, not a standalone audit helper.
  # Build it once from same-person/same-bin calibration pairs and annotate every
  # measured main pair below. Missing matches remain explicitly uncompensated.
  angle_noise_pairs=build_calibration_pair_index(cal,compare_landmarks,z106,z134)
  if o.exists() and self.cfg.overwrite:
   for child in o.iterdir():
    try:
     shutil.rmtree(child) if child.is_dir() else child.unlink()
    except FileNotFoundError:
     pass
  o.mkdir(parents=True,exist_ok=True)
  atomic_json(o/'zone_map.json',{'schema':'primary-hypothesis-zone-map-v1','ldm106':z106,'ldm134':z134,'ldm106_meta':m106,'ldm134_meta':m134})
  atomic_json(o/'calibration_noise_model.json',{'schema':'calibration-noise-v2-balanced','policy':'equal_person_median_of_quantiles_v1','datasets':model.datasets,'record_count':len(cal),'references':model.references})
  calibration_sensitivity=leave_one_dataset_sensitivity(cal,z106,z134)
  atomic_json(o/'calibration_sensitivity.json',calibration_sensitivity)
  atomic_json(o/'mesh_noise_model.json',mesh_model.to_json())
  atomic_json(o/'lead_registry.json',leads);write_csv(o/'lead_coverage.csv',leads.get('coverage') or [{'legacy_metric':'none','coverage':'not_provided'}])
  point_payload={}
  for (pose,count),ref in point_model.references.items():
   prefix=f'{pose}__ldm{count}';point_payload[f'{prefix}__median']=ref.median;point_payload[f'{prefix}__mad']=ref.mad;point_payload[f'{prefix}__p95']=ref.p95;point_payload[f'{prefix}__count']=ref.count;point_payload[f'{prefix}__template']=ref.template
  _atomic_npz(o/'point_noise_model.npz',**point_payload)
  descriptor_payload={'metric_names':np.asarray(DESCRIPTOR_NAMES)}
  for pose,ref in descriptor_model.refs.items():
   descriptor_payload[f'{pose}__median']=ref.median;descriptor_payload[f'{pose}__mad']=ref.mad;descriptor_payload[f'{pose}__p95']=ref.p95;descriptor_payload[f'{pose}__count']=ref.count;descriptor_payload[f'{pose}__template']=ref.template
  _atomic_npz(o/'descriptor_noise_model.npz',**descriptor_payload)
  motion_dir=o/'point_motion';motion_dir.mkdir(exist_ok=True)
  groups=defaultdict(list)
  for r in main:groups[r.pose_bin].append(r)
  qc_by_id={r.record_id:_record_qc(r) for r in main}
  alignment_quality={rid:q.get('alignment_quality') for rid,q in qc_by_id.items()}
  corner_lift_ioc={rid:q.get('corner_lift_ioc') for rid,q in qc_by_id.items()}
  jaw_open_ratio={rid:q.get('jaw_open_ratio') for rid,q in qc_by_id.items()}
  smile_detected={rid:q.get('smile_detected',False) for rid,q in qc_by_id.items()}
  jaw_open_detected={rid:q.get('jaw_open_detected',False) for rid,q in qc_by_id.items()}
  jaw_open_degree={rid:q.get('jaw_open_degree') for rid,q in qc_by_id.items()}
  detection_confidence={rid:q.get('detection_confidence') for rid,q in qc_by_id.items()}
  face_area_ratio={rid:q.get('face_area_ratio') for rid,q in qc_by_id.items()}
  skin_quality_score={rid:q.get('skin_quality_score') for rid,q in qc_by_id.items()}
  unstable_calibration=[x for x in calibration_sensitivity.get('summary',[]) if x.get('stability')!='stable']
  if calibration_sensitivity.get('status')!='complete':status_warning('calibration_stability',str(calibration_sensitivity.get('status')))
  elif unstable_calibration:status_warning('calibration_stability',f'{len(unstable_calibration)} unstable_or_sparse pose/metric references')
  else:log_status('calibration_stability','complete')
  # Temporal neighbours are retained for later chronology diagnostics.
  temporal_context={}
  for _,records in groups.items():
   records_sorted=sorted(records,key=lambda r:(r.date or '9999',r.sequence))
   for i,r in enumerate(records_sorted):
    prev_rec=records_sorted[i-1] if i>0 else None;next_rec=records_sorted[i+1] if i<len(records_sorted)-1 else None
    temporal_context[r.record_id]={'prev_record_id':prev_rec.record_id if prev_rec else None,'next_record_id':next_rec.record_id if next_rec else None,'prev_date':prev_rec.date if prev_rec else None,'next_date':next_rec.date if next_rec else None,'index_in_pose_bin':i,'total_in_pose_bin':len(records_sorted)}
  specs=[];skipped_pair_rows=[];skipped_counts=defaultdict(int)
  missing_qc_record_count=sum(q.get('status')!='available' for q in qc_by_id.values())
  if missing_qc_record_count:status_warning('mandatory_qc',f'{missing_qc_record_count} records are fail-closed')
  for pose,rs in sorted(groups.items()):
   rs.sort(key=lambda x:(x.date or '9999',x.sequence,x.record_id))
   candidates=plan_pairs(rs)
   for ptype,a,b in candidates:
    decision=_pair_qc_decision(a,b,qc_by_id)
    if not decision['applicable']:
     skipped_counts[decision['skip_reason']]+=1
     skipped_pair_rows.append({'pair_type':ptype,'pose_bin':pose,'photo_a':a.record_id,'photo_b':b.record_id,'date_a':a.date,'date_b':b.date,**decision})
     continue
    specs.append((ptype,a,b,decision))
  rows=[];zones=[];details=[];quality_zone_rows=[];texture_zone_rows=[];mesh_rows=[];mesh_zones=[];anchor_policy_by_bin={};expr_gate_summary={'pairs':0,'accepted':0}
  spec_ids=[f'{ptype}__{a.record_id}__{b.record_id}' for ptype,a,b,_ in specs]
  checkpoint_signature={'schema':SCHEMA,'stage1_manifest_digest':digest_file(self.cfg.stage1_root/'stage1_manifest.json'),'calibration_root':str(Path(self.cfg.calibration_root).resolve()),'main_record_ids':[r.record_id for r in main],'spec_ids':spec_ids,'config_hash':digest_json(self.cfg.payload())}
  processed_pair_ids=set()
  if self.cfg.resume:
   checkpoint=_read_checkpoint(checkpoint_path)
   if checkpoint.get('signature')!=checkpoint_signature:raise RuntimeError('Stage 2 checkpoint does not match current Stage 1, calibration, or analysis configuration')
   rows=checkpoint['rows'];zones=checkpoint['zones'];details=checkpoint['details'];quality_zone_rows=checkpoint['quality_zone_rows'];texture_zone_rows=checkpoint['texture_zone_rows'];mesh_rows=checkpoint['mesh_rows'];mesh_zones=checkpoint['mesh_zones'];anchor_policy_by_bin=checkpoint['anchor_policy_by_bin'];expr_gate_summary=checkpoint['expr_gate_summary'];processed_pair_ids=set(checkpoint['processed_pair_ids'])
   log_status('checkpoint_resume',f'{len(processed_pair_ids)}/{len(specs)} pairs restored')
  for n,(ptype,a,b,qc_decision) in enumerate(specs,1):
   pid=f'{ptype}__{a.record_id}__{b.record_id}'
   if pid in processed_pair_ids:continue
   meta_a={'detection_confidence':detection_confidence.get(a.record_id),'skin_quality_score':skin_quality_score.get(a.record_id),'face_area_ratio':face_area_ratio.get(a.record_id)}
   meta_b={'detection_confidence':detection_confidence.get(b.record_id),'skin_quality_score':skin_quality_score.get(b.record_id),'face_area_ratio':face_area_ratio.get(b.record_id)}
   expr_gate=expression_gate({**meta_a,'jaw_open_detected':jaw_open_detected.get(a.record_id,False),'jaw_open_degree':jaw_open_degree.get(a.record_id),'smile_detected':smile_detected.get(a.record_id,False)},{**meta_b,'jaw_open_detected':jaw_open_detected.get(b.record_id,False),'jaw_open_degree':jaw_open_degree.get(b.record_id),'smile_detected':smile_detected.get(b.record_id,False)},era_a=(str(a.date)[:4] if a.date else None),era_b=(str(b.date)[:4] if b.date else None))
   expr_gate_summary['pairs']+=1
   if expr_gate.get('accepted'):expr_gate_summary['accepted']+=1
   q_gate=quality_gate(meta_a,meta_b)
   c=compare_landmarks(a,b,z106,z134,self.cfg.min_points106,self.cfg.min_points134);matched=model.matched_null(a,b) if c.status=='measured' else {};scores={}
   if c.diagnostics.get('anchor134_policy'):
    _ap_entry=anchor_policy_by_bin.setdefault(a.pose_bin,{'pairs':0,'policies':{},'sources':{}});_ap_entry['pairs']+=1;_ap_p=c.diagnostics.get('anchor134_policy') or 'unknown';_ap_s=c.diagnostics.get('anchor134_source') or 'unknown';_ap_entry['policies'][_ap_p]=_ap_entry['policies'].get(_ap_p,0)+1;_ap_entry['sources'][_ap_s]=_ap_entry['sources'].get(_ap_s,0)+1
   pair_sigma=max(float(getattr(a,'coordinate_noise_sigma',0.0) or 0.0),float(getattr(b,'coordinate_noise_sigma',0.0) or 0.0))
   vis134=pair_visibility(a.visible134,b.visible134,contract='ldm134');vis106=pair_visibility(a.visible106,b.visible106,contract='ldm106')
   stratum_arg=q_gate.get('stratum') if model.has_stratified_references() else None
   for k,v in c.metrics.items():scores[k]=calibrated_score(v,model.reference(a.pose_bin,k,stratum=stratum_arg),matched.get(k,[]),coordinate_noise_sigma=pair_sigma)
   primary=scores.get('ldm134_rmse',{'status':c.status,'robust_z':0,'calibration_p95':0});status=str(primary['status']) if c.status=='measured' else c.status
   motion106=aligned_point_motion(a,b,106);motion134=aligned_point_motion(a,b,134);motion_score106=point_model.score(a.pose_bin,106,motion106);motion_score134=point_model.score(a.pose_bin,134,motion134);descriptor_score=descriptor_model.score(a.pose_bin,a,b)
   identity_motion=aligned_point_motion(a,b,134,identity_only=True)
   identity_rmse=float(np.sqrt(np.nanmean(np.asarray(identity_motion['magnitude'])**2))) if identity_motion['status']=='measured' else float('nan')
   full_rmse=float(np.sqrt(np.nanmean(np.asarray(motion134['magnitude'])**2))) if motion134['status']=='measured' else float('nan')
   # ⚠️ FIX: Prevent division by zero when full_rmse is 0 or NaN
   # If full_rmse is 0, both photos are identical (no motion)
   # If full_rmse is NaN, motion couldn't be measured
   if not np.isfinite(full_rmse) or full_rmse < 1e-8:
       expression_influence = 0.0
   elif not np.isfinite(identity_rmse):
       expression_influence = 0.0
   else:
       expression_influence = float(max(0., 1. - identity_rmse / full_rmse))
   if c.status=='measured':status=motion_score134['status']
   if descriptor_score['status']=='descriptor_jump_candidate' and status in ('within_reconstruction_noise','scattered_or_uncertain'):status='coherent_jump_candidate'
   safe_pid=pid.replace('/','_');_atomic_npz(motion_dir/f'{safe_pid}.npz',ldm106_vectors=motion106['vectors'],ldm106_magnitude=motion106['magnitude'],ldm106_point_z=motion_score106['z'],ldm106_significant=motion_score106['significant'],ldm134_vectors=motion134['vectors'],ldm134_magnitude=motion134['magnitude'],ldm134_point_z=motion_score134['z'],ldm134_significant=motion_score134['significant'],ldm134_identity_only_vectors=identity_motion['vectors'],ldm134_identity_only_magnitude=identity_motion['magnitude'],descriptor_names=np.asarray(DESCRIPTOR_NAMES),descriptor_values=descriptor_score['values'],descriptor_z=descriptor_score['z'],descriptor_significant=descriptor_score['significant'])
   ms=motion_score134['summary'];ds=descriptor_score['summary'];lead=pair_leads(leads,a.date,b.date);mesh_row,mesh_zone_list=dense_mesh_pair(a,b,o,pid);texture_row,texture_zone_list=texture_pair_deltas(a,b,pid);texture_zone_rows.extend(texture_zone_list);mesh_score=mesh_model.score(a.pose_bin,mesh_row);mesh_row.update(mesh_score);mesh_rows.append({'pair_id':pid,'pair_type':ptype,'pose_bin':a.pose_bin,'photo_a':a.record_id,'photo_b':b.record_id,**mesh_row});mesh_zones.extend(mesh_zone_list)
   angle_adjusted=subtract_angle_noise({'pose_bin':a.pose_bin,'angles_a':a.angles,'angles_b':b.angles,**c.metrics},angle_noise_pairs)
   angle_fields={k:v for k,v in angle_adjusted.items() if k.startswith('angle_') or k.endswith('_angle_compensated') or k.endswith('_angle_noise')}
   row={'pair_id':pid,'pair_index':n,'pair_type':ptype,'pose_bin':a.pose_bin,'photo_a':a.record_id,'photo_b':b.record_id,'date_a':a.date,'date_b':b.date,**angle_fields,'source_group_a':a.source_group,'source_group_b':b.source_group,'source_digest_a':a.source_digest,'source_digest_b':b.source_digest,'analysis_space':a.analysis_space,'date_provenance_status_a':a.date_provenance_status,'date_provenance_status_b':b.date_provenance_status,'exif_date_a':a.exif_date,'exif_date_b':b.exif_date,'date_delta_days_a':a.date_delta_days,'date_delta_days_b':b.date_delta_days,'source_claimed_date_a':a.source_claimed_date,'source_claimed_date_b':b.source_claimed_date,'source_claimed_delta_days_a':a.source_claimed_delta_days,'source_claimed_delta_days_b':b.source_claimed_delta_days,'date_conflict_sources_a':a.date_conflict_sources,'date_conflict_sources_b':b.date_conflict_sources,'date_provenance_limited':bool(a.date_provenance_status=='conflict' or b.date_provenance_status=='conflict'),'near_duplicate_of_a':a.near_duplicate_of,'near_duplicate_of_b':b.near_duplicate_of,'near_duplicate_pair':bool(a.near_duplicate_of or b.near_duplicate_of),'source_provenance_status_a':a.source_provenance.get('status','not_provided'),'source_provenance_status_b':b.source_provenance.get('status','not_provided'),'source_url_a':a.source_provenance.get('source_url'),'source_url_b':b.source_provenance.get('source_url'),'archive_url_a':a.source_provenance.get('archive_url'),'archive_url_b':b.source_provenance.get('archive_url'),'alignment_quality_a':alignment_quality.get(a.record_id),'alignment_quality_b':alignment_quality.get(b.record_id),'corner_lift_ioc_a':corner_lift_ioc.get(a.record_id),'corner_lift_ioc_b':corner_lift_ioc.get(b.record_id),'jaw_open_ratio_a':jaw_open_ratio.get(a.record_id),'jaw_open_ratio_b':jaw_open_ratio.get(b.record_id),'smile_detected_a':smile_detected.get(a.record_id),'smile_detected_b':smile_detected.get(b.record_id),'jaw_open_detected_a':jaw_open_detected.get(a.record_id),'jaw_open_detected_b':jaw_open_detected.get(b.record_id),'expression_source':'geometry_landmarks_v1','qc_skip_reason':qc_decision.get('skip_reason',''),'status':status,'motion_file':f'point_motion/{safe_pid}.npz',**mesh_row,**texture_row,'point_motion_status':motion_score134['status'],'ldm134_anchor_count':motion134.get('anchor_count',0),'ldm134_anchor_policy':motion134.get('anchor_policy','unknown'),'ldm134_alignment_policy':motion134.get('alignment_policy','unknown'),'ldm134_alignment_trimmed_count':motion134.get('alignment_trimmed_count',0),'ldm106_anchor_count':motion106.get('anchor_count',0),'ldm106_anchor_policy':motion106.get('anchor_policy','unknown'),'descriptor_status':descriptor_score['status'],'descriptor_significant_fraction':ds.get('significant_cell_fraction',0.),'descriptor_landmark_fraction':ds.get('significant_landmark_fraction',0.),'descriptor_p95_z':ds.get('p95_descriptor_z',0.),'descriptor_top_families':ds.get('top_descriptor_families',''),'descriptor_top_counts':ds.get('top_descriptor_counts',''),'calibrated_point_count':ms.get('calibrated_point_count',0),'significant_point_count':ms.get('significant_point_count',0),'significant_point_fraction':ms.get('significant_fraction',0.),'coherent_motion_fraction':ms.get('coherent_fraction',0.),'median_point_z':ms.get('median_point_z',0.),'p95_point_z':ms.get('p95_point_z',0.),'identity_only_motion_rmse':identity_rmse,'expression_influence':expression_influence,**lead,**c.diagnostics,**c.metrics,'primary_robust_z':float(primary.get('robust_z',0)),'primary_calibration_p95':float(primary.get('calibration_p95',0)),'matched_calibration_sets':len(matched.get('ldm134_rmse',[]))}
   qmin = min(float(getattr(a, 'quality_texture_score', 0.0) or 0.0), float(getattr(b, 'quality_texture_score', 0.0) or 0.0))
   qzone_summary,qzone_pair_rows=pair_quality_zone_overlap(a,b,pid)
   quality_zone_rows.extend(qzone_pair_rows)
   qlimited = bool(qmin < 0.35 or qzone_summary.get('quality_zone_pair_limited') or str(getattr(a, 'quality_status', 'unknown')) in ('weak_or_insufficient','unknown') or str(getattr(b, 'quality_status', 'unknown')) in ('weak_or_insufficient','unknown'))
   row.update({
    **qzone_summary,
    'quality_status_a': getattr(a, 'quality_status', 'unknown'),
    'quality_status_b': getattr(b, 'quality_status', 'unknown'),
    'quality_texture_score_a': float(getattr(a, 'quality_texture_score', 0.0) or 0.0),
    'quality_texture_score_b': float(getattr(b, 'quality_texture_score', 0.0) or 0.0),
    'quality_limited': qlimited,
'forehead_wrinkle_supported_a': bool(getattr(a, 'forehead_wrinkle_supported', False)),
   'forehead_wrinkle_supported_b': bool(getattr(b, 'forehead_wrinkle_supported', False)),
   })
   row.update({'expression_gate_multiplier':expr_gate.get('threshold_multiplier'),'expression_gate_jaw_mismatch':expr_gate.get('jaw_mismatch'),'expression_gate_smile_mismatch':expr_gate.get('smile_mismatch'),'expression_gate_jaw_degree_gap':expr_gate.get('jaw_degree_gap'),'expression_gate_confidence':expr_gate.get('confidence'),'expression_gate_stratum':expr_gate.get('stratum'),'expression_gate_jaw_degree_gap_exceeded':expr_gate.get('jaw_degree_gap_exceeded'),'quality_stratum_a':q_gate.get('stratum_a'),'quality_stratum_b':q_gate.get('stratum_b'),'quality_stratum':q_gate.get('stratum'),'quality_calibration_key_suffix':q_gate.get('calibration_key_suffix'),'quality_threshold_multiplier':q_gate.get('threshold_multiplier'),'quality_gate_accepted':q_gate.get('accepted'),'visibility_gate_common134':vis134.get('common'),'visibility_gate_required134':vis134.get('required'),'visibility_gate_accepted134':vis134.get('accepted'),'visibility_gate_common106':vis106.get('common'),'visibility_gate_required106':vis106.get('required'),'visibility_gate_accepted106':vis106.get('accepted')})
   dpl = row.get('date_provenance_limited')
   if isinstance(dpl, str):
       dpl = dpl.strip().lower() in ('true', '1', 'yes')
   row['evidence_state']=('date_provenance_limited' if dpl else ('near_duplicate_limited' if row.get('near_duplicate_pair') and status not in ('within_reconstruction_noise','within_calibration_noise') else evidence_state(str(row.get('status','')),quality_limited=qlimited)))
   row=enrich_pair_row(row,zones=c.zones,record_a=a,record_b=b,qc_a=qc_by_id.get(a.record_id,{}),qc_b=qc_by_id.get(b.record_id,{}),smile_a=bool(smile_detected.get(a.record_id)),smile_b=bool(smile_detected.get(b.record_id)),jaw_a=bool(jaw_open_detected.get(a.record_id)),jaw_b=bool(jaw_open_detected.get(b.record_id)))
   rows.append(row)
   for z in c.zones:
    zr={'pair_id':pid,'pair_type':ptype,'pose_bin':a.pose_bin,'photo_a':a.record_id,'photo_b':b.record_id,**z}
    if z.get('status')=='measured':
     k=f"zone::{z['zone']}::rmse";s=calibrated_score(float(z['rmse']),model.reference(a.pose_bin,k,stratum=stratum_arg),matched.get(k,[]),coordinate_noise_sigma=pair_sigma);zr.update({'calibration_status':s['status'],'robust_z':s['robust_z'],'calibration_p95':s['calibration_p95']})
    zones.append(zr)
   details.append({'pair':row,'calibrated_metrics':scores,'zones':c.zones})
   processed_pair_ids.add(pid)
   if self.cfg.checkpoint_every and len(processed_pair_ids)%self.cfg.checkpoint_every==0:
    _write_checkpoint(checkpoint_path,{'schema':CHECKPOINT_SCHEMA,'signature':checkpoint_signature,'processed_pair_ids':sorted(processed_pair_ids),'rows':rows,'zones':zones,'details':details,'quality_zone_rows':quality_zone_rows,'texture_zone_rows':texture_zone_rows,'mesh_rows':mesh_rows,'mesh_zones':mesh_zones,'anchor_policy_by_bin':anchor_policy_by_bin,'expr_gate_summary':expr_gate_summary})
    log_status('checkpoint',f'{len(processed_pair_ids)}/{len(specs)} pairs persisted')
  self._persistence(rows)
  # 🚧 Патч 14: без временной оси (калибровка, единичная дата) временные
  # детекторы не запускаются вовсе, а в отчёт идёт явный skip-статус.
  temporal_axis = require_temporal_axis(main)
  if temporal_axis is None:
      alpha_chronology_report=apply_alpha_chronology(rows,model)
      baseline_return_report=apply_baseline_return(rows,o)
      chronology_refs=apply_chronology_rate_flags(rows)
      cumulative_drift_report=apply_cumulative_drift_flags(rows)
  else:
      _temporal_skip = {"schema": TEMPORAL_AXIS_SCHEMA,
                        "status": "skipped_no_temporal_axis",
                        "reason": "dataset has no validated evidence time axis",
                        "temporal_axis": None}
      alpha_chronology_report = _temporal_skip
      baseline_return_report = _temporal_skip
      chronology_refs = _temporal_skip
      cumulative_drift_report = _temporal_skip
  cross_bin_report=apply_cross_bin_corroboration(rows)
  event_rows=aggregate_events(rows)
  # Глобальный диагноз утечки позы — для информации
  pose_leakage_report=pose_leakage_diagnostic(rows)
  multiple_testing_report={'pair_fdr':apply_pair_fdr(rows,photo_count=len(main)),'zone_fdr':apply_zone_fdr(zones)}
  unstable_poses={str(x.get('pose_bin')) for x in unstable_calibration if x.get('pose_bin') and str(x.get('metric')) in PRIMARY_CALIBRATION_METRICS}
  sensitivity_incomplete=calibration_sensitivity.get('status')!='complete'
  primary_pose_leakage_metrics=sorted(set(pose_leakage_report.get('flagged_metrics',[])) & PRIMARY_POSE_LEAKAGE_METRICS)
  global_pose_leakage_flagged=bool(primary_pose_leakage_metrics)
  # ⚡ Per-pair pose leakage: блокируем только те пары, где поза действительно
  # разная (pose_distance > 1.0). Если обе фото в анфас или близком ракурсе —
  # утечка позы не имеет значения, метрики считаются.
  POSE_LEAKAGE_DISTANCE_THRESHOLD=1.0
  for r in rows:
   r['calibration_limited']=bool(sensitivity_incomplete or str(r.get('pose_bin')) in unstable_poses)
   r['calibration_limitation_reason']='sensitivity_incomplete' if sensitivity_incomplete else ('unstable_or_sparse_pose_reference' if r['calibration_limited'] else '')
   r['pose_leakage_limited']=global_pose_leakage_flagged and (float(r.get('pose_distance',999))>POSE_LEAKAGE_DISTANCE_THRESHOLD)
   r['evidence_state']=evidence_state(str(r.get('status','')),quality_limited=bool(r.get('quality_limited')),calibration_limited=r['calibration_limited'],pose_leakage_limited=r['pose_leakage_limited'])
  states={r['pair_id']:r['status'] for r in rows}
  evidence_states={r['pair_id']:r['evidence_state'] for r in rows}
  for d in details:
   d['pair']['status']=states[d['pair']['pair_id']]
   d['pair']['evidence_state']=evidence_states[d['pair']['pair_id']]
  texture_pair_rows=summarize_texture_pairs(quality_zone_rows)
  tex_by_pair={r['pair_id']:r for r in texture_pair_rows if r.get('pair_id')}
  for r in rows:
   if r.get('pair_id') in tex_by_pair:r.update(tex_by_pair[r['pair_id']])
  metric_catalog=build_metric_catalog(rows)
  evidence_packets=[packet_from_pair(r) for r in rows]
  changes=[{'pair_id':r['pair_id'],'pair_type':r['pair_type'],'pose_bin':r['pose_bin'],'date':r['date_b'],'photo_a':r['photo_a'],'photo_b':r['photo_b'],'status':r.get('evidence_state',''),'measurement_status':r['status'],'evidence_state':r.get('evidence_state',''),'p95_point_z':r.get('p95_point_z',0),'significant_point_fraction':r.get('significant_point_fraction',0),'coherent_motion_fraction':r.get('coherent_motion_fraction',0),'days_delta':r.get('days_delta',-1),'chronology_rate_status':r.get('chronology_rate_status',''),'chronology_rate_z':r.get('chronology_rate_z',0.0),'cross_bin_corroboration_status':r.get('cross_bin_corroboration_status',''),'cross_bin_support_pose_count':r.get('cross_bin_support_pose_count',0)} for r in rows if is_reportable_change(r)]
  # Persist every computed stage transformation before final post-processing.
  # Previously these values existed only in memory, so validation truthfully
  # rejected the manifest as incomplete after an otherwise successful analysis.
  atomic_json(o/'chronology_rate_model.json',{'schema':'deeputin-stage2-chronology-rate-model-v1.0','references':chronology_refs})
  atomic_json(o/'alpha_chronology.json',alpha_chronology_report)
  write_csv(o/'alpha_chronology_events.csv',alpha_chronology_report.get('events') or [{'status':alpha_chronology_report.get('status','no_events')}])
  atomic_json(o/'baseline_return.json',baseline_return_report)
  atomic_json(o/'cumulative_drift.json',cumulative_drift_report)
  atomic_json(o/'cross_bin_corroboration.json',cross_bin_report)
  write_csv(o/'event_aggregation.csv',event_rows or [{'status':'no_events'}])
  atomic_json(o/'pose_leakage_diagnostic.json',pose_leakage_report)
  atomic_json(o/'multiple_testing.json',multiple_testing_report)
  atomic_json(o/'metric_catalog.json',metric_catalog)
  atomic_json(o/'change_points.json',{'schema':'deeputin-stage2-change-points-v1.0','change_points':changes})
  # pair_details.json, evidence_packets.json, evidence_packets.jsonl, mesh_zone_metrics.csv
  # removed to reduce storage; UI uses pair_metrics.csv + zone_metrics.csv instead
  write_csv(o/'pair_metrics.csv',rows or [{'status':'no_pairs'}]);write_csv(o/'skipped_pairs.csv',skipped_pair_rows or [{'status':'no_skipped_pairs'}]);write_csv(o/'zone_metrics.csv',zones or [{'status':'no_zones'}]);write_csv(o/'quality_zone_pair_coverage.csv',quality_zone_rows or [{'status':'no_quality_zone_pairs'}]);write_csv(o/'texture_pair_metrics.csv',texture_pair_rows or [{'status':'no_texture_pairs'}]);write_csv(o/'texture_zone_metrics.csv',texture_zone_rows or [{'status':'no_texture_zone_metrics'}]);write_csv(o/'mesh_pair_metrics.csv',mesh_rows or [{'status':'no_mesh_pairs'}])
  postprocess_summary=write_postprocess_reports(o,rows=rows,zones=zones,mesh_zones=mesh_zones,texture_zone_rows=texture_zone_rows,changes=changes,evidence_packets=evidence_packets)
  pd=o/'photo_analysis';pd.mkdir(exist_ok=True)
  for r in main:atomic_json(pd/f'{r.record_id}.json',{'schema':SCHEMA,'photo_id':r.record_id,'date':r.date,'pose_bin':r.pose_bin,'related_pairs':[x for x in rows if r.record_id in (x['photo_a'],x['photo_b'])]})
  postprocess_summary=write_postprocess_reports(o,rows=rows,zones=zones,mesh_zones=mesh_zones,texture_zone_rows=texture_zone_rows,changes=changes,evidence_packets=evidence_packets)
  artifact_names=['pair_metrics.csv','zone_metrics.csv','quality_zone_pair_coverage.csv','texture_pair_metrics.csv','texture_zone_metrics.csv','mesh_pair_metrics.csv','multiple_testing.json','alpha_chronology.json','baseline_return.json','cumulative_drift.json','cross_bin_corroboration.json','event_aggregation.csv','pose_leakage_diagnostic.json','metric_catalog.json','change_points.json','manual_review_queue.csv','public_safety_report.json','degraded_modules.json','mesh_shape_summary.csv','texture_summary.json','status_summary.csv','gate_report.json','stage3_input_summary.json','artifact_index.json','evidence_chain_manifest.json']
  artifact_hashes={name:digest_file(o/name) for name in artifact_names if (o/name).is_file()}
  _work_root=Path(__file__).resolve().parents[2]
  _reuse_report=model.reuse_report();_space_manifest=space_manifest()
  _modules={
   'angle_noise':{'imported':True,'applied':any(bool(r.get('angle_noise_compensated')) for r in rows),'affected_pair_count':sum(bool(r.get('angle_noise_compensated')) for r in rows)},
   'chronology_rate':{'imported':True,'applied':bool(chronology_refs),'affected_pair_count':sum(bool(r.get('chronology_rate_status')) for r in rows)},
   'same_day_gate_v2':{'imported':True,'applied':any(r.get('days_delta')==0 for r in rows),'affected_pair_count':sum(r.get('days_delta')==0 for r in rows)},
   'multiple_testing':{'imported':True,'applied':bool(multiple_testing_report['pair_fdr'].get('test_count')),'affected_pair_count':multiple_testing_report['pair_fdr'].get('test_count',0)},
   'cross_bin_corroboration':{'imported':True,'applied':bool(cross_bin_report),'affected_pair_count':sum(bool(r.get('cross_bin_corroboration_status')) for r in rows)},
  }
  _run_manifest=build_manifest(_work_root,code_hash=digest_file(Path(__file__)),config_hash=digest_json(self.cfg.payload()),model_hash=digest_file(_work_root/'3ddfa_v3'/'assets'/'face_model.npy') or 'missing',reuse_report=_reuse_report,space_manifest=_space_manifest,anchor_policy=anchor_policy_by_bin,modules=_modules)
  manifest={'schema_version':SCHEMA,'status':'complete','reuse_report':_reuse_report,'space_manifest':_space_manifest,'run_manifest':_run_manifest,'anchor_policy_by_bin':anchor_policy_by_bin,'expression_gate_summary':expr_gate_summary,'created_at_utc':utc(),'stage1_manifest_digest':digest_file(self.cfg.stage1_root/'stage1_manifest.json'),'config_hash':digest_json(self.cfg.payload()),'robustness_policy':self.cfg.payload(),'execution':{'checkpoint_every':self.cfg.checkpoint_every,'resumed':self.cfg.resume},'main_record_count':len(main),'calibration_record_count':len(cal),'calibration_dataset_count':len(model.datasets),'mesh_calibration_status':mesh_model.reference.status,'mesh_calibration_pair_count':mesh_model.reference.pair_count,'calibration_sensitivity_status':calibration_sensitivity.get('status'),'calibration_limited_pair_count':sum(bool(r.get('calibration_limited')) for r in rows),'pose_leakage_status':pose_leakage_report.get('status'),'pose_leakage_limited_pair_count':sum(bool(r.get('pose_leakage_limited')) for r in rows),'missing_mandatory_qc_record_count':missing_qc_record_count,'skipped_pair_counts':dict(skipped_counts),'pose_leakage_flagged_metrics':pose_leakage_report.get('flagged_metrics',[]),'multiple_testing_pair_count':multiple_testing_report['pair_fdr'].get('test_count',0),'pair_count':len(rows),'zone_measurement_count':len(zones),'quality_zone_pair_count':len(quality_zone_rows),'texture_pair_count':len(texture_pair_rows),'texture_zone_metric_count':len(texture_zone_rows),'mesh_pair_count':len(mesh_rows),'mesh_zone_count':len(mesh_zones),'point_motion_pair_count':len(rows),'descriptor_family_count':len(DESCRIPTOR_NAMES),'lead_registry_status':leads.get('status'),'lead_date_count':leads.get('date_count',0),'lead_metric_count':leads.get('metric_count',0),'lead_overlap_pair_count':sum(bool(r.get('lead_overlap')) for r in rows),'change_point_count':len(changes),'cumulative_drift_event_count':cumulative_drift_report.get('event_count',0),'alpha_chronology_event_count':alpha_chronology_report.get('event_count',0),'baseline_return_count':baseline_return_report.get('event_count',0),'evidence_packet_count':len(evidence_packets),'postprocess_summary':postprocess_summary,'artifact_hashes':artifact_hashes,'pose_bins':{k:len(v) for k,v in groups.items()},'elapsed_seconds':time.time()-t,'limitations':['Prior leads prioritize coverage and reporting but never define ground truth or thresholds.','Coordinate zones are not anatomical labels.','Statuses are measurements, not identity or medical verdicts.']}
  atomic_json(o/'technical_summary.json',build_technical_summary(rows,changes,manifest))
  atomic_json(o/'analysis_manifest.json',manifest)
  req=['analysis_manifest.json','technical_summary.json','calibration_noise_model.json','calibration_sensitivity.json','mesh_noise_model.json','point_noise_model.npz','descriptor_noise_model.npz','lead_registry.json','lead_coverage.csv','chronology_rate_model.json','alpha_chronology.json','alpha_chronology_events.csv','baseline_return.json','cumulative_drift.json','cross_bin_corroboration.json','event_aggregation.csv','pose_leakage_diagnostic.json','metric_catalog.json','zone_map.json','pair_metrics.csv','zone_metrics.csv','quality_zone_pair_coverage.csv','texture_pair_metrics.csv','texture_zone_metrics.csv','mesh_pair_metrics.csv','multiple_testing.json','change_points.json','manual_review_queue.csv','public_safety_report.json','degraded_modules.json','mesh_shape_summary.csv','texture_summary.json','status_summary.csv','gate_report.json','stage3_input_summary.json','artifact_index.json','evidence_chain_manifest.json']
  errors=validate_analysis_contract(o,required_files=req,rows=rows,changes=changes,evidence_packets=evidence_packets,public_safety={'status':postprocess_summary.get('public_safety_status')});atomic_json(o/'analysis_validation.json',{'schema':'stage2-validation-v1.1','status':'complete' if not errors else 'invalid','errors':errors})
  if errors:raise RuntimeError(str(errors))
  checkpoint_path.unlink(missing_ok=True)
  return manifest
 @staticmethod
 def _persistence(rows):
  by=defaultdict(list)
  for r in rows:
   if r['pair_type']=='adjacent':by[r['pose_bin']].append(r)
  for g in by.values():
   g.sort(key=lambda x:(x['date_b'] or '',x['pair_index']))
   for i,r in enumerate(g):
    nxt=g[i+1:i+3]
    if r['status']=='coherent_jump_candidate' and any(x.get('point_motion_status')=='coherent_jump_candidate' or x.get('descriptor_status')=='descriptor_jump_candidate' for x in nxt):r['status']='persistent_geometric_change'
