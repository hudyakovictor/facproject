#!/usr/bin/env python3
"""Post-run diagnostic: geometry vs support vs evidence for skin packages.

Usage:
  python app6/scripts/check_geometry_vs_evidence.py /path/to/results_root [--out report_dir]

Expects packages like:
  results_root/<photo_id>/skin/{atlas_projection.npz,quality_maps.npz,features/texture.npz,quality.json}
📊 CONVENTIONS v2 → аудит-скрипт; статус: 🔬 EXPERIMENTAL
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

import numpy as np

try:
    from PIL import Image
except Exception:
    Image = None


def load_mask(skin: Path, shape):
    p = skin / 'analysis_mask.png'
    if p.is_file() and Image is not None:
        m = np.array(Image.open(p).convert('L')) > 0
        if m.shape != shape:
            # nearest resize without cv2 dependency
            ys = (np.linspace(0, m.shape[0] - 1, shape[0])).astype(int)
            xs = (np.linspace(0, m.shape[1] - 1, shape[1])).astype(int)
            m = m[ys][:, xs]
        return m
    return np.ones(shape, bool)


def analyze_pkg(skin: Path) -> dict:
    with np.load(skin / 'atlas_projection.npz') as z:
        A = z['zone_id_a20']
        domain = z['domain_mask'].astype(bool) if 'domain_mask' in z.files else (A >= 0)
    mask = load_mask(skin, A.shape)
    dom = domain & mask

    qw = pw = conf = None
    qmaps = skin / 'quality_maps.npz'
    if qmaps.is_file():
        with np.load(qmaps) as qm:
            qw = qm['quality_weight'] if 'quality_weight' in qm.files else None
            pw = qm['pose_weight'] if 'pose_weight' in qm.files else None
            conf = qm['projection_confidence'] if 'projection_confidence' in qm.files else None
            dens = qm['projected_density_map'] if 'projected_density_map' in qm.files else None
    else:
        dens = None

    tex_state = {}
    tpath = skin / 'features/texture.npz'
    if tpath.is_file():
        with np.load(tpath) as t:
            for i, zid in enumerate(t['zone_id']):
                if str(t['zone_level'][i]) != 'A20' and not str(zid).startswith('A'):
                    continue
                tex_state[str(zid)] = str(t['state'][i])

    qj = {}
    if (skin / 'quality.json').is_file():
        qj = json.loads((skin / 'quality.json').read_text(encoding='utf-8'))

    rows = []
    for i in range(20):
        z = f'A{i+1:02d}'
        m = dom & (A == i)
        px = int(m.sum())
        row = {
            'zone': z,
            'geometry_px': px,
            'geometry_frac': float(px / max(int(dom.sum()), 1)),
            'pose_w_mean': float(pw[m].mean()) if pw is not None and px else None,
            'quality_w_mean': float(qw[m].mean()) if qw is not None and px else None,
            'quality_pos_frac': float((qw[m] > 1e-8).mean()) if qw is not None and px else None,
            'conf_med': float(np.median(conf[m])) if conf is not None and px else None,
            'texture_state': tex_state.get(z),
            'geometry_without_evidence': bool(px >= 64 and qw is not None and float(qw[m].sum()) < 50),
        }
        rows.append(row)

    dens_meta = {
        'unique': int(len(np.unique(np.round(dens[dom], 5)))) if dens is not None and dom.any() else None,
        'median': float(np.median(dens[dom])) if dens is not None and dom.any() else None,
        'frac_ge_99': float((dens[dom] >= 99).mean()) if dens is not None and dom.any() else None,
    }
    return {
        'package': skin.parent.name,
        'yaw': (qj.get('pose') or {}).get('yaw'),
        'pose_bin_policy': (qj.get('pose_policy') or {}).get('selected_center_deg'),
        'implementation_status': qj.get('implementation_status'),
        'production_evidence_allowed': qj.get('production_evidence_allowed'),
        'usable_zones': sum(1 for r in rows if r['texture_state'] == 'usable'),
        'geometry_without_evidence_zones': sum(1 for r in rows if r['geometry_without_evidence']),
        'density': dens_meta,
        'zones': rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results_root', type=Path)
    ap.add_argument('--out', type=Path, default=None)
    args = ap.parse_args()
    root = args.results_root
    out = args.out or (root / '_geometry_vs_evidence_report')
    out.mkdir(parents=True, exist_ok=True)

    pkgs = []
    for p in sorted(root.iterdir()):
        skin = p / 'skin'
        if (skin / 'atlas_projection.npz').is_file():
            try:
                pkgs.append(analyze_pkg(skin))
            except Exception as e:
                pkgs.append({'package': p.name, 'error': str(e)})

    summary = {
        'n_packages': len(pkgs),
        'mean_usable_zones': float(np.mean([p.get('usable_zones', 0) for p in pkgs if 'error' not in p])) if pkgs else 0,
        'mean_geom_wo_evidence': float(np.mean([p.get('geometry_without_evidence_zones', 0) for p in pkgs if 'error' not in p])) if pkgs else 0,
        'packages': pkgs,
    }
    (out / 'report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    # CSV flat
    lines = ['package,yaw,zone,geometry_px,geometry_frac,pose_w_mean,quality_w_mean,texture_state,geometry_without_evidence']
    for p in pkgs:
        if 'error' in p:
            continue
        for z in p['zones']:
            lines.append(','.join([
                p['package'], str(p.get('yaw')), z['zone'], str(z['geometry_px']),
                f"{z['geometry_frac']:.6f}", str(z['pose_w_mean']), str(z['quality_w_mean']),
                str(z['texture_state']), str(z['geometry_without_evidence']),
            ]))
    (out / 'zones.csv').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print(f'packages={summary["n_packages"]} mean_usable={summary["mean_usable_zones"]:.2f} mean_geom_wo_ev={summary["mean_geom_wo_evidence"]:.2f}')
    print(f'wrote {out}')
    # fail if systemic geometry-without-evidence on large zones after patch expectation
    bad = 0
    for p in pkgs:
        if 'error' in p:
            continue
        for z in p['zones']:
            if z['geometry_frac'] >= 0.05 and z['geometry_without_evidence'] and (z['pose_w_mean'] or 0) == 0:
                # after patch pose_w may still be 0 (prior) but quality should not be dead if conf ok
                if (z['quality_w_mean'] or 0) <= 1e-8:
                    bad += 1
    if bad:
        print(f'WARN residual geometry-without-evidence large zones: {bad}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
