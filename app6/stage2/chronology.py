"""🎯 CRITICAL → Хронологические флаги: скорость изменения признака во времени.
🚪 API: apply_chronology_rate_flags(), apply_biological_rate_flags()
🔗 DEPENDS ON: stage1 chronology alignment (vertices_chronology_aligned)
🚨 WARNING: требует >=2 дат; при одной дате флаги не выставляются.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
import math
import numpy as np
from app6.stage1.status_logger import log_status

# Справочный порог (D-003): alignment_quality НЕ гейтит пары — некоррелирован.
MIN_ALIGNMENT_QUALITY = 0.5

def _days(a: str | None, b: str | None) -> int | None:
    if not a or not b: return None
    try:
        da=date.fromisoformat(str(a)[:10]); db=date.fromisoformat(str(b)[:10]); return (db-da).days
    except Exception:
        return None

def _robust(vals: list[float]) -> tuple[float,float,float]:
    arr=np.asarray([v for v in vals if np.isfinite(v)],dtype=float)
    if arr.size==0: return 0.0,0.0,0.0
    med=float(np.median(arr)); mad=float(np.median(np.abs(arr-med))); p95=float(np.percentile(arr,95)); return med,mad,p95

def _as_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "yes"}


def _quality_exclusion_reason(row: dict) -> str | None:
    """Return a fail-closed reason when pair-level chronology is not applicable."""
    if _as_flag(row.get('date_provenance_limited')):return 'date_provenance_conflict'
    if _as_flag(row.get('near_duplicate_pair')):return 'perceptual_duplicate_dependence'
    if _as_flag(row.get('quality_limited')):
        return 'quality_limited'
    # D-003 пересмотр (2026-08-03): alignment_quality некоррелирован с остатком
    return None

def _mark_chronology_excluded(row: dict, reason: str) -> None:
    row['days_delta'] = None
    row['time_weighted_jump_rate'] = float('nan')
    row['chronology_rate_z'] = float('nan')
    row['chronology_rate_status'] = 'excluded'
    row['chronology_rate_reason'] = reason
    row['biological_rate_z'] = row['chronology_rate_z']
    row['biological_rate_status'] = row['chronology_rate_status']
    row['biological_reason'] = row['chronology_rate_reason']

def apply_chronology_rate_flags(rows: list[dict]) -> dict[str,dict[str,float]]:
    """🎯 CRITICAL → Apply chronology rate flags to adjacent pairs.

    💡 NOTE:
    - Rate = p95_point_z * coherent_fraction / sqrt(days)
    - Flags: same_day_structural_conflict, rapid_change_candidate
    """
    log_status("apply_chronology_rate_flags", "complete")
    refs={}; by=defaultdict(list)
    for r in rows:
        if r.get('pair_type')=='adjacent':
            exclusion = _quality_exclusion_reason(r)
            if exclusion:
                _mark_chronology_excluded(r, exclusion)
                continue
            by[r['pose_bin']].append(r)
    for pose,group in by.items():
        rates=[]; coherent=[]
        for r in group:
            d=_days(r.get('date_a'),r.get('date_b'))
            if d is None:
                # Missing dates must not silently become a 1-day rate denominator.
                r['days_delta']=None
                r['time_weighted_jump_rate']=float('nan')
                r['date_status']='date_missing'
                continue
            if d < 0:
                r['days_delta']=int(d)
                r['time_weighted_jump_rate']=float('nan')
                r['date_status']='date_order_conflict'
                continue
            r['date_status']='ok'
            eff=max(1,int(d))
            weighted=float(r.get('p95_point_z',0.0))*max(float(r.get('coherent_motion_fraction',0.0)),0.1)/math.sqrt(eff)
            rates.append(weighted); coherent.append(float(r.get('coherent_motion_fraction',0.0)))
            r['days_delta']=int(d); r['time_weighted_jump_rate']=weighted
        med,mad,p95=_robust(rates); cmed,cmad,cp95=_robust(coherent)
        refs[pose]={'rate_median':med,'rate_mad':mad,'rate_p95':p95,'coherence_median':cmed,'coherence_mad':cmad,'coherence_p95':cp95,'count':len(rates)}
        floor=max(1.4826*mad,0.05)
        seq=sorted(group,key=lambda x:(x.get('date_b') or '',x.get('pair_index',0)))
        for i,r in enumerate(seq):
            if r.get('date_status') in ('date_missing','date_order_conflict') or r.get('days_delta') is None:
                r['chronology_rate_z']=float('nan')
                r['chronology_rate_status']=r.get('date_status','date_missing')
                r['chronology_rate_reason']=('date_b_precedes_date_a' if r.get('date_status')=='date_order_conflict' else 'missing_or_unparseable_pair_dates')
                r['biological_rate_z']=r['chronology_rate_z']
                r['biological_rate_status']=r['chronology_rate_status']
                r['biological_reason']=r['chronology_rate_reason']
                continue
            d=r.get('days_delta'); weighted=float(r.get('time_weighted_jump_rate',0.0)); pz=float(r.get('p95_point_z',0.0)); coh=float(r.get('coherent_motion_fraction',0.0)); sig=float(r.get('significant_point_fraction',0.0))
            rate_z=(weighted-med)/floor if floor>0 and np.isfinite(weighted) else 0.0
            r['chronology_rate_z']=rate_z; r['chronology_rate_status']='within_expected_rate'; r['chronology_rate_reason']=''
            same_day=(d==0 and pz>=4.5 and coh>=0.35)
            fast=(d is not None and 0<d<=60 and pz>=4.5 and sig>=0.15 and coh>=0.45 and rate_z>=3.0)
            medium=(d is not None and 60<d<=180 and pz>=5.5 and sig>=0.18 and coh>=0.5 and rate_z>=3.5)
            if same_day:
                r['chronology_rate_status']='same_day_structural_conflict'; r['chronology_rate_reason']='same day but coherent structural shift above calibrated noise'
            elif fast or medium:
                r['chronology_rate_status']='rapid_change_candidate'; r['chronology_rate_reason']='coherent calibrated shift is large relative to the elapsed days'
            if r['chronology_rate_status'] in ('same_day_structural_conflict','rapid_change_candidate'):
                nxt=seq[i+1] if i+1 < len(seq) else None
                if nxt and float(nxt.get('p95_point_z',0.0))>=3.5:
                    r['chronology_rate_status']='persistent_rapid_change_candidate'; r['chronology_rate_reason']+='; post-change state remains elevated'; r['status']='persistent_rapid_change_candidate'
                elif r['status'] in ('coherent_jump_candidate','persistent_geometric_change'):
                    r['status']=r['chronology_rate_status']
            # Compatibility aliases for older consumers. Canonical public fields are chronology_rate_*.
            r['biological_rate_z']=r['chronology_rate_z']
            r['biological_rate_status']=r['chronology_rate_status']
            r['biological_reason']=r['chronology_rate_reason']
    return refs


# 🗑️ DEPRECATED alias → используйте apply_chronology_rate_flags
def apply_biological_rate_flags(rows: list[dict]) -> dict[str,dict[str,float]]:
    """Deprecated compatibility alias; use apply_chronology_rate_flags."""
    # 🗑️ DEPRECATED (AUDIT-5): алиас логирует свой статус при вызове, делегирует основной функции
    log_status("apply_biological_rate_flags", "deprecated", "Alias of apply_chronology_rate_flags")
    return apply_chronology_rate_flags(rows)


def apply_cumulative_drift_flags(
    rows: list[dict], *, point_z_floor: float = 2.5, cusum_threshold: float = 6.0,
    anchor_threshold: float = 4.5,
) -> dict[str, object]:
    """Detect gradual drift missed by individually small adjacent changes.

    Adjacent rows receive a one-sided CUSUM of excess calibrated point-z.
    Existing baseline rows act as explicit anchor comparisons.  Quality-limited
    or otherwise excluded rows never contribute evidence.
    """
    by_pose=defaultdict(list)
    for row in rows:
        if row.get('pair_type') in ('adjacent','baseline'):
            by_pose[str(row.get('pose_bin','unknown'))].append(row)
    events=[]; summaries={}
    for pose, group in by_pose.items():
        adjacent=sorted((r for r in group if r.get('pair_type')=='adjacent'),
                        key=lambda r:(r.get('date_b') or '',r.get('pair_index',0)))
        cusum=0.0; max_cusum=0.0
        for row in adjacent:
            reason=_quality_exclusion_reason(row)
            z=float(row.get('p95_point_z',float('nan')))
            if reason or not np.isfinite(z):
                row['cumulative_drift_status']='excluded'
                row['cumulative_drift_reason']=reason or 'nonfinite_point_z'
                row['cumulative_drift_cusum']=float('nan')
                cusum=0.0
                continue
            cusum=max(0.0,cusum+(z-float(point_z_floor)))
            max_cusum=max(max_cusum,cusum)
            row['cumulative_drift_cusum']=cusum
            row['cumulative_drift_status']='within_cumulative_noise'
            row['cumulative_drift_reason']=''
            if cusum>=float(cusum_threshold):
                row['cumulative_drift_status']='cumulative_drift_candidate'
                row['cumulative_drift_reason']='several sub-threshold adjacent changes accumulated'
                events.append({'pair_id':row.get('pair_id'),'pose_bin':pose,'type':'cusum',
                               'score':cusum,'date':row.get('date_b')})
        anchor_events=0
        for row in (r for r in group if r.get('pair_type')=='baseline'):
            reason=_quality_exclusion_reason(row)
            z=float(row.get('p95_point_z',float('nan')))
            sig=float(row.get('significant_point_fraction',0.0) or 0.0)
            row['anchor_drift_status']='excluded' if reason else 'within_anchor_noise'
            if not reason and np.isfinite(z) and z>=float(anchor_threshold) and sig>=0.15:
                row['anchor_drift_status']='anchor_drift_candidate'; anchor_events+=1
                events.append({'pair_id':row.get('pair_id'),'pose_bin':pose,'type':'anchor',
                               'score':z,'date':row.get('date_b')})
        summaries[pose]={'adjacent_count':len(adjacent),'max_cusum':max_cusum,
                         'anchor_event_count':anchor_events}
    return {'schema':'cumulative-drift-v1','events':events,'event_count':len(events),
            'pose_summaries':summaries,'point_z_floor':point_z_floor,
            'cusum_threshold':cusum_threshold,'anchor_threshold':anchor_threshold}
