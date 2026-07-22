#!/usr/bin/env python3
"""📤 Экспорт соответствий зон атласа ↔ mesh-индексы для внешних инструментов.
🔗 DEPENDS ON: stage1.skin_zone_atlas_final.export_contract()
💡 NOTE: чистая выгрузка; ничего не пересчитывает.
"""
import argparse,numpy as np
p=argparse.ArgumentParser();p.add_argument('--source-tri',required=True);p.add_argument('--target-tri',required=True);p.add_argument('--source-to-target-vertex',required=True);p.add_argument('--output',required=True);p.add_argument('--min-coverage',type=float,default=.995);a=p.parse_args();sf=np.load(a.source_tri);tf=np.load(a.target_tri);mp=np.load(a.source_to_target_vertex);lut={tuple(sorted(map(int,t))):i for i,t in enumerate(tf)};fm=np.full(len(sf),-1,np.int64)
for i,t in enumerate(sf):
 q=mp[t]
 if np.all(q>=0):fm[i]=lut.get(tuple(sorted(map(int,q))),-1)
cov=float(np.mean(fm>=0))
if cov<a.min_coverage:raise SystemExit(f'FAIL-LOUD: exact face coverage {cov:.3%} below {a.min_coverage:.3%}; no output')
if len(np.unique(fm[fm>=0]))!=np.sum(fm>=0):raise SystemExit('FAIL-LOUD: mapping is not bijective')
np.savez_compressed(a.output,source_face_to_target_face=fm,coverage=np.array(cov));print(cov)
