import json, numpy as np, glob, os, cv2
from PIL import Image, ImageOps
import sys
sys.path.insert(0,'.')
from server.uv_texture import bake_photo_to_uv
ROOT='/Users/victorkhudyakov/work/atlas'; ASSETS='/Users/victorkhudyakov/work/3ddfa_v3/assets'
basis=np.load(os.path.join(ASSETS,'face_model.npy'),allow_pickle=True).item()
tri=np.asarray(basis['tri'],np.int32); uvt=basis['uv_coords'].astype(np.float32)
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
depth=10.0-cam[:,2]
px=1015.0*cam[:,0]/depth+112.0; py=1015.0*cam[:,1]/depth+112.0
left,top,scale=meta['alignment']['crop']; nw=max(1,int(round(W*scale))); nh=max(1,int(round(H*scale)))
ox=(px+left)/(nw/W); oy=(223.0-py+top)/(nh/H)
src=np.stack([ox/(W-1),1-oy/(H-1)],-1).astype(np.float32)
# painter id buffer
S=512; sx=src[:,0]*(S-1); sy=(1-src[:,1])*(S-1)
order=np.argsort(cam[tri].mean(1)[:,2])  # far to near (z bigger = closer)
ids=np.full((S,S),-1,np.int32)
p2d=np.stack([sx,sy],-1)
for ti in order:
    t=tri[ti]; pts=p2d[t]
    x0,y0=np.floor(pts.min(0)).astype(int); x1,y1=np.ceil(pts.max(0)).astype(int)
    x0=max(0,x0); y0=max(0,y0); x1=min(S-1,x1); y1=min(S-1,y1)
    if x1<x0 or y1<y0: continue
    mask=np.zeros((y1-y0+1,x1-x0+1),np.uint8)
    cv2.fillConvexPoly(mask,(pts-[x0,y0]).round().astype(np.int32),1)
    ids[y0:y1+1,x0:x1+1][mask>0]=ti
# area each triangle covers (unoccluded)
flat=ids.ravel(); keep=flat[flat>=0]
counts=np.bincount(keep,minlength=len(tri))
# projected area
p0,p1,p2=p2d[tri[:,0]],p2d[tri[:,1]],p2d[tri[:,2]]
area=np.abs(np.cross(p1-p0,p2-p0))/2
ratio=np.divide(counts,np.maximum(area,1e-6))
print('ratio percentiles',np.percentile(ratio,[10,25,50,75,90]),'zero frac',(ratio<0.02).mean())
for th in (0.0,0.05,0.2,0.5):
    m=ratio>th
    atlas,_=bake_photo_to_uv(rgb,src,uvt,tri[m],1024)
    Image.fromarray(atlas).save(f'{ROOT}/.runtime_audit/atlas_vis_{int(th*100):02d}.png')
    print('th',th,'tris',m.sum())
# UV-space ratio visualization
import cv2
canvas=np.zeros((1024,1024,3),np.uint8)
color=np.zeros((len(tri),3),np.uint8)
color[:,0]=np.clip(ratio,0,1)*255
color[:,1]=(np.clip(ratio,0,1)**0.5)*120
color[:,2]=(1-np.clip(ratio,0,1))*180
dst=np.stack([uvt[:,0]*1023,(1-uvt[:,1])*1023],-1)
for ti,t in enumerate(tri):
    if ratio[ti]<0.2: continue
    cv2.fillConvexPoly(canvas,dst[t].astype(np.int32).reshape(-1,1,2),color[ti].tolist())
Image.fromarray(canvas).save(f'{ROOT}/.runtime_audit/uv_ratio.png')
# id buffer
vis=np.zeros((S,S,3),np.uint8)
vis[ids>=0]=[0,200,0]
Image.fromarray(vis).save(f'{ROOT}/.runtime_audit/idbuf.png')
# diff B vs vis20
b=np.asarray(Image.open(f'{ROOT}/.runtime_audit/atlas_B_fixed.png').convert('RGB')).astype(int)
v=np.asarray(Image.open(f'{ROOT}/.runtime_audit/atlas_vis_20.png').convert('RGB')).astype(int)
lost=(b.sum(2)>10)&(v.sum(2)<5)
print('lost texels',lost.sum(), 'of observed', (b.sum(2)>10).sum())
Image.fromarray((lost*255).astype(np.uint8)).save(f'{ROOT}/.runtime_audit/lost_mask.png')
