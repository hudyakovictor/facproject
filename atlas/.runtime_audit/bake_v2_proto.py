import json, numpy as np, glob, os, cv2, sys, time
from PIL import Image, ImageOps, ImageDraw
sys.path.insert(0,'.')
ROOT='/Users/victorkhudyakov/work/atlas'; ASSETS='/Users/victorkhudyakov/work/3ddfa_v3/assets'
basis=np.load(os.path.join(ASSETS,'face_model.npy'),allow_pickle=True).item()
tri=np.asarray(basis['tri'],np.int32); uvt=basis['uv_coords'].astype(np.float32)

def bake(image_rgb, src_uv, uv, tri, cols, vert_vis, size=1024):
    image=np.asarray(image_rgb); h,w=image.shape[:2]
    dst=np.column_stack((uv[:,0]*(size-1),(1-uv[:,1])*(size-1)))
    src=np.column_stack((src_uv[:,0]*(w-1),(1-src_uv[:,1])*(h-1)))
    acc=np.zeros((size,size,3),np.float32); wt=np.zeros((size,size),np.float32)
    aacc=np.zeros((size,size,3),np.float32); at=np.zeros((size,size),np.float32)
    for ids in tri:
        d=dst[ids]; sp=src[ids]
        if abs(cv2.contourArea(d.astype(np.float32)))<.15: continue
        x0,y0=np.floor(d.min(0)).astype(int); x1,y1=np.ceil(d.max(0)).astype(int)
        x0,y0=max(0,x0),max(0,y0); x1,y1=min(size-1,x1),min(size-1,y1)
        if x1<=x0 or y1<=y0: continue
        local=d-np.array([x0,y0],np.float32)
        mask=np.zeros((y1-y0+1,x1-x0+1),np.uint8)
        cv2.fillConvexPoly(mask,np.round(local).astype(np.int32),1)
        yy,xx=np.where(mask!=0)
        if not len(xx): continue
        # barycentric
        v0,v1,v2=d
        den=(v1[1]-v2[1])*(v0[0]-v2[0])+(v2[0]-v1[0])*(v0[1]-v2[1])
        if abs(den)<1e-9: continue
        X=xx+x0; Y=yy+y0
        b0=((v1[1]-v2[1])*(X-v2[0])+(v2[0]-v1[0])*(Y-v2[1]))/den
        b1=((v2[1]-v0[1])*(X-v2[0])+(v0[0]-v2[0])*(Y-v2[1]))/den
        b2=1-b0-b1
        conf=b0*vert_vis[ids[0]]+b1*vert_vis[ids[1]]+b2*vert_vis[ids[2]]
        mat=cv2.getAffineTransform(d.astype(np.float32),sp.astype(np.float32))
        xy=mat@np.vstack((X,Y,np.ones(len(X),np.float32)))
        inside=(xy[0]>=0)&(xy[0]<=w-1)&(xy[1]>=0)&(xy[1]<=h-1)
        idx=np.flatnonzero(inside)
        if len(idx):
            sampled=cv2.remap(image,xy[0,idx].astype(np.float32).reshape(1,-1),xy[1,idx].astype(np.float32).reshape(1,-1),cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE).reshape(-1,3)
            acc[Y[idx],X[idx]]+=sampled.astype(np.float32)*conf[idx,None]
            wt[Y[idx],X[idx]]+=conf[idx]
        alb=b0[:,None]*cols[ids[0]]+b1[:,None]*cols[ids[1]]+b2[:,None]*cols[ids[2]]
        aacc[Y,X]+=alb; at[Y,X]+=1
    photo=np.zeros_like(acc); obs=wt>1e-6
    photo[obs]=np.clip(acc[obs]/wt[obs,None],0,255)
    albedo=np.zeros_like(acc); has=at>0
    albedo[has]=np.clip(aacc[has]/at[has,None],0,255)
    conf=np.clip(wt,0,1)[...,None]
    med=np.median(photo[obs],axis=0) if obs.any() else np.array([160,130,120],np.float32)
    flat=np.zeros_like(photo)+med
    atlas=np.where(has[...,None], np.where(obs[...,None], photo, flat), 0).astype(np.uint8)
    # crack fill from observed neighbours
    vis=obs.astype(np.uint8)
    near=cv2.dilate(vis,np.ones((3,3),np.uint8),iterations=1)>0
    cracks=near&~obs
    if cracks.any(): atlas[cracks]=cv2.inpaint(atlas,cracks.astype(np.uint8),2,cv2.INPAINT_TELEA)[cracks]
    return atlas, vis*255

pid='2a29f955863593e6'; meta=json.load(open(f'{ROOT}/cache/{pid}/meta.json'))
lib=json.load(open(f'{ROOT}/data/library.json')); photo=[p for p in lib['photos'] if p['id']==pid][0]
key=meta.get('feature_key',''); fp=[f for f in glob.glob(f'{ROOT}/cache/{pid}/features-*.npz') if key in f][0]
F=np.load(fp,allow_pickle=True); alpha=F['alpha'].astype(np.float64); alb=F['albedo'].astype(np.float32)
img=ImageOps.exif_transpose(Image.open(f'{ROOT}/'+photo['path'])).convert('RGB'); rgb=np.asarray(img); H,W=rgb.shape[:2]
shape=(basis['u'].reshape(-1)+basis['id']@alpha[:80]+basis['exp']@alpha[80:144]).reshape(-1,3)
x,y,z=alpha[224:227]
Rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
Ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
Rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
R=Rz@Ry@Rx
cam=shape@R.T+alpha[254:257]
depthn=10.0-cam[:,2]
px=1015.0*cam[:,0]/depthn+112.0; py=1015.0*cam[:,1]/depthn+112.0
left,top,scale=meta['alignment']['crop']; nw=max(1,int(round(W*scale))); nh=max(1,int(round(H*scale)))
ox=(px+left)/(nw/W); oy=(223.0-py+top)/(nh/H)
srcuv=np.stack([ox/(W-1),1-oy/(H-1)],-1).astype(np.float32)
# per-vertex normal + visibility
from scipy.spatial import cKDTree
p2=np.stack([ox,oy],-1)
cen=p2[tri].mean(1); cd=depthn[tri].mean(1)
tree=cKDTree(cen); el=np.median(np.linalg.norm(p2[tri[:,1]]-p2[tri[:,0]],axis=1)); rad=max(3.0,el*3)
idxs=tree.query_ball_point(p2,rad)
mind=np.array([cd[i].min() if len(i) else np.inf for i in idxs])
occ=depthn>mind+0.03
n=np.zeros_like(shape)
fn=np.cross(shape[tri[:,1]]-shape[tri[:,0]],shape[tri[:,2]]-shape[tri[:,0]])
for k in range(3): np.add.at(n,tri[:,k],fn)
n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-8)
cos=np.clip((n@R.T)[:,2],-1,1)
face=np.clip((cos-0.12)/0.35,0,1)
vis=(face*(~occ)).astype(np.float32)
print('vis stats',np.percentile(vis,[10,50,90]),'zero',(vis<=0).mean())
t=time.time(); atlas,mask=bake(rgb,srcuv,uvt,tri,alb*255,vis,1024); print('bake sec',round(time.time()-t,2))
Image.fromarray(atlas).save(f'{ROOT}/.runtime_audit/atlas_F_occ_flat.png')
