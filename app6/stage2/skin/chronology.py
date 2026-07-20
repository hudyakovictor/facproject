"""Pose/expression-separated temporal candidate analysis."""
from __future__ import annotations
import json, math
from pathlib import Path


def circular_line_distance_deg(a, b):
    d = abs(float(a) - float(b)) % 180
    return min(d, 180 - d)


def match_branches(a, b, centroid_tol=.05, orientation_tol_deg=15, length_log_tol=.35):
    used, matches = set(), []
    for i, x in enumerate(a):
        best = None
        for j, y in enumerate(b):
            if j in used: continue
            loc = math.hypot(float(x.get('centroid_x', 0))-float(y.get('centroid_x', 0)),
                             float(x.get('centroid_y', 0))-float(y.get('centroid_y', 0)))
            ori = circular_line_distance_deg(x.get('orientation_deg', 0), y.get('orientation_deg', 0))
            lr = abs(math.log(max(float(x.get('length', 0)), 1e-6)/max(float(y.get('length', 0)), 1e-6)))
            if loc <= centroid_tol and ori <= orientation_tol_deg and lr <= length_log_tol:
                cost = loc/centroid_tol + ori/orientation_tol_deg + lr/length_log_tol
                if best is None or cost < best[0]: best = (cost, j)
        if best: used.add(best[1]); matches.append((i, best[1]))
    return {'matches': matches, 'match_fraction': len(matches)/max(1, len(a), len(b))}


def analyze_records(records, profile=None):
    by = {}
    for r in records: by.setdefault(str(r.get('pose_bin', 'unknown')), []).append(r)
    pairs = []
    for pose, g in by.items():
        g = sorted(g, key=lambda r: (str(r.get('date', '')), str(r.get('photo_id', ''))))
        for a, b in zip(g, g[1:]):
            pairs.append({'pair_id': f"{a.get('photo_id')}__{b.get('photo_id')}", 'pose_bin': pose,
                          'photo_a': a.get('photo_id'), 'photo_b': b.get('photo_id'),
                          'date_a': a.get('date'), 'date_b': b.get('date'),
                          'status': 'calibrated_consistent' if profile else 'uncalibrated',
                          'calibrated': bool(profile)})
    return {'schema': 'skin-temporal-v1', 'calibrated': bool(profile), 'pairs': pairs,
            'pose_bins': sorted(by), 'record_count': len(records)}


def load_records(path):
    p = Path(path)
    if p.is_dir():
        c = p/'stage1_records.json'
        if c.exists(): return json.loads(c.read_text())
        out = []
        for f in sorted(p.glob('*.json')):
            try:
                d = json.loads(f.read_text()); out.extend(d if isinstance(d, list) else [d])
            except Exception:
                continue
        return out
    text = p.read_text().strip()
    if '\n' in text and not text.lstrip().startswith('['):
        return [json.loads(x) for x in text.splitlines() if x.strip()]
    d = json.loads(text); return d if isinstance(d, list) else [d]


load_stage1_records = load_records


def _date_value(value):
    from datetime import date
    if not value: return None
    try: return date.fromisoformat(str(value)[:10])
    except ValueError: return None


def analyze_temporal_observations(observations, min_pre=3, min_post=3, jump_z=3.5):
    import numpy as np
    groups = {}
    for r in observations:
        if r.get('state') != 'usable' or r.get('raw_value') is None: continue
        if _date_value(r.get('date_start')) is None: continue
        key = (str(r.get('pose_bin', 'unknown')), str(r.get('expression_bin', 'unknown')),
               str(r.get('zone', '')), str(r.get('family', '')))
        groups.setdefault(key, []).append(r)
    series, changes = [], []
    for (pose, expression, zone, family), g in groups.items():
        # Aggregate duplicated observations within a capture event before temporal modelling.
        events = {}
        for r in g:
            eid = str(r.get('capture_event_id') or r.get('event_id') or r.get('photo_id'))
            events.setdefault(eid, []).append(r)
        agg = []
        for eid, rows in events.items():
            values = np.asarray([float(x['raw_value']) for x in rows], float)
            base = rows[0].copy(); base['raw_value'] = float(np.median(values)); base['event_id'] = eid
            agg.append(base)
        g = sorted(agg, key=lambda x: _date_value(x.get('date_start')))
        if len(g) < 3: continue
        d0 = _date_value(g[0]['date_start'])
        t = np.array([(_date_value(x['date_start']) - d0).days for x in g], float)
        y = np.array([x['raw_value'] for x in g], float)
        med = np.median(y); mad = 1.4826*np.median(abs(y-med)) + 1e-9
        try:
            from scipy.stats import theilslopes
            s, _intercept, lo, hi = theilslopes(y, t)
        except Exception:
            s = np.polyfit(t, y, 1)[0]; lo = hi = np.nan
        series.append({'pose_bin': pose, 'expression_bin': expression, 'zone': zone, 'family': family,
                       'events': len(g), 'slope_per_day': float(s), 'slope_low': float(lo),
                       'slope_high': float(hi), 'mad': float(mad)})
        for k in range(min_pre, len(g)-min_post+1):
            effect = float(np.median(y[k:]) - np.median(y[:k])); z = abs(effect)/mad
            sp = float(np.polyfit(t[:k], y[:k], 1)[0]); sq = float(np.polyfit(t[k:], y[k:], 1)[0])
            base = {'pose_bin': pose, 'expression_bin': expression, 'zone': zone, 'family': family,
                    'interval': [g[k-1]['date_start'], g[k]['date_start']], 'robust_z': z,
                    'effect': effect, 'slope_before': sp, 'slope_after': sq,
                    'evidence': 'candidate_requires_quality_source_alternative'}
            if z >= jump_z: changes.append({**base, 'type': 'level_jump_candidate'})
            if abs(sp-sq)*max(t[-1]-t[0], 1) > 2*mad: changes.append({**base, 'type': 'slope_change_candidate'})
            if abs(sp)*max(t[k-1]-t[0], 1) > 2*mad and abs(sq) < abs(sp)*.25:
                changes.append({**base, 'type': 'plateau_after_prior_trend_candidate'})
            if sp*sq < 0 and min(abs(sp), abs(sq))*max(t[-1]-t[0], 1) > mad:
                changes.append({**base, 'type': 'reversal_candidate'})
        if len(y) >= 5 and abs(y[0]-y[-1]) < mad and abs(np.median(y[1:-1])-y[0]) > 2.5*mad:
            changes.append({'pose_bin': pose, 'expression_bin': expression, 'zone': zone, 'family': family,
                            'interval': [g[0]['date_start'], g[-1]['date_start']],
                            'type': 'recurring_state_candidate',
                            'evidence': 'requires independent source replication'})
    return {'schema': 'skin-temporal-v1', 'implementation_status': 'experimental_candidate_detection',
            'grouping': 'pose_bin|expression_bin|zone|family; capture-event aggregated',
            'series': series, 'change_candidates': changes,
            'forbidden': 'no causal/identity/material verdict'}
