"""Compatibility adapter from legacy Stage2 to native skin pair evidence.

Despite the historical module name, no UV texture metrics are consumed. The
adapter reads immutable native-photo skin packages and compares common observed
surface. Missing wrinkle features remain insufficient evidence, never zeros.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from app6.stage1.utils import atomic_json
from .skin.loader import SkinPackage
from .skin.pair_comparison import compare_packages
UV_COMPARISON_SCHEMA="deeputin-stage2-native-skin-adapter-v2.0"
def uv_geometry_pair(a:Any,b:Any,output_dir:Path,pair_id:str):
 da=getattr(a,'record_dir',None);db=getattr(b,'record_dir',None)
 if da is None or db is None:return {'uv_geometry_status':'insufficient_evidence','uv_geometry_reason':'missing_record_dir'},[]
 try:pa=SkinPackage(Path(da)/'skin');pb=SkinPackage(Path(db)/'skin')
 except Exception as e:return {'uv_geometry_status':'insufficient_evidence','uv_geometry_reason':'invalid_or_missing_skin_package','uv_geometry_error':str(e)},[]
 result=compare_packages(pa,pb);zones=[]
 for z in result['zones']:
  zones.append({'pair_id':pair_id,'zone':z['zone'],'status':z['status'],'common_coverage':z['coverage_sym'],'effective_common_triangles':len(z['common_triangle_ids']),'uv_ridge_density_delta':None,'uv_branch_count_delta':None,'uv_total_length_delta':None,'uv_ridge_strength_delta':None})
 usable=[z for z in zones if z['status']!='insufficient_evidence'];row={'uv_geometry_status':'native_surface_available','uv_geometry_schema':UV_COMPARISON_SCHEMA,'uv_common_zone_count':len(usable),'uv_mean_common_coverage':sum(z['common_coverage'] for z in zones)/max(1,len(zones)),'uv_wrinkle_metrics_status':'not_measured' }
 d=Path(output_dir)/'uv_comparison';d.mkdir(parents=True,exist_ok=True);atomic_json(d/f'{pair_id}.json',{'pair_id':pair_id,'summary':row,'zones':zones,'native_pair':result});return row,zones
