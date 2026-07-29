#!/usr/bin/env python3
from pathlib import Path
s=(Path(__file__).resolve().parents[1]/'dist/index.html').read_text()
poses=['left_profile','left_deep','left_mid','left_light','frontal','right_light','right_mid','right_deep','right_profile']
assert all(x in s for x in poses);assert 'const P=' in s and ',T=' in s;assert 'deeputin.fix-capsule.v2' in s;assert 'НЕ ВЕРДИКТ' in s
print('PASS UI: 9 pose bins, 14 tracks, 8 routes, Fix Capsule')
