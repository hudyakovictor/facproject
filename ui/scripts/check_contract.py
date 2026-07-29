#!/usr/bin/env python3
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
package=json.loads((root/'package.json').read_text())
assert package['dependencies']['react'].startswith('19.')
assert package['scripts']['build']=='tsc --noEmit && vite build'
files={p.name:p.read_text() for p in [root/'src/data.ts',root/'src/App.tsx',root/'src/api.ts',root/'src/components/AnalysisViews.tsx']}
poses=['left_profile','left_deep','left_mid','left_light','frontal','right_light','right_mid','right_deep','right_profile']
assert all(p in files['data.ts'] for p in poses)
views=['FULL','MATRIX','CLUSTER','COMPARE','INSPECTOR','DRIFT','METRICS','STATS']
assert all(v in files['App.tsx'] for v in views)
assert '/api/v1/timeline' in files['api.ts']
assert 'deeputin.fix-capsule.v2' in files['api.ts']
assert 'НЕ ВЕРДИКТ' in files['App.tsx']
assert not (root/'static').exists() and not (root/'scripts/build_static.py').exists()
print('PASS React UI contract: React/Vite, 9 poses, 8 modes, API, Fix Capsule v2')
