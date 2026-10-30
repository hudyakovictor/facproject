import json,numpy as np,glob,os
from scipy.spatial import cKDTree
ROOT='/Users/victorkhudyakov/work/atlas'; ASSETS='/Users/victorkhudyakov/work/3ddfa_v3/assets'
basis=np.load(os.path.join(ASSETS,'face_model.npy'),allow_pickle=True).item()
tri=np.asarray(basis['tri'],np.int32)
pid='2a29f955863593e6'; meta=json.load(open(f'{ROOT}/cache/{pid}/meta.json'))
key=meta['feature_key']; fp=[f for f in glob.glob(f'{ROOT}/cache/{pid}/features-*.npz') if key in f][0]
a=np.load(fp,allow_pickle=True)['alpha'].astype(np.float64)
shape=(basis['u'].reshape(-1)+basis['id']@a[:80]+basis['exp']@a[80:144]).reshape(-1,3)
x,y,z=a[224:227]
Rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
Ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
Rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
R=Rz@Ry@Rx; cam=shape@R.T+a[254:257]
d=10.0-cam[:,2]; px=1015.0*cam[:,0]/d+112.0; py=1015.0*cam[:,1]/d+112.0
left,top,scale=meta['alignment']['crop']; W=800; H=800
nw=max(1,int(round(W*scale))); nh=max(1,int(round(H*scale)))
sx=(px+left)/(nw/W); sy=(223.0-py+top)/(nh/H)
p2=np.stack([sx,sy],-1)
cen=p2[tri].mean(1); cd=d[tri].mean(1)
tree=cKDTree(cen)
# local edge length estimate
el=np.median(np.linalg.norm(p2[tri[:,1]]-p2[tri[:,0]],axis=1))
print('median edge px',el)
for rad in (max(2.0,el*1.5), max(3.0,el*3)):
    idxs=tree.query_ball_point(p2,rad)
    mind=np.array([cd[i].min() if len(i) else np.inf for i in idxs])
    occluded=d>mind+0.03
    print('radius',round(rad,1),'occluded frac',occluded.mean())
n=np.zeros_like(shape); fn=np.cross(shape[tri[:,1]]-shape[tri[:,0]],shape[tri[:,2]]-shape[tri[:,0]])
for k in range(3): np.add.at(n,tri[:,k],fn)
n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-8); cos=np.clip((n@R.T)[:,2],-1,1)
idx=tree.query_ball_point(p2,rad); mind=np.array([cd[i].min() if len(i) else np.inf for i in idx])
occ=d>mind+0.03
print('occluded & facing', (occ&(cos>0)).mean(), 'facing', (cos>0).mean(), 'occ',occ.mean())
np.save(f'{ROOT}/.runtime_audit/vis_occ.npy',occ)
np.save(f'{ROOT}/.runtime_audit/vis_cos.npy',cos)
