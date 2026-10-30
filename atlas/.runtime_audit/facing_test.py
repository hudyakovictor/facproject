import json, numpy as np, glob, os, cv2
from PIL import Image, ImageOps
import sys
sys.path.insert(0,'.')
from server.uv_texture import bake_photo_to_uv
ROOT='/Users/victorkhudyakov/work/atlas'; ASSETS='/Users/victorkhudyakov/work/3ddfa_v3/assets'
basis=np.load(os.path.join(ASSETS,'face_model.npy'),allow_pickle=True).item()
tri=np.asarray(basis['tri'],np.int32); uv=basis['uv_coords'].astype(np.float32)
pid='2a29f955863593e6'; meta=json.load(open(f'{ROOT}/cache/{pid}/meta.json'))
lib=json.load(open(f'{ROOT}/data/library.json')); photo=[p for p in lib['photos'] if p['id']==pid][0]
key=meta.get('feature_key',''); fp=[f for f in glob.glob(f'{ROOT}/cache/{pid}/features-*.npz') if key in f][0]
alpha=np.load(fp,allow_pickle=True)['alpha'].astype(np.float64)
img=ImageOps.exif_transpose(Image.open(f'{ROOT}/'+photo['path'])).convert('RGB'); rgb=np.asarray(img); H,W=rgb.shape[:2]
shape=(basis['u'].reshape(-1)+basis['id']@alpha[:80]+basis['exp']@alpha[80:144]).reshape(-1,3)
x,y,z=alpha[224:227]
Rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
Ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
Rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
cam=shape@(Rz@Ry@Rx).T+alpha[254:257]
depth=10.0-cam[:,2]; px=1015.0*cam[:,0]/depth+112.0; py=1015.0*cam[:,1]/depth+112.0
left,top,scale=meta['alignment']['crop']; nw=max(1,int(round(W*scale))); nh=max(1,int(round(H*scale)))
ox=(px+left)/(nw/W); oy=(223.0-py+top)/(nh/H)
src=np.stack([ox/(W-1),1-oy/(H-1)],-1).astype(np.float32)
# signed area in SOURCE image space (pixels, y down)
p=src*np.array([W-1,H-1],np.float32)
a=0.5*np.cross(p[tri[:,1]]-p[tri[:,0]], p[tri[:,2]]-p[tri[:,0]])
print('2D area pos frac', (a>0).mean(), 'median', np.median(a), 'tiny', (np.abs(a)<1e-3).mean())
# signed area in UV space
quv=uv.copy(); q=quv*np.array([1023,1023])
au=0.5*np.cross(q[tri[:,1]]-q[tri[:,0]], q[tri[:,2]]-q[tri[:,0]])
print('UV area pos frac', (au>0).mean())
# correlation between area signs
print('sign agreement', ((a>0)==(au>0)).mean())
for name,mask in (('pos',a>0),('neg',a<0)):
    atlas,m=bake_photo_to_uv(rgb,src,uv,tri[mask],1024)
    Image.fromarray(atlas).save(f'{ROOT}/.runtime_audit/atlas_src_{name}.png')
    print(name,'coverage',(m>0).mean(),'tris',mask.sum())
