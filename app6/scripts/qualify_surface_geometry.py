#!/usr/bin/env python3
"""🔬 EXPERIMENTAL → Квалификация качества surface-геометрии (кривизны/границы).
🔗 DEPENDS ON: stage1.skin.surface_geometry
💡 NOTE: диагностика; отказ = warning, пайплайн не блокируется.
"""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from app6.stage1.skin.surface_geometry import SurfaceGeometry
p=argparse.ArgumentParser();p.add_argument('--face-model',default='assets/face_model.npy');a=p.parse_args();m=np.load(a.face_model,allow_pickle=True).item();v=m['u'].reshape(-1,3);f=m['tri'];g=SurfaceGeometry(v,f,True);pairs=[(int(m['ldm68'][i]),int(m['ldm68'][j])) for i,j in ((0,16),(36,45),(31,35),(48,54))];rows=[]
for s,t in pairs:
 t0=time.perf_counter();ds=g.distance(s);dt=g.distance(t);rows.append({'source':s,'target':t,'d_st':float(ds[t]),'d_ts':float(dt[s]),'symmetry_error':float(abs(ds[t]-dt[s])),'roundtrip_vector_error':g.transport_roundtrip_error(s,t),'seconds':time.perf_counter()-t0})
print(json.dumps({'schema':'surface-geometry-qualification-v1','metadata':g.metadata(),'pairs':rows},indent=2))
