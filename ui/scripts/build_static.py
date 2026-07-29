#!/usr/bin/env python3
from pathlib import Path
import shutil
r=Path(__file__).resolve().parents[1];s=r/'static/index.html';o=r/'dist'
t=s.read_text();required=['left_profile','right_profile','Age curve','deeputin.fix-capsule.v2','3D Inspector']
missing=[x for x in required if x not in t]
if missing:raise SystemExit('missing '+','.join(missing))
if o.exists():shutil.rmtree(o)
o.mkdir();shutil.copy2(s,o/'index.html');print('built',o/'index.html')
