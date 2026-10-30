import json, numpy as np, glob, os
from PIL import Image, ImageOps, ImageDraw

ROOT='/Users/victorkhudyakov/work/atlas'
ASSETS='/Users/victorkhudyakov/work/3ddfa_v3/assets'
basis=np.load(os.path.join(ASSETS,'face_model.npy'),allow_pickle=True).item()
print('basis keys:', list(basis.keys())[:20])
uv=basis['uv_coords']; print('uv_coords', uv.shape, uv.min(0), uv.max(0))

pid='2a29f955863593e6'
meta=json.load(open(f'{ROOT}/cache/{pid}/meta.json'))
lib=json.load(open(f'{ROOT}/data/library.json'))
photo=[p for p in lib['photos'] if p['id']==pid][0]
feat_files=glob.glob(f'{ROOT}/cache/{pid}/features-*.npz')
print('features', feat_files)
# choose feature matching meta feature_key if available
key=meta.get('feature_key')
feat=[f for f in feat_files if key and key in f] or feat_files
print('use', feat)
f=np.load(feat[0], allow_pickle=True)
alpha=f['alpha'].astype(np.float64)
print('alpha', alpha.shape, 'angles deg', np.degrees(alpha[224:227]))

img=ImageOps.exif_transpose(Image.open(f'{ROOT}/'+photo['path'])).convert('RGB')
W,H=img.size
print('image', img.size, 'alignment', meta['alignment'])

def shape_from(alpha):
    return (basis['u'].reshape(-1)+basis['id']@alpha[:80]+basis['exp']@alpha[80:144]).reshape(-1,3)

def project(alpha, transpose):
    a=alpha
    x,y,z=a[224:227]
    Rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
    Ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
    Rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
    R = Rz@Ry@Rx
    shape=shape_from(a)
    # variant A: current code: shape @ R
    # variant B: upstream: shape @ R.T
    cam = shape @ (R.T if transpose else R) + a[254:257]
    depth=10.0-cam[:,2]
    px=1015.0*cam[:,0]/depth+112.0
    py=1015.0*cam[:,1]/depth+112.0
    left,top,scale=meta['alignment']['crop']
    nw=max(1,int(round(W*scale))); nh=max(1,int(round(H*scale)))
    ox=(px+left)/(nw/W); oy=(223.0-py+top)/(nh/H)
    u=ox/max(1,W-1); v=1-oy/max(1,H-1)
    return np.stack([u,v],-1), np.stack([ox,oy],-1)

ldm68=np.asarray(basis['ldm68'],np.int32).reshape(-1)
for tr in (False,True):
    uv2, pix = project(alpha, tr)
    pts=pix[ldm68]
    print('transpose',tr,'pix range', np.nanmin(pts,0), np.nanmax(pts,0))

# overlay with both
det=json.load(open(f'{ROOT}/cache/{pid}/ocular-detection.json'))
mp=np.array(det['points'],np.float64)
print('mp size', det['width'], det['height'], 'img', W,H)
mp[:,0]*=W/det['width']; mp[:,1]*=H/det['height']

buf=img.copy(); d=ImageDraw.Draw(buf)
# mp points small red
for x,y in mp[::2]:
    d.ellipse([x-1,y-1,x+1,y+1], fill=(255,0,0))
_,pixA=project(alpha,False); _,pixB=project(alpha,True)
for name,pix,col in (('A',pixA,(0,255,0)),('B',pixB,(0,120,255))):
    pts=pix[ldm68]
    r=3 if name=='A' else 1
    for x,y in pts:
        d.ellipse([x-r,y-r,x+r,y+r], outline=col, width=1)
buf.save(f'{ROOT}/.runtime_audit/overlay_both.png')
print('saved overlay')

# numeric: compare 3DDFA eye corners etc with nearest MP landmark in a generous neighborhood
for name,pix in (('A',pixA),('B',pixB)):
    pts=pix[ldm68]
    ds=[]
    for i in [36,39,42,45,30,48,54,8,0,16]:
        dd=np.linalg.norm(mp-pts[i],axis=1)
        j=int(dd.argmin()); ds.append((i,j,round(float(dd[j]),1)))
    print(name, ds)
