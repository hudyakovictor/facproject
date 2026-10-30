from pathlib import Path
from itertools import combinations
import numpy as np,pandas as pd,json,hashlib
def euler_xyz(angles):
 x,y,z=np.radians(angles)
 rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
 ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
 rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
 return rz@ry@rx
R=Path('/data');O=R/'output_v7';S=R/'raw/verified396';rng=np.random.default_rng(20261024)
patches=[
('eye_L','Глаз L',list(range(66,74))),('eye_R','Глаз R',list(range(75,83))),
('upper_lid_L','Верхнее веко L',[66,67,68,69,70]),('upper_lid_R','Верхнее веко R',[75,76,77,78,79]),
('lower_lid_L','Нижнее веко L',[66,73,72,71,70]),('lower_lid_R','Нижнее веко R',[75,82,81,80,79]),
('brow_L','Бровь L',list(range(33,42))),('brow_R','Бровь R',list(range(42,51))),
('nasal_ridge','Носовой профиль',[51,52,53,54,60]),('nose_full','Нос целиком',list(range(51,66))),
('nose_base','Основание носа',[54,57,58,59,60,61,62,63]),
('nose_side_L','Боковая часть носа L',[51,55,56,57,58,60]),('nose_side_R','Боковая часть носа R',[51,65,64,63,62,60]),
('upper_lip','Верхняя губа',list(range(84,91))),('lower_lip','Нижняя губа',[84,95,94,93,92,91,90]),
('outer_lips','Наружный контур губ',list(range(84,96))),('inner_lips','Внутренний контур губ',list(range(96,104))),
('jaw_L','Контур челюсти L',[0,4,8,12,16]),('jaw_R','Контур челюсти R',[16,20,24,28,32]),
('chin','Подбородок',[10,13,16,19,22]),('central_midface','Центральная средняя зона',[70,75,51,54,60,87]),
('eye_nose_L','Глаз–нос L',[66,68,70,51,54,57]),('eye_nose_R','Глаз–нос R',[75,77,79,51,54,63]),
('nose_lips','Нос–губы',[57,63,60,84,87,90,93]),('lower_face','Нижняя зона лица',[60,84,90,93,13,16,19])]
families=[
('distance_gini','Неравномерность межточечных расстояний','sum_i( (2*i-m-1)*sort(d)_i ) / (m*sum(d)); i=1..m'),
('distance_iqr','Межквартильный размах расстояний / медиана','(Q75(d)-Q25(d))/Q50(d); quantile=linear'),
('mst_fraction','Длина минимального остова / сумма расстояний','Euclidean_MST_length / sum(all_pair_distances)'),
('triangle_quality_median','Медианная форма треугольников','median_all_triples(4*sqrt(3)*area/(a^2+b^2+c^2))'),
('triangle_area_gini','Неравномерность площадей треугольников','Gini(all_triangle_areas)'),
('tetra_volume_mean','Средний абсолютный объём тетраэдров / диаметр³','mean_all_quadruples(abs(det(b-a,c-a,d-a))/6) / max(pair_distances)^3')]
DIC=[]
for name,label,ids in patches:
 for fam,fl,formula in families:DIC.append(dict(metric=f'v7_{name}_{fam}',label_ru=f'{label}: {fl}',region=name,region_ru=label,family=fam,ids106=','.join(map(str,ids)),n_points=len(ids),formula=formula,unit='dimensionless',rotation_invariant=True))
dic=pd.DataFrame(DIC);cols=dic.metric.tolist();dic.to_csv(O/'dictionary_new150.csv',index=False)
old_dic=pd.read_csv(S/'dictionary_all396.csv');assert len(dic)==150 and not set(cols)&set(old_dic.metric)
# Formula family inspection is manual in the report; new IDs alone do not prove novelty.
def gini(x):
 x=np.sort(x,axis=1);m=x.shape[1];return (x*(2*np.arange(1,m+1)-m-1)).sum(1)/(m*x.sum(1))
def compute(P):
 res=[]
 for _,_,ids in patches:
  q=P[:,ids,:];n=len(ids);ij=np.array(list(combinations(range(n),2)));tri=np.array(list(combinations(range(n),3)));tet=np.array(list(combinations(range(n),4)))
  dv=q[:,ij[:,0]]-q[:,ij[:,1]];dist=np.linalg.norm(dv,axis=2);diam=dist.max(1)
  mat=np.linalg.norm(q[:,:,None,:]-q[:,None,:,:],axis=3)
  used=np.zeros((len(P),n),bool);used[:,0]=True;best=mat[:,0,:].copy();mst=np.zeros(len(P));rr=np.arange(len(P))
  for _ in range(n-1):
   nearest=np.where(used,np.inf,best);k=nearest.argmin(1);mst+=nearest[rr,k];used[rr,k]=True;best=np.minimum(best,mat[rr,k,:])
  a=q[:,tri[:,1]]-q[:,tri[:,0]];b=q[:,tri[:,2]]-q[:,tri[:,0]];area=.5*np.linalg.norm(np.cross(a,b),axis=2)
  denom=(a*a).sum(2)+(b*b).sum(2)+((a-b)**2).sum(2)
  quality=4*np.sqrt(3)*area/denom
  ta=q[:,tet[:,1]]-q[:,tet[:,0]];tb=q[:,tet[:,2]]-q[:,tet[:,0]];tc=q[:,tet[:,3]]-q[:,tet[:,0]]
  vol=abs(np.einsum('bki,bki->bk',ta,np.cross(tb,tc)))/6
  quant=np.quantile(dist,[.25,.5,.75],axis=1)
  res.extend([gini(dist),(quant[2]-quant[0])/quant[1],mst/dist.sum(1),np.median(quality,axis=1),gini(area),vol.mean(1)/diam**3])
 return np.stack(res,axis=1)
def batch(P):return np.concatenate([compute(P[i:i+128]) for i in range(0,len(P),128)])
files=sorted((R/'raw/coordinates106').glob('*.csv'));frames=[];pts=[];visible=[]
for f in files:
 a=pd.read_csv(f).sort_values('landmark_id');assert a.landmark_id.tolist()==list(range(106))
 frames.append(f.stem.removeprefix('ldm106_aligned_'));pts.append(a[['x','y','z']].to_numpy());visible.append(a.visible.to_numpy()==1)
P=np.array(pts);V=np.array(visible);assert P.shape==(144,106,3) and np.isfinite(P).all()
X=batch(P);assert X.shape==(144,150) and np.isfinite(X).all()
meta=pd.DataFrame({'frame':frames,'date':[f[:10].replace('_','-') for f in frames]})
pd.concat([meta,pd.DataFrame(X,columns=cols)],axis=1).to_csv(O/'new150_original144.csv',index=False)
groups=pd.read_csv(S/'all396_groups38.csv')[['frame','date','archive']];ix=np.array([frames.index(f) for f in groups.frame]);G=X[ix];Pg=P[ix];g3=groups.archive.eq(3).to_numpy();g4=~g3
vis=np.column_stack([V[ix][:,ids].all(1) for _,_,ids in patches for _ in families])
pd.concat([groups,pd.DataFrame(G,columns=cols)],axis=1).to_csv(O/'new150_groups38.csv',index=False)
pd.concat([groups,pd.DataFrame(vis,columns=cols)],axis=1).to_csv(O/'fully_visible_flags38.csv',index=False)
# Invariance on every source frame, for isolated small rotations and a similarity transform.
inv=[]
for name,angles,scale,shift in [('yaw_m5',[0,-5,0],1,[0,0,0]),('yaw_p5',[0,5,0],1,[0,0,0]),('pitch_m5',[-5,0,0],1,[0,0,0]),('pitch_p5',[5,0,0],1,[0,0,0]),('roll_m5',[0,0,-5],1,[0,0,0]),('roll_p5',[0,0,5],1,[0,0,0]),('combined3',[3,-3,3],1,[0,0,0]),('similarity',[4,-5,2],1.37,[.4,-.2,.7])]:
 rot=euler_xyz(angles);Y=batch(P@rot.T*scale+shift);diff=abs(Y-X)
 for j,c in enumerate(cols):inv.append(dict(metric=c,test=name,max_abs_error=diff[:,j].max(),max_relative_error=(diff[:,j]/np.maximum(abs(X[:,j]),1e-12)).max()))
pd.DataFrame(inv).to_csv(O/'rotation_similarity_validation.csv',index=False)
print('invariance_done',flush=True)
# Synthetic coordinate perturbations; paired noise applied to all regions, no claim of real estimator error.
# D is distance between means of eye corner endpoints.
D=np.linalg.norm((Pg[:,66]+Pg[:,70])/2-(Pg[:,75]+Pg[:,79])/2,axis=1)
noisestats=[];floor_by_sigma={};noise_sigmas=[.0005,.001,.002];reps=48
for sigma in noise_sigmas:
 noisy=Pg[None,:,:,:]+rng.normal(size=(reps,38,106,3))*(sigma*D)[None,:,None,None]
 Y=batch(noisy.reshape(-1,106,3)).reshape(reps,38,150);delta=Y-G[None,:,:];floors=[]
 for j,c in enumerate(cols):
  # Strict visible controls preferred, or explicit exploratory fallback to all19controls.
  refmask=g4&vis[:,j];fallback=refmask.sum()<8
  if fallback:refmask=g4
  floor=float(np.quantile(abs(delta[:,refmask,j]).ravel(),.95));floors.append(max(floor,1e-12))
  ref=G[refmask,j];mad=1.4826*np.median(abs(ref-np.median(ref)))
  noisestats.append(dict(metric=c,sigma_over_D=sigma,replicates=reps,noise_ref_n=int(refmask.sum()),noise_ref_fallback_all19=fallback,noise_abs_p95=floor,noise_p95_over_ref_MAD=floor/max(mad,1e-12)))
 floor_by_sigma[sigma]=np.array(floors)
 print('noise_done',sigma,flush=True)
pd.DataFrame(noisestats).to_csv(O/'synthetic_coordinate_noise.csv',index=False)
def rsd(x):return 1.4826*np.median(abs(x-np.median(x)))
rows=[];zout=np.full_like(G,np.nan);sensitivity=[];jack=[]
for j,c in enumerate(cols):
 m3=g3&vis[:,j];m4=g4&vis[:,j];n3=m3.sum();n4=m4.sum();floor=floor_by_sigma[.001][j]
 # All-frame exploratory result is separate from main fully-visible result.
 ra=G[g4,j];ca=np.median(ra);sa=max(rsd(ra),floor);za=(G[g3,j]-ca)/sa
 row=dict(metric=c,label_ru=dic.iloc[j].label_ru,region=dic.iloc[j].region,family=dic.iloc[j].family,G3_visible_n=int(n3),G4_visible_n=int(n4),coverage15=bool(n3>=15 and n4>=15),all19_G3_flags=int((abs(za)>3).sum()),synthetic_floor_sigma001=floor)
 if n3>=8 and n4>=8:
  ref=G[m4,j];center=np.median(ref);spread=rsd(ref);scale=max(spread,floor);z=(G[m3,j]-center)/scale;zout[m3,j]=z
  for i in np.where(m4)[0]:
   rr=G[m4&(np.arange(38)!=i),j];zout[i,j]=(G[i,j]-np.median(rr))/max(rsd(rr),floor)
  a=int((abs(z)>3).sum());b=int((abs(zout[m4,j])>3).sum());jk=[]
  for i in np.where(m4)[0]:
   rr=G[m4&(np.arange(38)!=i),j];zz=(G[m3,j]-np.median(rr))/max(rsd(rr),floor);cnt=int((abs(zz)>3).sum());jk.append(cnt);jack.append(dict(metric=c,omitted_frame=groups.frame[i],G3_flags=cnt))
  # Reference bootstrap, counts only: reference-composition sensitivity, not population CI.
  boot=[]
  for _ in range(500):
   rr=rng.choice(ref,len(ref));boot.append(int((abs((G[m3,j]-np.median(rr))/max(rsd(rr),floor))>3).sum()))
  indate=m3&(groups.date<=groups.loc[g4,'date'].max()).to_numpy()
  row.update(G3_flags=a,G4_LOO_flags=b,excess_rate_pp=100*(a/n3-b/n4),ref_median=center,ref_MAD=spread,floor_active=floor>spread,noise_p95_over_ref_MAD=floor/max(spread,1e-12),jackknife_min=min(jk),jackknife_max=max(jk),bootstrap_p05=float(np.quantile(boot,.05)),bootstrap_p95=float(np.quantile(boot,.95)),G3_datewindow_n=int(indate.sum()),G3_datewindow_flags=int((abs((G[indate,j]-center)/scale)>3).sum()))
  for sig in noise_sigmas:
   fl=floor_by_sigma[sig][j];zz=(G[m3,j]-center)/max(spread,fl)
   for t in [2.5,3,3.5]:sensitivity.append(dict(metric=c,sigma=sig,threshold=t,G3_n=int(n3),G3_flags=int((abs(zz)>t).sum())))
 rows.append(row)
rank=pd.DataFrame(rows);rank['screen_stable']=rank.coverage15&(rank.noise_p95_over_ref_MAD<=.5)
rank['tier']=np.where(rank.screen_stable,'A_visible_noise_low',np.where(rank.coverage15,'B_visible_noise_higher','C_exploratory_coverage'))
rank=rank.sort_values(['screen_stable','coverage15','excess_rate_pp','G3_flags'],ascending=[False,False,False,False],na_position='last');rank.insert(0,'rank',range(1,151));rank.to_csv(O/'ranking_new150.csv',index=False)
rank[rank.screen_stable].head(10).to_csv(O/'TOP10_strict.csv',index=False)
rank.sort_values(['all19_G3_flags','metric'],ascending=[False,True]).head(10).to_csv(O/'TOP10_exploratory_all19.csv',index=False)
pd.DataFrame(sensitivity).to_csv(O/'threshold_noise_sensitivity.csv',index=False);pd.DataFrame(jack).to_csv(O/'reference_jackknife.csv',index=False)
pd.concat([groups,pd.DataFrame(zout,columns=cols)],axis=1).to_csv(O/'visible_scores38.csv',index=False)
# Check exact numerical repeats/affine repeats against old396 and among new150, with normalized residual.
old=pd.read_csv(S/'all396_original144.csv').set_index('frame').loc[frames,old_dic.metric].to_numpy()
Z=np.concatenate([old,X],axis=1);names=old_dic.metric.tolist()+cols
means=Z.mean(0);sd=Z.std(0);Zs=(Z-means)/np.maximum(sd,1e-15);corr=Zs.T@Zs/len(Zs)
pairs=[]
for j in range(396,546):
 for k in range(j):
  r=corr[j,k]
  if abs(r)>.98:
   residual=np.sqrt(max(0,1-min(1,r*r)));pairs.append(dict(new_metric=names[j],other_metric=names[k],other_is_previous396=k<396,pearson_r=r,standardized_affine_residual_rms=residual,near_exact_affine=bool(residual<1e-6)))
pd.DataFrame(pairs).to_csv(O/'correlated_or_duplicate_pairs.csv',index=False)
assert max(i['max_abs_error'] for i in inv)<1e-10
exact=[p for p in pairs if p['near_exact_affine']]
# Direct independent recomputation of all150 from one source using scalar formulas and scipy MST.
def kruskal(mat):
 n=len(mat);parent=list(range(n));total=0
 def root(i):
  while parent[i]!=i:i=parent[i]
  return i
 for w,i,j in sorted((mat[i,j],i,j) for i in range(n) for j in range(i+1,n)):
  a,b=root(i),root(j)
  if a!=b:parent[a]=b;total+=w
 return total
ind=[];pp=P[0]
for _,_,ids in patches:
 q=pp[ids];dd=np.array([np.linalg.norm(a-b) for a,b in combinations(q,2)])
 ar=[];qual=[]
 for a,b,c in combinations(q,3):
  A=np.linalg.norm(np.cross(b-a,c-a))/2;ar.append(A);qual.append(4*np.sqrt(3)*A/(sum((a-b)**2)+sum((b-c)**2)+sum((c-a)**2)))
 def slow_gini(a):return np.abs(np.array(a)[:,None]-np.array(a)[None,:]).sum()/(2*len(a)*sum(a))
 mat=np.linalg.norm(q[:,None]-q[None,:],axis=2)
 vol=[abs(np.linalg.det(np.stack([b-a,c-a,d-a])))/6 for a,b,c,d in combinations(q,4)]
 ind.extend([slow_gini(dd),np.subtract(*np.quantile(dd,[.75,.25]))/np.median(dd),kruskal(mat)/sum(dd),np.median(qual),slow_gini(ar),np.mean(vol)/max(dd)**3])
inderr=float(np.max(abs(np.array(ind)-X[0])));assert inderr<1e-12
summary=dict(new_metrics=150,previous_metrics=396,total_after=546,source_frames=144,group3_measured=19,group3_total=50,group4_measured=19,missing_group3=31,patches=25,families=6,strict_coverage_count=int(rank.coverage15.sum()),strict_low_noise_count=int(rank.screen_stable.sum()),synthetic_replicates_per_sigma=reps,noise_sigmas=noise_sigmas,max_invariance_abs_error=max(i['max_abs_error'] for i in inv),independent_scalar_max_error=inderr,near_exact_affine_pairs=exact,high_correlation_pairs=len(pairs),selection='25 anatomically defined patches x6 new intrinsic formula families, fixed before group contrasts; not a globally optimal search',strict_rule='all defining points visible>=15/19 in each group, synthetic p95 error<=0.5 reference MAD at sigma=.001D',data_limits='pose invariance of fixed3D coordinates is not pose robustness of re-estimated3DDFA landmarks')
(O/'evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False),flush=True)
