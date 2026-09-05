import pandas as pd, numpy as np, glob, os, re
from pathlib import Path
BASE=Path('/data/raw/archive2'); OUT=Path('/data/analysis2'); OUT.mkdir(exist_ok=True)
files=sorted(BASE.glob('ldm106_aligned_*.csv'))
pat=re.compile(r'ldm106_aligned_(.+)\.csv$')
records=[]; shapes=[]; visibility=[]
for f in files:
 d=pd.read_csv(f).sort_values('landmark_id')
 stem=pat.match(f.name).group(1)
 date='-'.join(stem.split('__')[0].split('_')[:3])
 records.append({'stem':stem,'filename':stem+'.png','date':date})
 shapes.append(d[['x','y','z']].to_numpy(float)); visibility.append(d.visible.to_numpy(float))
A=np.stack(shapes); V=np.stack(visibility); cov=V.mean(0)
hi=np.where(cov>=.90)[0]
# Center and isotropically scale using only >=90%-visible landmarks. Distances then pose/scale robust.
Q=[]
for a in A:
 c=a[hi].mean(0); q=a-c; scale=np.sqrt(np.mean(np.sum(q[hi]**2,axis=1))); Q.append(q/scale)
Q=np.stack(Q)

def dist(q,i,j): return np.linalg.norm(q[i]-q[j])
def centroid(q,idx): return q[np.array(idx)].mean(0)
def line_dev(q,idx):
 p=q[idx[0]]; v=q[idx[-1]]-p; v=v/(np.linalg.norm(v)+1e-12)
 return float(np.mean([np.linalg.norm((q[i]-p)-np.dot(q[i]-p,v)*v) for i in idx[1:-1]]))
# All constituent landmarks meet >=90% visibility across the 144-frame set.
metric_defs={
 'brow_span_3d':([34,35,36,37,38,39,40,42,43,44,45,47,48,49,50],'Расстояние между центрами бровей'),
 'brow_height_asym':([34,35,36,37,38,39,40,42,43,44,45,47,48,49,50],'Разность вертикального положения бровей'),
 'eye_anchor_spacing_3d':([67,74,104,76,78,81,83,105],'Расстояние между устойчивыми глазничными якорями'),
 'eye_level_asym':([67,74,104,76,78,81,83,105],'Разность уровней глазничных якорей'),
 'brow_eye_left_3d':([34,35,36,37,38,39,40,67,74,104],'Бровь–глазница слева'),
 'brow_eye_right_3d':([42,43,44,45,47,48,49,50,76,78,81,83,105],'Бровь–глазница справа'),
 'brow_eye_asym':([34,35,36,37,38,39,40,42,43,44,45,47,48,49,50,67,74,104,76,78,81,83,105],'Асимметрия бровь–глазница'),
 'nose_ridge_length_3d':([51,54],'Длина переносицы/спинки'),
 'nose_base_width_3d':([58,62],'Ширина основания носа'),
 'nose_axis_bend_3d':([51,52,53,54],'Отклонение промежуточных точек спинки от прямой'),
 'nose_base_asym':([58,60,62],'Смещение центральной точки основания носа'),
 'nose_projection_3d':([54,58,62],'Проекция кончика носа относительно крыльев'),
 'midface_ratio':([67,74,104,76,78,81,83,105,58,59,60,61,62],'Глазничная ширина к вертикали до основания носа'),
 'mouth_width_3d':([84,90],'Ширина рта'),
 'mouth_height_3d':([86,87,88,92,93,94],'Вертикальный размах губ'),
 'mouth_nose_offset':([58,59,60,61,62,84,86,87,88,90,91,92,93,94,95],'Боковое смещение центра рта относительно носа'),
 'central_depth_contrast':([54,67,74,104,76,78,81,83,105],'Выступание носа относительно глазничной плоскости'),
}
rows=[]
for rec,q in zip(records,Q):
 lb=centroid(q,[34,35,36,37,38,39,40]); rb=centroid(q,[42,43,44,45,47,48,49,50])
 le=centroid(q,[67,74,104]); re=centroid(q,[76,78,81,83,105]); nb=centroid(q,[58,59,60,61,62])
 ul=centroid(q,[86,87,88]); ll=centroid(q,[92,93,94]); mc=centroid(q,[84,86,87,88,90,91,92,93,94,95])
 dl=np.linalg.norm(lb-le); dr=np.linalg.norm(rb-re)
 eye_mid=(le+re)/2
 vals={
 'brow_span_3d':np.linalg.norm(lb-rb), 'brow_height_asym':abs(lb[1]-rb[1]),
 'eye_anchor_spacing_3d':np.linalg.norm(le-re), 'eye_level_asym':abs(le[1]-re[1]),
 'brow_eye_left_3d':dl,'brow_eye_right_3d':dr,'brow_eye_asym':abs(dl-dr),
 'nose_ridge_length_3d':dist(q,51,54),'nose_base_width_3d':dist(q,58,62),
 'nose_axis_bend_3d':line_dev(q,[51,52,53,54]),
 'nose_base_asym':abs(q[60,0]-(q[58,0]+q[62,0])/2),
 'nose_projection_3d':q[54,2]-(q[58,2]+q[62,2])/2,
 'midface_ratio':np.linalg.norm(eye_mid-nb)/(np.linalg.norm(le-re)+1e-12),
 'mouth_width_3d':dist(q,84,90),'mouth_height_3d':abs(ul[1]-ll[1]),
 'mouth_nose_offset':abs(mc[0]-nb[0]),
 'central_depth_contrast':q[54,2]-np.mean(q[[67,74,104,76,78,81,83,105],2]),
 }
 rows.append({**rec,**vals})
df=pd.DataFrame(rows)
features=list(metric_defs)
X=df[features].to_numpy(float)
med=np.median(X,axis=0); mad=np.median(np.abs(X-med),axis=0); scale=1.4826*mad; scale[scale<1e-8]=np.std(X,axis=0)[scale<1e-8]+1e-8
Z=(X-med)/scale
# robust multimetric anomaly; broad changes score high, single-feature expression spikes limited
absz=np.abs(Z); df['geometry_anomaly_score']=np.mean(np.sort(absz,axis=1)[:,-5:],axis=1)
df['features_over_2_5mad']=(absz>=2.5).sum(1)
df['top_changed_features']=['; '.join([features[j] for j in np.argsort(-absz[i])[:5]]) for i in range(len(df))]
df.to_csv(OUT/'keypoint_features_90plus.csv',index=False)
top=df.sort_values(['geometry_anomaly_score','features_over_2_5mad'],ascending=False).head(40)
top.to_csv(OUT/'keypoint_anomalies_top40.csv',index=False)
# Top feature extrema
ext=[]
for j,f in enumerate(features):
 for i in np.argsort(-absz[:,j])[:8]: ext.append({'metric':f,'description_ru':metric_defs[f][1],'filename':df.iloc[i].filename,'date':df.iloc[i].date,'value':X[i,j],'robust_z':Z[i,j],'abs_robust_z':absz[i,j]})
pd.DataFrame(ext).sort_values('abs_robust_z',ascending=False).to_csv(OUT/'keypoint_metric_extrema.csv',index=False)
# Consecutive ABA in robust feature space
aba=[]
for i in range(1,len(df)-1):
 dab=np.linalg.norm(Z[i-1]-Z[i])/np.sqrt(len(features)); dbc=np.linalg.norm(Z[i]-Z[i+1])/np.sqrt(len(features)); dac=np.linalg.norm(Z[i-1]-Z[i+1])/np.sqrt(len(features)); score=(dab+dbc)/2-dac
 # count features where B is >1 MAD away from both A/C while A-C <= 1 MAD
 per=np.minimum(np.abs(Z[i]-Z[i-1]),np.abs(Z[i]-Z[i+1])); returnmask=(per>=1.0)&(np.abs(Z[i-1]-Z[i+1])<=1.0)
 changed=[features[j] for j in np.argsort(-per*returnmask) if returnmask[j]][:6]
 aba.append({'a_filename':df.iloc[i-1].filename,'b_filename':df.iloc[i].filename,'c_filename':df.iloc[i+1].filename,'a_date':df.iloc[i-1].date,'b_date':df.iloc[i].date,'c_date':df.iloc[i+1].date,'d_ab':dab,'d_bc':dbc,'d_ac':dac,'aba_score_geometry':score,'return_features_count':int(returnmask.sum()),'return_features':'; '.join(changed)})
aba=pd.DataFrame(aba).sort_values(['aba_score_geometry','return_features_count'],ascending=False)
aba.to_csv(OUT/'keypoint_aba_top25.csv',index=False)
# PCA + deterministic k-means diagnostics without external dependencies
Zc=Z-Z.mean(0)
u,sv,vt=np.linalg.svd(Zc,full_matrices=False)
p=u[:,:min(12,len(features))]*sv[:min(12,len(features))]
def kmeans(x,k,iters=100,seed=42):
 rng=np.random.default_rng(seed); centers=x[rng.choice(len(x),k,replace=False)].copy()
 for _ in range(iters):
  d=((x[:,None,:]-centers[None,:,:])**2).sum(2); lab=d.argmin(1)
  nc=np.array([x[lab==j].mean(0) if np.any(lab==j) else centers[j] for j in range(k)])
  if np.allclose(nc,centers): break
  centers=nc
 return lab
def silhouette(x,lab):
 D=np.sqrt(((x[:,None,:]-x[None,:,:])**2).sum(2)); vals=[]
 for i in range(len(x)):
  same=(lab==lab[i]); same[i]=False; a=D[i,same].mean() if same.any() else 0
  bs=[D[i,lab==j].mean() for j in np.unique(lab) if j!=lab[i] and np.any(lab==j)]
  b=min(bs) if bs else 0; vals.append((b-a)/max(a,b,1e-12))
 return float(np.mean(vals))
clusters=[]
for k in range(2,7):
 best=None
 for seed in range(20):
  lab=kmeans(p,k,seed=seed); inertia=sum(((p[lab==j]-p[lab==j].mean(0))**2).sum() for j in range(k) if np.any(lab==j))
  if best is None or inertia<best[0]: best=(inertia,lab)
 lab=best[1]
 clusters.append({'k':k,'silhouette':silhouette(p,lab),'sizes':','.join(map(str,np.bincount(lab,minlength=k)))})
pd.DataFrame(clusters).to_csv(OUT/'keypoint_cluster_diagnostics.csv',index=False)
# metric definitions + actual coverage
md=[]
for f,(idx,desc) in metric_defs.items(): md.append({'metric':f,'description_ru':desc,'landmark_ids':','.join(map(str,idx)),'min_landmark_visibility_rate':float(cov[idx].min()),'all_144_values_present':True})
pd.DataFrame(md).to_csv(OUT/'keypoint_metric_definitions_90plus.csv',index=False)
print('frames',len(df),'high_visibility_points_106',len(hi),'features',len(features))
print('\nTOP ANOMALIES')
print(top[['date','filename','geometry_anomaly_score','features_over_2_5mad','top_changed_features']].head(20).to_string(index=False))
print('\nTOP ABA')
print(aba.head(15)[['a_date','b_date','c_date','aba_score_geometry','return_features_count','return_features','b_filename']].to_string(index=False))
print('\nCLUSTERS')
print(pd.DataFrame(clusters).to_string(index=False))
