#!/usr/bin/env python3
"""🔬 EXPERIMENTAL → Бенчмарк скорости сборки skin-пакета на корпусе фото.
🔗 DEPENDS ON: stage1.skin.pipeline
💡 NOTE: только диагностика производительности; на контракты не влияет.
"""
import argparse,json,time,resource
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--skin-package',required=True);a=p.parse_args();r=Path(a.skin_package);rows=[]
for name in ('surface_observations.npz','atlas_projection.npz','quality_maps.npz','features/texture.npz','wrinkles/classical.npz'):
 q=r/name;t=time.perf_counter()
 with np.load(q,allow_pickle=False) as z:shapes={k:list(z[k].shape) for k in z.files}
 rows.append({'file':name,'bytes':q.stat().st_size,'load_seconds':time.perf_counter()-t,'arrays':shapes})
print(json.dumps({'schema':'skin-package-benchmark-v1','files':rows,'peak_rss_platform_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2))
