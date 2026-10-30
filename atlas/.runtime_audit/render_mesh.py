import json, numpy as np, sys
from PIL import Image
ROOT='/Users/victorkhudyakov/work/atlas'
topo=json.load(open(f'{ROOT}/data/topology.json'))
tri=np.asarray(topo['triangles'],np.int32); uv=np.asarray(topo['uv'],np.float32)
base=np.asarray(topo['mean'],np.float32)
feat=np.load(f'{ROOT}/cache/2a29f955863593e6/features-a32e4210936076d7.npz',allow_pickle=True)
verts=feat['vertices'].astype(np.float32)
def render(atlas_path, out, yaw_deg=0, size=560, fill=None):
    atlas=np.asarray(Image.open(atlas_path).convert('RGB'))
    S=atlas.shape[0]
    img=np.zeros((size,size,3),np.uint8); zbuf=np.full((size,size),1e9,np.float32)
    yaw=np.radians(yaw_deg); cy,sy=np.cos(yaw),np.sin(yaw)
    v=verts.copy()
    x=v[:,0]*cy + v[:,2]*sy
    z=-v[:,0]*sy + v[:,2]*cy
    px=(x*0.34+0.5)*size
    py=(0.5-(v[:,1]+0.41)*0.34)*size
    depth=-z
    for t in tri:
        i0,i1,i2=t
        x0,y0,x1,y1,x2,y2=px[i0],py[i0],px[i1],py[i1],px[i2],py[i2]
        minx=max(int(np.floor(min(x0,x1,x2))),0); maxx=min(int(np.ceil(max(x0,x1,x2))),size-1)
        miny=max(int(np.floor(min(y0,y1,y2))),0); maxy=min(int(np.ceil(max(y0,y1,y2))),size-1)
        if maxx<minx or maxy<miny: continue
        d=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(d)<1e-12: continue
        xs=np.arange(minx,maxx+1)+0.5; ys=np.arange(miny,maxy+1)[:,None]+0.5
        w0=((y1-y2)*(xs-x2)+(x2-x1)*(ys-y2))/d
        w1=((y2-y0)*(xs-x2)+(x0-x2)*(ys-y2))/d
        w2=1-w0-w1
        mask=(w0>=0)&(w1>=0)&(w2>=0)
        if not mask.any(): continue
        z=w0*depth[i0]+w1*depth[i1]+w2*depth[i2]
        yy,xx=np.where(mask)
        zz=z[yy,xx]
        sub=zbuf[miny:miny+len(ys),minx:minx+len(xs)]
        better=zz<sub[yy,xx]
        if not better.any(): continue
        yy=yy[better]; xx=xx[better]; zz=zz[better]
        u=w0[yy,xx]*uv[i0,0]+w1[yy,xx]*uv[i1,0]+w2[yy,xx]*uv[i2,0]
        vv=w0[yy,xx]*uv[i0,1]+w1[yy,xx]*uv[i1,1]+w2[yy,xx]*uv[i2,1]
        ax=np.clip((u*(S-1)).astype(int),0,S-1); ay=np.clip(((1-vv)*(S-1)).astype(int),0,S-1)
        rgb=atlas[ay,ax]
        gy=yy+miny; gx=xx+minx
        img[gy,gx]=rgb; zbuf[gy,gx]=zz
    Image.fromarray(img).save(out)
    print('saved',out)
render(f'{ROOT}/.runtime_audit/atlas_F_occ_flat.png',f'{ROOT}/.runtime_audit/mesh_F.png',0)
render(f'{ROOT}/.runtime_audit/atlas_F_occ_flat.png',f'{ROOT}/.runtime_audit/mesh_F_yaw35.png',35)
