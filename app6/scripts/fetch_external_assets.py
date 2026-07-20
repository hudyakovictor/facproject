#!/usr/bin/env python3
"""Fetch hash-pinned 3DDFA assets. Unpinned downloads are rejected by default."""
from __future__ import annotations
import argparse, hashlib, json, urllib.request
from pathlib import Path
ASSETS={
 'face_model.npy':'https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/face_model.npy?download=true',
 'net_recon.pth':'https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/net_recon.pth?download=true',
 'net_recon_mbnet.pth':'https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/net_recon_mbnet.pth?download=true',
 'large_base_net.pth':'https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/large_base_net.pth?download=true',
 'retinaface_resnet50_2020-07-20_old_torch.pth':'https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/retinaface_resnet50_2020-07-20_old_torch.pth?download=true',
 'similarity_Lm3D_all.mat':'https://huggingface.co/datasets/Zidu-Wang/3DDFA-V3/resolve/main/assets/similarity_Lm3D_all.mat?download=true'}

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',default='assets');p.add_argument('--mobile',action='store_true')
    p.add_argument('--force',action='store_true')
    p.add_argument('--expected-hashes',required=True,help='JSON mapping filename to approved SHA-256')
    a=p.parse_args(); expected=json.loads(Path(a.expected_hashes).read_text())
    o=Path(a.output);o.mkdir(parents=True,exist_ok=True)
    names=['face_model.npy','net_recon_mbnet.pth' if a.mobile else 'net_recon.pth','large_base_net.pth','retinaface_resnet50_2020-07-20_old_torch.pth','similarity_Lm3D_all.mat'];m={}
    missing=[n for n in names if not isinstance(expected.get(n),str) or len(expected[n])!=64]
    if missing: raise SystemExit('missing approved SHA-256: '+', '.join(missing))
    for n in names:
        q=o/n
        if not q.exists() or a.force:
            tmp=q.with_suffix(q.suffix+'.partial');print('download',n,flush=True)
            urllib.request.urlretrieve(ASSETS[n],tmp)
            got=sha(tmp)
            if got.lower()!=expected[n].lower():
                tmp.unlink(missing_ok=True);raise SystemExit(f'SHA-256 mismatch for {n}: {got}')
            tmp.replace(q)
        got=sha(q)
        if got.lower()!=expected[n].lower(): raise SystemExit(f'existing asset SHA-256 mismatch for {n}: {got}')
        m[n]={'sha256':got,'bytes':q.stat().st_size,'source':ASSETS[n]}
    (o/'ASSET_MANIFEST.json').write_text(json.dumps(m,indent=2));print(json.dumps(m,indent=2))
if __name__=='__main__': main()
