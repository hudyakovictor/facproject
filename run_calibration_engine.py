#!/usr/bin/env python3
"""Run full stage1 engine on calibration dataset."""
import sys
sys.path.insert(0, '/Users/victorkhudyakov/work')
sys.path.insert(0, '/Users/victorkhudyakov/work/3ddfa_v3')

from app6.stage1.config import Stage1Config
from app6.stage1.engine import Stage1Engine
from app6.stage1.utils import atomic_json

from pathlib import Path
ROOT = Path('/Users/victorkhudyakov/work')
cfg = Stage1Config(
    project_root=ROOT,
    input_dir=Path('/Volumes/SDCARD/storage/calibration_input'),
    output_dir=Path('/Volumes/SDCARD/storage/stage1'),
    device='auto',
    overwrite=False,
)
engine = Stage1Engine(cfg)
manifest = engine.run()
print('DONE', flush=True)
