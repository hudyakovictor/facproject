#!/usr/bin/env python3
"""Deterministic mean-mesh smoke test for the complete skin package, no Torch."""
import argparse,cv2,json,shutil,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from app6.stage1.skin.pipeline import build_skin_package
from app6.stage2.skin.loader import SkinPackage
p=argparse.ArgumentParser();p.add_argument('--face-model',default='assets/face_model.npy');p.add_argument('--output',default='/tmp/facproject_skin_smoke');a=p.parse_args();m=np.load(a.face_model,allow_pickle=True).item();v=m['u'].reshape(-1,3).astype('f4');f=m['tri'].astype('i4');n=np.zeros_like(v);fn=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
for k in range(3):np.add.at(n,f[:,k],fn)
n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-8);xy=np.c_[256+v[:,0]*270,270-v[:,1]*245].astype('f4');Y,X=np.mgrid[:512,:512];im=np.dstack((80+X/4,70+Y/5,90+(X+Y)/8)).clip(0,255).astype('u1');o=Path(a.output);shutil.rmtree(o,ignore_errors=True);o.mkdir();cv2.imwrite(str(o/'input.png'),im);np.savez_compressed(o/'face_mask.npz',mask_original=np.ones((512,512),bool));r=build_skin_package(photo_id='smoke',input_path=o/'input.png',bgr=im,out_dir=o,triangles=f,vertices_original_xy=xy,vertices_depth=-v[:,2],normals=n,surface_vertices=v,vertex_visibility=np.ones(len(v),bool),face_mask_data_path=o/'face_mask.npz',atlas_path=ROOT/'app6/atlas/texture_zones_bfm35709_v3.npz',coordinate_chain={'smoke':True},models={'mean_mesh':True},config={'smoke':True},pose={'yaw':0});SkinPackage(o/'skin');print(json.dumps({'ok':True,'products':len(r['products']),'output':str(o)},indent=2))
