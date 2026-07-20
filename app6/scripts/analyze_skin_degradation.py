#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--stage1',required=True);p.add_argument('--output',required=True);a=p.parse_args();rows=[]
for d in Path(a.stage1).iterdir():
 q=d/'skin/sensitivity/degradation.json'
 if not q.is_file():continue
 x=json.loads(q.read_text())['rows'];v={r['variant']:r.get('value') for r in x if r.get('status')=='measured'};blur=[v.get(f'blur_{s}') for s in (1.0,2.0,3.0)];jpeg=[v.get(f'jpeg_{q}') for q in (90,70,50,30)];down=[v.get(f'down_{s}') for s in (.75,.5,.35)];mono=lambda z:all(z[i]>=z[i+1] for i in range(len(z)-1)) if all(x is not None for x in z) else None;rows.append({'photo_id':d.name,'raw':v.get('raw'),'blur_monotonic':mono(blur),'jpeg_monotonic':mono(jpeg),'downsample_monotonic':mono(down)})
report={'schema':'skin-degradation-report-v1','photos':len(rows),'blur_monotonic_rate':float(np.mean([r['blur_monotonic'] for r in rows if r['blur_monotonic'] is not None])) if rows else None,'jpeg_monotonic_rate':float(np.mean([r['jpeg_monotonic'] for r in rows if r['jpeg_monotonic'] is not None])) if rows else None,'downsample_monotonic_rate':float(np.mean([r['downsample_monotonic'] for r in rows if r['downsample_monotonic'] is not None])) if rows else None,'rows':rows};Path(a.output).write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
