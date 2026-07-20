#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from app6.stage1.skin.atlas_registry import AtlasRegistry
from app6.stage1.skin.patch_registry import build_patch_registry
p=argparse.ArgumentParser();p.add_argument('--face-model',default='assets/face_model.npy');p.add_argument('--atlas',default='app6/atlas/texture_zones_bfm35709_v3.npz');p.add_argument('--output',default='app6/atlas/canonical_patches_v1.json');a=p.parse_args();m=np.load(a.face_model,allow_pickle=True).item();atlas=AtlasRegistry(a.atlas,m['tri']);q=build_patch_registry(m['u'].reshape(-1,3),m['tri'],m['uv_coords'],atlas);Path(a.output).write_text(json.dumps(q,indent=2));print(a.output)
