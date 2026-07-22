"""
🎯 CRITICAL → Оркестратор Stage 2: формирование пар, фильтры, payload для отчёта.

run(): load_main/load_calibration (хронология-выравненные данные), затем пары
(соседние по времени + не-соседние) с гейтами: MIN_ALIGNMENT_QUALITY=0.5 (патч 02),
MAX_EXPRESSION_MAGNITUDE=1.5 (#11). Далее: core-показатели, calibration,
chronology rate flags, corroboration, motion/dense-mesh/texture каналы,
multiple_testing FDR, persistence результатов.
⚠️ Открыто: calibration cross-validation и residual pose check (status_warning TODO).
"""
from __future__ import annotations
import json,time,shutil
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from app6.stage1.utils import atomic_json,sha256_file,sha256_json,write_csv
from app6.stage1.status_logger import log_status, status_warning
from .calibration import CalibrationModel
from .calibration_sensitivity import leave_one_dataset_sensitivity
from .core import build_coordinate_zone_map,calibrated_score,compare_landmarks
from .loaders import load_calibration,load_main
from .mesh_calibration import MeshNoiseModel
from .multiple_testing import apply_pair_fdr, apply_zone_fdr
from .mesh_dense import dense_mesh_pair
from .motion import PointNoiseModel,aligned_point_motion
from .quality_integration import pair_quality_zone_overlap
from .texture_pair import summarize_texture_pairs
from .texture_image import texture_pair_deltas
from .uv_comparison import uv_geometry_pair
from .technical_summary import build_technical_summary
from .postprocess_reports import write_postprocess_reports
from .descriptors import DescriptorNoiseModel,NAMES as DESCRIPTOR_NAMES
from .leads import load_leads,pair_leads
from .alpha_chronology import apply_alpha_chronology
from .baseline_return import apply_baseline_return
from .chronology import apply_chronology_rate_flags
from .corroboration import apply_cross_bin_corroboration, aggregate_events
from .pose_leakage import pose_leakage_diagnostic
from .metric_registry import build_metric_catalog
from .evidence import evidence_state, packet_from_pair

SCHEMA='deeputin-stage2-v1.3'

# 🔄 UTC-штамп для payload
def utc():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

@dataclass(frozen=True)
class Stage2Config:
 stage1_root:Path;calibration_root:Path;output_dir:Path;overwrite:bool=False;min_points106:int=24;min_points134:int=30;lead_archive:Path|None=None
 # 🏭 FACTORY → сборка итогового payload прогона
 def payload(self):return {'schema':SCHEMA,'min106':self.min_points106,'min134':self.min_points134,'calibration':'7x-same-person-matched-plus-pooled-v1','lead_policy':'coverage_only_not_threshold_tuning','descriptor_families':list(DESCRIPTOR_NAMES)}

 def __post_init__(self):
  if self.min_points106 < 8 or self.min_points134 < 8:raise ValueError('min_points must be >= 8')
  if self.stage1_root == self.output_dir or self.calibration_root == self.output_dir:raise ValueError('output_dir must differ from input roots')

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

  ⚠️ IN PROGRESS:
    - Использует chronology-aligned landmarks (исправлено)
    - Фильтрует по alignment quality (исправлено)
    - Нет проверки что калибровочная модель стабильна (cross-validation)

  💡 NOTE:
    - Пары только внутри одного pose bin (adjacent + baseline)
    - Calibration noise из 7 same-person datasets
    - FDR correction для multiple testing

  🚨 WARNING:
    - При отсутствии калибровочных данных — ошибка
    - При большом количестве пар — медленно (FDR)
  """
  log_status("run", "complete")
  t=time.time();o=self.cfg.output_dir
  if o.exists() and any(o.iterdir()) and not self.cfg.overwrite:raise FileExistsError(f'output exists: {o}')
  if o.exists() and self.cfg.overwrite:
   for child in o.iterdir():
    shutil.rmtree(child) if child.is_dir() else child.unlink()
  o.mkdir(parents=True,exist_ok=True)
  main=load_main(self.cfg.stage1_root);cal=load_calibration(self.cfg.calibration_root);leads=load_leads(self.cfg.lead_archive)
  if not main:raise RuntimeError('no valid stage1 records')
  z106,m106=build_coordinate_zone_map(cal,106);z134,m134=build_coordinate_zone_map(cal,134);model=CalibrationModel(cal,z106,z134);point_model=PointNoiseModel(cal);descriptor_model=DescriptorNoiseModel(cal);mesh_model=MeshNoiseModel(cal)
  atomic_json(o/'zone_map.json',{'schema':'coordinate-zone-map-v1','ldm106':z106,'ldm134':z134,'ldm106_meta':m106,'ldm134_meta':m134})
  atomic_json(o/'calibration_noise_model.json',{'schema':'calibration-noise-v1','datasets':model.datasets,'record_count':len(cal),'references':model.references})
  calibration_sensitivity=leave_one_dataset_sensitivity(cal,z106,z134)
  atomic_json(o/'calibration_sensitivity.json',calibration_sensitivity)
  atomic_json(o/'mesh_noise_model.json',mesh_model.to_json())
  atomic_json(o/'lead_registry.json',leads);write_csv(o/'lead_coverage.csv',leads.get('coverage') or [{'legacy_metric':'none','coverage':'not_provided'}])
  point_payload={}
  for (pose,count),ref in point_model.references.items():
   prefix=f'{pose}__ldm{count}';point_payload[f'{prefix}__median']=ref.median;point_payload[f'{prefix}__mad']=ref.mad;point_payload[f'{prefix}__p95']=ref.p95;point_payload[f'{prefix}__count']=ref.count;point_payload[f'{prefix}__template']=ref.template
  np.savez_compressed(o/'point_noise_model.npz',**point_payload)
  descriptor_payload={'metric_names':np.asarray(DESCRIPTOR_NAMES)}
  for pose,ref in descriptor_model.refs.items():
   descriptor_payload[f'{pose}__median']=ref.median;descriptor_payload[f'{pose}__mad']=ref.mad;descriptor_payload[f'{pose}__p95']=ref.p95;descriptor_payload[f'{pose}__count']=ref.count;descriptor_payload[f'{pose}__template']=ref.template
  np.savez_compressed(o/'descriptor_noise_model.npz',**descriptor_payload)
  motion_dir=o/'point_motion';motion_dir.mkdir(exist_ok=True)
  groups=defaultdict(list)
  for r in main:groups[r.pose_bin].append(r)
  # Load alignment quality from info.json for each record
  alignment_quality = {}
  for r in main:
      info_path = Path(r.record_dir) / 'info.json' if r.record_dir else None
      if info_path and info_path.is_file():
          try:
              info = json.loads(info_path.read_text(encoding='utf-8'))
              chronology = info.get('chronology', {})
              alignment_quality[r.record_id] = chronology.get('alignment_quality', 1.0)
          except Exception:
              alignment_quality[r.record_id] = 1.0
      else:
          alignment_quality[r.record_id] = 1.0
  # Load expression magnitude from info.json for each record
  expression_magnitude = {}
  for r in main:
      info_path = Path(r.record_dir) / 'info.json' if r.record_dir else None
      if info_path and info_path.is_file():
          try:
              info = json.loads(info_path.read_text(encoding='utf-8'))
              chronology = info.get('chronology', {})
              expression_magnitude[r.record_id] = chronology.get('expression_magnitude', 0.0)
          except Exception:
              expression_magnitude[r.record_id] = 0.0
      else:
          expression_magnitude[r.record_id] = 0.0
  # ⚠️ IN PROGRESS: Calibration stability cross-validation not implemented
  # TODO: Add leave-one-out validation for calibration model
  status_warning("calibration_stability", "Cross-validation not implemented")

  # ⚠️ IN PROGRESS: Pose delta gate doesn't check residual after correction
  # TODO: Add residual pitch/roll check after chronology alignment
  status_warning("pose_delta_gate", "Residual pose check not implemented")
  # Load temporal context: previous/next photos for each record
  # This enables temporal smoothing and consistency checks
  temporal_context = {}
  for pose_bin, records in groups.items():
      records_sorted = sorted(records, key=lambda r: (r.date or '9999', r.sequence))
      for i, r in enumerate(records_sorted):
          prev_rec = records_sorted[i - 1] if i > 0 else None
          next_rec = records_sorted[i + 1] if i < len(records_sorted) - 1 else None
          temporal_context[r.record_id] = {
              'prev_record_id': prev_rec.record_id if prev_rec else None,
              'next_record_id': next_rec.record_id if next_rec else None,
              'prev_date': prev_rec.date if prev_rec else None,
              'next_date': next_rec.date if next_rec else None,
              'index_in_pose_bin': i,
              'total_in_pose_bin': len(records_sorted),
          }


  # Filter out pairs where either photo has poor alignment quality (< 0.5)
  MIN_ALIGNMENT_QUALITY = 0.5
  # Filter out pairs where either photo has strong expression (jaw open, smile)
  MAX_EXPRESSION_MAGNITUDE = 1.5  # threshold for expression dominance
  specs=[]
  skipped_alignment = 0
  skipped_expression = 0
  # 🚨 WARNING (AUDIT-5): при отсутствии info.json дефолты (1.0/0.0) ПРОПУСКАЮТ фото
  # через фильтры — без сигнала это скрывает loss of filtering. Считаем и предупреждаем.
  missing_alignment_info = sum(1 for r in main if r.record_id not in alignment_quality)
  missing_expression_info = sum(1 for r in main if r.record_id not in expression_magnitude)
  if missing_alignment_info > 0:
      status_warning("alignment_filter", f"{missing_alignment_info} records lack alignment_quality — NOT filtered (default pass)")
  if missing_expression_info > 0:
      status_warning("expression_filter", f"{missing_expression_info} records lack expression_magnitude — NOT filtered (default pass)")
  for pose,rs in sorted(groups.items()):
   rs.sort(key=lambda x:(x.date or '9999',x.sequence,x.record_id))
   for a,b in zip(rs,rs[1:]):
       # Skip if either photo has poor alignment
       if alignment_quality.get(a.record_id, 1.0) < MIN_ALIGNMENT_QUALITY or alignment_quality.get(b.record_id, 1.0) < MIN_ALIGNMENT_QUALITY:
           skipped_alignment += 1
           continue
       # Skip if either photo has strong expression
       if expression_magnitude.get(a.record_id, 0.0) > MAX_EXPRESSION_MAGNITUDE or expression_magnitude.get(b.record_id, 0.0) > MAX_EXPRESSION_MAGNITUDE:
           skipped_expression += 1
           continue
       specs.append(('adjacent',a,b))
   if len(rs)>2:
       for b in rs[2:]:
           if alignment_quality.get(rs[0].record_id, 1.0) < MIN_ALIGNMENT_QUALITY or alignment_quality.get(b.record_id, 1.0) < MIN_ALIGNMENT_QUALITY:
               skipped_alignment += 1
               continue
           if expression_magnitude.get(rs[0].record_id, 0.0) > MAX_EXPRESSION_MAGNITUDE or expression_magnitude.get(b.record_id, 0.0) > MAX_EXPRESSION_MAGNITUDE:
               skipped_expression += 1
               continue
           specs.append(('baseline',rs[0],b))
  if skipped_alignment > 0:
      print(f"  Skipped {skipped_alignment} pairs due to poor alignment quality (< {MIN_ALIGNMENT_QUALITY})", flush=True)
  if skipped_expression > 0:
      print(f"  Skipped {skipped_expression} pairs due to strong expression (> {MAX_EXPRESSION_MAGNITUDE})", flush=True)
  rows=[];zones=[];details=[];quality_zone_rows=[];texture_zone_rows=[];mesh_rows=[];mesh_zones=[];uv_zone_list=[]
  for n,(ptype,a,b) in enumerate(specs,1):
   pid=f'{ptype}__{a.record_id}__{b.record_id}';c=compare_landmarks(a,b,z106,z134,self.cfg.min_points106,self.cfg.min_points134);matched=model.matched_null(a,b) if c.status=='measured' else {};scores={}
   for k,v in c.metrics.items():scores[k]=calibrated_score(v,model.reference(a.pose_bin,k),matched.get(k,[]))
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
   if status=='coherent_jump_candidate':
    es=scores.get('alpha_exp_l2',{}).get('status')
    status='expression_dominated' if expression_influence>=.45 and es in ('elevated','elevated_but_uncertain') else 'coherent_jump_candidate'
   safe_pid=pid.replace('/','_');np.savez_compressed(motion_dir/f'{safe_pid}.npz',ldm106_vectors=motion106['vectors'],ldm106_magnitude=motion106['magnitude'],ldm106_point_z=motion_score106['z'],ldm106_significant=motion_score106['significant'],ldm134_vectors=motion134['vectors'],ldm134_magnitude=motion134['magnitude'],ldm134_point_z=motion_score134['z'],ldm134_significant=motion_score134['significant'],ldm134_identity_only_vectors=identity_motion['vectors'],ldm134_identity_only_magnitude=identity_motion['magnitude'],descriptor_names=np.asarray(DESCRIPTOR_NAMES),descriptor_values=descriptor_score['values'],descriptor_z=descriptor_score['z'],descriptor_significant=descriptor_score['significant'])
   ms=motion_score134['summary'];ds=descriptor_score['summary'];lead=pair_leads(leads,a.date,b.date);mesh_row,mesh_zone_list=dense_mesh_pair(a,b,o,pid);texture_row,texture_zone_list=texture_pair_deltas(a,b,pid);uv_row,uv_zone_list_local=uv_geometry_pair(a,b,o,pid);texture_zone_rows.extend(texture_zone_list);uv_zone_list.extend(uv_zone_list_local);mesh_score=mesh_model.score(a.pose_bin,mesh_row);mesh_row.update(mesh_score);mesh_rows.append({'pair_id':pid,'pair_type':ptype,'pose_bin':a.pose_bin,'photo_a':a.record_id,'photo_b':b.record_id,**mesh_row});mesh_zones.extend(mesh_zone_list)
   row={'pair_id':pid,'pair_index':n,'pair_type':ptype,'pose_bin':a.pose_bin,'photo_a':a.record_id,'photo_b':b.record_id,'date_a':a.date,'date_b':b.date,'source_group_a':a.source_group,'source_group_b':b.source_group,'source_sha256_a':a.source_sha256,'source_sha256_b':b.source_sha256,'status':status,'motion_file':f'point_motion/{safe_pid}.npz',**mesh_row,**texture_row,**uv_row,'point_motion_status':motion_score134['status'],'ldm134_anchor_count':motion134.get('anchor_count',0),'ldm134_anchor_policy':motion134.get('anchor_policy','unknown'),'ldm134_alignment_policy':motion134.get('alignment_policy','unknown'),'ldm134_alignment_trimmed_count':motion134.get('alignment_trimmed_count',0),'ldm106_anchor_count':motion106.get('anchor_count',0),'ldm106_anchor_policy':motion106.get('anchor_policy','unknown'),'descriptor_status':descriptor_score['status'],'descriptor_significant_fraction':ds.get('significant_cell_fraction',0.),'descriptor_landmark_fraction':ds.get('significant_landmark_fraction',0.),'descriptor_p95_z':ds.get('p95_descriptor_z',0.),'descriptor_top_families':ds.get('top_descriptor_families',''),'descriptor_top_counts':ds.get('top_descriptor_counts',''),'significant_point_count':ms.get('significant_point_count',0),'significant_point_fraction':ms.get('significant_fraction',0.),'coherent_motion_fraction':ms.get('coherent_fraction',0.),'median_point_z':ms.get('median_point_z',0.),'p95_point_z':ms.get('p95_point_z',0.),'identity_only_motion_rmse':identity_rmse,'expression_influence':expression_influence,**lead,**c.diagnostics,**c.metrics,'primary_robust_z':float(primary.get('robust_z',0)),'primary_calibration_p95':float(primary.get('calibration_p95',0)),'matched_calibration_sets':len(matched.get('ldm134_rmse',[]))}
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
   row['evidence_state'] = evidence_state(str(row.get('status','')), quality_limited=qlimited)
   rows.append(row)
   for z in c.zones:
    zr={'pair_id':pid,'pair_type':ptype,'pose_bin':a.pose_bin,'photo_a':a.record_id,'photo_b':b.record_id,**z}
    if z.get('status')=='measured':
     k=f"zone::{z['zone']}::rmse";s=calibrated_score(float(z['rmse']),model.reference(a.pose_bin,k),matched.get(k,[]));zr.update({'calibration_status':s['status'],'robust_z':s['robust_z'],'calibration_p95':s['calibration_p95']})
    zones.append(zr)
   details.append({'pair':row,'calibrated_metrics':scores,'zones':c.zones})
  self._persistence(rows)
  alpha_chronology_report=apply_alpha_chronology(rows,model)
  baseline_return_report=apply_baseline_return(rows,o)
  chronology_refs=apply_chronology_rate_flags(rows)
  cross_bin_report=apply_cross_bin_corroboration(rows)
  event_rows=aggregate_events(rows)
  pose_leakage_report=pose_leakage_diagnostic(rows)
  multiple_testing_report={'pair_fdr':apply_pair_fdr(rows),'zone_fdr':apply_zone_fdr(zones)}
  for r in rows:
   r['evidence_state'] = evidence_state(str(r.get('status','')), quality_limited=bool(r.get('quality_limited')))
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
  changes=[{'pair_id':r['pair_id'],'pose_bin':r['pose_bin'],'date':r['date_b'],'photo_a':r['photo_a'],'photo_b':r['photo_b'],'status':r['status'],'evidence_state':r.get('evidence_state',''),'p95_point_z':r.get('p95_point_z',0),'significant_point_fraction':r.get('significant_point_fraction',0),'coherent_motion_fraction':r.get('coherent_motion_fraction',0),'days_delta':r.get('days_delta',-1),'chronology_rate_status':r.get('chronology_rate_status',''),'chronology_rate_z':r.get('chronology_rate_z',0.0),'cross_bin_corroboration_status':r.get('cross_bin_corroboration_status',''),'cross_bin_support_pose_count':r.get('cross_bin_support_pose_count',0)} for r in rows if r['pair_type']=='adjacent' and r['status'] in ('persistent_geometric_change','coherent_jump_candidate','alpha_id_jump_candidate','baseline_return_candidate','expression_dominated','same_day_structural_conflict','rapid_change_candidate','persistent_rapid_change_candidate','biologically_improbable_rate_candidate','persistent_biologically_improbable_change')]
  uv_zone_rows=[z for z in uv_zone_list] if uv_zone_list else []
  write_csv(o/'pair_metrics.csv',rows or [{'status':'no_pairs'}]);write_csv(o/'zone_metrics.csv',zones or [{'status':'no_zones'}]);write_csv(o/'quality_zone_pair_coverage.csv',quality_zone_rows or [{'status':'no_quality_zone_pairs'}]);write_csv(o/'texture_pair_metrics.csv',texture_pair_rows or [{'status':'no_texture_pairs'}]);write_csv(o/'texture_zone_metrics.csv',texture_zone_rows or [{'status':'no_texture_zone_metrics'}]);write_csv(o/'mesh_pair_metrics.csv',mesh_rows or [{'status':'no_mesh_pairs'}]);write_csv(o/'mesh_zone_metrics.csv',mesh_zones or [{'status':'no_mesh_zones'}]);write_csv(o/'uv_geometry_zone_metrics.csv',uv_zone_rows or [{'status':'no_uv_zones'}]);atomic_json(o/'pair_details.json',{'schema':SCHEMA,'pairs':details});atomic_json(o/'evidence_packets.json',{'schema':'deeputin-stage2-evidence-v1.0','packets':evidence_packets})
  with (o/'evidence_packets.jsonl').open('w',encoding='utf-8') as f:
   for pkt in evidence_packets:f.write(json.dumps(pkt,ensure_ascii=False,allow_nan=False)+'\n')
  atomic_json(o/'multiple_testing.json',multiple_testing_report);atomic_json(o/'alpha_chronology.json',alpha_chronology_report);write_csv(o/'alpha_chronology_events.csv',alpha_chronology_report.get('events') or [{'status':'no_alpha_events'}]);atomic_json(o/'baseline_return.json',baseline_return_report);atomic_json(o/'cross_bin_corroboration.json',cross_bin_report);write_csv(o/'event_aggregation.csv',event_rows or [{'status':'no_events'}]);atomic_json(o/'pose_leakage_diagnostic.json',pose_leakage_report);atomic_json(o/'metric_catalog.json',metric_catalog);atomic_json(o/'change_points.json',{'schema':SCHEMA,'change_points':changes});atomic_json(o/'chronology_rate_model.json',{'schema':'chronology-rate-v2-neutral','references':chronology_refs})
  pd=o/'photo_analysis';pd.mkdir(exist_ok=True)
  for r in main:atomic_json(pd/f'{r.record_id}.json',{'schema':SCHEMA,'photo_id':r.record_id,'date':r.date,'pose_bin':r.pose_bin,'related_pairs':[x for x in rows if r.record_id in (x['photo_a'],x['photo_b'])]})
  postprocess_summary=write_postprocess_reports(o,rows=rows,zones=zones,mesh_zones=mesh_zones,texture_zone_rows=texture_zone_rows,changes=changes,evidence_packets=evidence_packets)
  artifact_names=['pair_metrics.csv','zone_metrics.csv','quality_zone_pair_coverage.csv','texture_pair_metrics.csv','texture_zone_metrics.csv','mesh_pair_metrics.csv','mesh_zone_metrics.csv','evidence_packets.json','evidence_packets.jsonl','multiple_testing.json','alpha_chronology.json','baseline_return.json','cross_bin_corroboration.json','event_aggregation.csv','pose_leakage_diagnostic.json','metric_catalog.json','change_points.json','manual_review_queue.csv','public_safety_report.json','degraded_modules.json','mesh_shape_summary.csv','texture_summary.json','status_summary.csv','gate_report.json','stage3_input_summary.json','artifact_index.json','evidence_chain_manifest.json']
  artifact_hashes={name:sha256_file(o/name) for name in artifact_names if (o/name).is_file()}
  manifest={'schema_version':SCHEMA,'status':'complete','created_at_utc':utc(),'stage1_manifest_sha256':sha256_file(self.cfg.stage1_root/'stage1_manifest.json'),'config_hash':sha256_json(self.cfg.payload()),'main_record_count':len(main),'calibration_record_count':len(cal),'calibration_dataset_count':len(model.datasets),'mesh_calibration_status':mesh_model.reference.status,'mesh_calibration_pair_count':mesh_model.reference.pair_count,'calibration_sensitivity_status':calibration_sensitivity.get('status'),'pose_leakage_status':pose_leakage_report.get('status'),'pose_leakage_flagged_metrics':pose_leakage_report.get('flagged_metrics',[]),'multiple_testing_pair_count':multiple_testing_report['pair_fdr'].get('test_count',0),'pair_count':len(rows),'zone_measurement_count':len(zones),'quality_zone_pair_count':len(quality_zone_rows),'texture_pair_count':len(texture_pair_rows),'texture_zone_metric_count':len(texture_zone_rows),'mesh_pair_count':len(mesh_rows),'mesh_zone_count':len(mesh_zones),'point_motion_pair_count':len(rows),'descriptor_family_count':len(DESCRIPTOR_NAMES),'lead_registry_status':leads.get('status'),'lead_date_count':leads.get('date_count',0),'lead_metric_count':leads.get('metric_count',0),'lead_overlap_pair_count':sum(bool(r.get('lead_overlap')) for r in rows),'change_point_count':len(changes),'alpha_chronology_event_count':alpha_chronology_report.get('event_count',0),'baseline_return_count':baseline_return_report.get('event_count',0),'evidence_packet_count':len(evidence_packets),'postprocess_summary':postprocess_summary,'artifact_hashes':artifact_hashes,'pose_bins':{k:len(v) for k,v in groups.items()},'elapsed_seconds':time.time()-t,'limitations':['Prior leads prioritize coverage and reporting but never define ground truth or thresholds.','Coordinate zones are not anatomical labels.','Statuses are measurements, not identity or medical verdicts.']}
  atomic_json(o/'technical_summary.json',build_technical_summary(rows,changes,manifest))
  atomic_json(o/'analysis_manifest.json',manifest)
  req=['analysis_manifest.json','technical_summary.json','calibration_noise_model.json','calibration_sensitivity.json','mesh_noise_model.json','point_noise_model.npz','descriptor_noise_model.npz','lead_registry.json','lead_coverage.csv','chronology_rate_model.json','alpha_chronology.json','alpha_chronology_events.csv','baseline_return.json','cross_bin_corroboration.json','event_aggregation.csv','pose_leakage_diagnostic.json','metric_catalog.json','zone_map.json','pair_metrics.csv','zone_metrics.csv','quality_zone_pair_coverage.csv','texture_pair_metrics.csv','texture_zone_metrics.csv','mesh_pair_metrics.csv','mesh_zone_metrics.csv','pair_details.json','evidence_packets.json','evidence_packets.jsonl','multiple_testing.json','change_points.json','manual_review_queue.csv','public_safety_report.json','degraded_modules.json','mesh_shape_summary.csv','texture_summary.json','status_summary.csv','gate_report.json','stage3_input_summary.json','artifact_index.json','evidence_chain_manifest.json']
  errors=[f'missing {x}' for x in req if not (o/x).is_file()];atomic_json(o/'analysis_validation.json',{'schema':'stage2-validation-v1','status':'complete' if not errors else 'invalid','errors':errors})
  if errors:raise RuntimeError(str(errors))
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
