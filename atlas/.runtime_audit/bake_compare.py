import json, numpy as np, glob, os
from PIL import Image, ImageOps
import sys
sys.path.insert(0,'.')
from server.uv_texture import bake_photo_to_uv
ROOT='/Users/victorkhudyakov/work/atlas'
ASSETS='/Users/victorkhudyakov/work/3ddfa_v3/assets'
basis=np.load(os.path.join(ASSETS,'face_model.npy'),allow_pickle=True).item()
tri=np.asarray(basis['tri'],np.int32); uv=basis['uv_coords'].astype(np.float32)
ldm68=np.asarray(basis['ldm68'],np.int32).reshape(-1)
pid='2a29f955863593e6'
meta=json.load(open(f'{ROOT}/cache/{pid}/meta.json'))
lib=json.load(open(f'{ROOT}/data/library.json'))
photo=[p for p in lib['photos'] if p['id']==pid][0]
key=meta.get('feature_key','')
fp=[f for f in glob.glob(f'{ROOT}/cache/{pid}/features-*.npz') if key in f][0]
f=np.load(fp,allow_pickle=True); alpha=f['alpha'].astype(np.float64)
img=ImageOps.exif_transpose(Image.open(f'{ROOT}/'+photo['path'])).convert('RGB')
rgb=np.asarray(img); H,W=rgb.shape[:2]
shape=(basis['u'].reshape(-1)+basis['id']@alpha[:80]+basis['exp']@alpha[80:144]).reshape(-1,3)
x,y,z=alpha[224:227]
Rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
Ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
Rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
R=Rz@Ry@Rx
camT=shape@R.T+alpha[254:257]
camR=shape@R+alpha[254:257]
left,top,scale=meta['alignment']['crop']
nw=max(1,int(round(W*scale))); nh=max(1,int(round(H*scale)))
def cam2uv(cam):
    depth=10.0-cam[:,2]
    px=1015.0*cam[:,0]/depth+112.0
    py=1015.0*cam[:,1]/depth+112.0
    ox=(px+left)/(nw/W); oy=(223.0-py+top)/(nh/H)
    return np.stack([ox/max(1,W-1),1-oy/max(1,H-1)],-1).astype(np.float32)
for name,cam in (('A_current',camR),('B_fixed',camT)):
    src=cam2uv(cam)
    atlas,mask=bake_photo_to_uv(rgb,src,uv,tri,1024)
    Image.fromarray(atlas).save(f'{ROOT}/.runtime_audit/atlas_{name}.png')
    print(name,'coverage', (mask>0).mean())
# UV layout preview: draw mesh triangles in UV space colored by facing
cam=camT
p0,p1,p2=cam[tri[:,0]],cam[tri[:,1]],cam[tri[:,2]]
n=np.cross(p1-p0,p2-p0)
# camera looks along -z? depth = 10 - z, so view dir from point to camera +z. front face if n_z>0
front=(n[:,2]>0)
canon=np.zeros((1024,1024,3),np.uint8)
dst=np.stack([uv[:,0]*1023,(1-uv[:,1])*1023],-1)
import cv2
for ids,vis in zip(tri,front):
    pts=dst[ids].astype(np.int32).reshape(-1,1,2)
    cv2.fillConvexPoly(canon,pts,(0,140,0) if vis else (0,0,120))
Image.fromarray(canon).save(f'{ROOT}/.runtime_audit/uv_facing.png')
print('front triangles',front.mean())
# bake culled: only front triangles (remove back)
src=cam2uv(cam)
atlas2,mask2=bake_photo_to_uv(rgb,src,uv,tri[front],1024)
Image.fromarray(atlas2).save(f'{ROOT}/.runtime_audit/atlas_C_fixed_culled.png')
print('culled coverage',(mask2>0).mean())
