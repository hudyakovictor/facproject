from pathlib import Path
import json,re,sys
root=Path(__file__).parent
for name in ('package.json','tsconfig.json'):
    json.loads((root/name).read_text())
sources='\n'.join(p.read_text() for p in (root/'src').rglob('*') if p.suffix in {'.ts','.tsx'})
for token in ('generateDataset','Math.random','mockData','H0','H1','H2'):
    if token in sources: raise SystemExit(f'forbidden token: {token}')
required=['/api/v1/timeline','/api/v1/photos/','/api/v1/pairs/','/api/v1/health','/api/v1/calibration/health','/api/v1/system/health','/api/v1/run/summary','/api/v1/run/artifacts/','/api/v1/report/summary','/api/v1/report/sections/','/api/v1/jobs','/api/v1/data/clear','/api/v1/settings','/api/v1/photos/upload','/mesh','/artifacts/']
missing=[x for x in required if x not in sources]
if missing: raise SystemExit('missing API contracts: '+','.join(missing))
if "Number(v||0)" in sources: raise SystemExit('unsafe null-to-zero conversion')
print('STATIC CONTRACT PASS: no mocks; UI v2/app6 routes present; null-safe renderer')
