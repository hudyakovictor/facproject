from pathlib import Path
from itertools import combinations
import ast,sys,zipfile,json,hashlib
import numpy as np,pandas as pd
R=Path('/data');O=R/'output_v8';S=R/'raw/verified396';rng=np.random.default_rng(20261025)
# Load only reviewed pure definitions/constants; do not execute old pipelines.
def definitions(path,constants):
 tree=ast.parse(Path(path).read_text());nodes=[]
 for n in tree.body:
  if isinstance(n,ast.FunctionDef):nodes.append(n)
  elif isinstance(n,ast.Assign) and all(isinstance(t,ast.Name) and t.id in constants for t in n.targets):nodes.append(n)
 ns={'np':np,'pd':pd,'combinations':combinations};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),ns);return ns
helpers=definitions(R/'raw/previous_scripts/audit_helpers.py',set())
f100=definitions(R/'raw/previous_scripts/dependencies/metric_functions100.py',{'DICT','baseids','axisids'})
v4=definitions(R/'raw/previous_scripts/dependencies/additional100.py',{'REGIONS','DESCRIPTORS','AREA_PAIRS'})
v5=definitions(R/'raw/previous_scripts/metrics150.py',{'BASE','ANCHORS','CHAINS','DESCRIPTORS','QUADS','TETRA','PAIRS'})
v7=definitions(R/'analysis/v7/new150.py',{'patches','families'})
dold=pd.read_csv(S/'dictionary_all396.csv').fillna('');dn=pd.read_csv(R/'output_v7/dictionary_new150.csv').fillna('');dn['stage']='additional150_intrinsic';dic=pd.concat([dold,dn],ignore_index=True).fillna('');cols=dic.metric.tolist();assert len(cols)==546 and len(set(cols))==546
c46=dold.metric.iloc[:46].tolist()
def oldcalc(p,q):
 a=helpers['original46'](p,q);return np.r_[[a[c] for c in c46],f100['compute'](p)[0],v4['compute'](p),v5['compute'](p)]
# Dense134 coordinates from the original archive; ignore macOS resource forks.
z=zipfile.ZipFile(R/'.agent-service/files/04965019-8f8f-4f37-9bb1-bb2d1361a9ca/Архив 2.zip');dense={Path(n).stem.removeprefix('ldm134_aligned_'):n for n in z.namelist() if Path(n).name.startswith('ldm134_aligned_') and n.endswith('.csv') and '__MACOSX' not in n}
frames=[];pp=[];qq=[];vis106=[];vis134=[];vertexp=[];vertexq=[]
for f in sorted((R/'raw/coordinates106').glob('*.csv')):
 frame=f.stem.removeprefix('ldm106_aligned_');a=pd.read_csv(f).sort_values('landmark_id');b=pd.read_csv(z.open(dense[frame])).sort_values('landmark_id')
 assert a.landmark_id.tolist()==list(range(106)) and b.landmark_id.tolist()==list(range(134))
 frames.append(frame);pp.append(a[['x','y','z']].to_numpy());qq.append(b[['x','y','z']].to_numpy());vis106.append(a.visible.to_numpy()==1);vis134.append(b.visible.to_numpy()==1);vertexp.append(a.vertex_index.to_numpy());vertexq.append(b.vertex_index.to_numpy())
P=np.array(pp);Q=np.array(qq);V=np.array(vis106);W=np.array(vis134);assert len(frames)==144
Xold=np.array([oldcalc(p,q) for p,q in zip(P,Q)]);Xnew=v7['batch'](P);X=np.c_[Xold,Xnew];assert X.shape==(144,546) and np.isfinite(X).all()
savedold=pd.read_csv(S/'all396_original144.csv').set_index('frame').loc[frames,dold.metric].to_numpy();savednew=pd.read_csv(R/'output_v7/new150_original144.csv').set_index('frame').loc[frames,dn.metric].to_numpy()
err_old=float(abs(Xold-savedold).max());err_new=float(abs(Xnew-savednew).max());assert max(err_old,err_new)<1e-10
meta=pd.DataFrame({'frame':frames,'date':[f[:10].replace('_','-') for f in frames]});assert meta.frame.is_unique;meta['date']=pd.to_datetime(meta.date)
labels=pd.read_csv(S/'all396_groups38.csv')[['frame','archive']];meta=meta.merge(labels,on='frame',how='left',validate='one_to_one');meta['set_role']=np.where(meta.archive.eq(3),'archive3',np.where(meta.archive.eq(4),'archive4_reference','unlabelled_original'));gi=np.where(meta.archive.notna())[0];gg=meta.iloc[gi].reset_index(drop=True);G=X[gi];g3=gg.archive.eq(3).to_numpy();g4=~g3;assert g3.sum()==g4.sum()==19 and gg.date.nunique()==38
# Visibility uses every defining vertex, including all normalising/axis anchors declared in audited dictionary.
visible=[];coverage=[]
for _,r in dic.iterrows():
 ids=lambda s:sorted(set(int(v) for v in str(s).split(',') if v.strip()))
 a=ids(r.ids106);b=ids(r.get('ids134',''));vv=np.c_[V[:,a],W[:,b]];assert vv.shape[1]>0
 visible.append(vv.all(1));coverage.append(vv.mean(1))
VIS=np.array(visible).T;COVER=np.array(coverage).T
oldv=pd.read_csv(S/'visibility_all396_groups38.csv').set_index('frame').loc[gg.frame,dold.metric].to_numpy();assert np.array_equal(VIS[gi,:396],oldv==1)
print('fresh546_done',err_old,err_new,flush=True)
# Common synthetic guard, sigma=.001D, 32 replicates of all19 control frames.
# Shared mesh vertex indices receive exactly the same perturbation in106/134 exports.
refidx=gi[g4];noise=[];D=np.linalg.norm((P[:,66]+P[:,70]-P[:,75]-P[:,79])/2,axis=1)
assert all(np.array_equal(vertexp[0],v) for v in vertexp) and all(np.array_equal(vertexq[0],v) for v in vertexq)
unique=np.unique(np.r_[vertexp[0],vertexq[0]]);ip=np.searchsorted(unique,vertexp[0]);iq=np.searchsorted(unique,vertexq[0])
for rep in range(32):
 delta=rng.normal(size=(19,len(unique),3))*(.001*D[refidx])[:,None,None];pn=P[refidx]+delta[:,ip];qn=Q[refidx]+delta[:,iq]
 Yold=np.array([oldcalc(p,q) for p,q in zip(pn,qn)]);Ynew=v7['batch'](pn);noise.append(abs(np.c_[Yold,Ynew]-X[refidx]))
noise=np.array(noise);floor=np.quantile(noise.reshape(-1,546),.95,axis=0);floor=np.maximum(floor,1e-12)
pd.DataFrame({'metric':cols,'sigma_over_D':.001,'reference_frames':19,'replicates':32,'absolute_error_p95':floor}).to_csv(O/'common_noise_floor546.csv',index=False)
print('noise_done',flush=True)
def rsd(a):return 1.4826*np.median(abs(a-np.median(a,axis=0)),axis=0)
# Preregistered repeated3-fold comparison: fit reference center on training G4 ONLY.
# Heldout G3 and G4 are compared within the same fold, eliminating scale differences.
repeats=50;auc=np.zeros((repeats,546));oof=np.zeros((38,546));splitrows=[]
for rep in range(repeats):
 folds3=np.array_split(rng.permutation(np.where(g3)[0]),3);folds4=np.array_split(rng.permutation(np.where(g4)[0]),3);wins=np.zeros(546);pairs=0
 for fold,(test3,test4) in enumerate(zip(folds3,folds4)):
  train4=np.setdiff1d(np.where(g4)[0],test4);center=np.median(G[train4],axis=0);a=abs(G[test3]-center);b=abs(G[test4]-center)
  diff=a[:,None,:]-b[None,:,:];wins+=(diff>0).sum((0,1))+.5*(diff==0).sum((0,1));pairs+=len(test3)*len(test4)
  scale=np.maximum(rsd(G[train4]),1e-12);ti=np.r_[test3,test4];oof[ti]+=abs(G[ti]-center)/scale
  for i in ti:splitrows.append(dict(repeat=rep,fold=fold,frame=gg.frame[i],archive=int(gg.archive[i]),training_reference_n=len(train4)))
 auc[rep]=wins/pairs
oof/=repeats
# Primary fit for applying the same546 reference definitions to ALL144 frames. Refit G4 center/scale without self for control rows.
center=np.median(X[refidx],axis=0);spread=rsd(X[refidx]);scale=np.maximum(spread,floor);Z=(X-center)/scale
for i in refidx:
 rr=X[np.setdiff1d(refidx,[i])];Z[i]=(X[i]-np.median(rr,axis=0))/np.maximum(rsd(rr),floor)
flags=abs(Z)>3;fv=flags&VIS
# Unified comparison all19, plus fully-visible sensitivity where>=8 each.
rows=[];visible_auc=[]
for j,c in enumerate(cols):
 n3=int(VIS[gi[g3],j].sum());n4=int(VIS[gi[g4],j].sum());a=int(flags[gi[g3],j].sum());b=int(flags[gi[g4],j].sum());k3=int(fv[gi[g3],j].sum());k4=int(fv[gi[g4],j].sum())
 row=dict(metric=c,label_ru=dic.iloc[j].label_ru,stage=dic.iloc[j].stage,family=dic.iloc[j].family,CV_AUC_mean=auc[:,j].mean(),CV_AUC_split_sd=auc[:,j].std(),CV_AUC_split_p05=np.quantile(auc[:,j],.05),CV_AUC_split_p95=np.quantile(auc[:,j],.95),G3_flags_all19=a,G4_LOO_flags_all19=b,balanced_accuracy_at3=(a/19+1-b/19)/2,excess_flag_rate_pp=100*(a-b)/19,G3_fully_visible=n3,G4_fully_visible=n4,full144_fully_visible=int(VIS[:,j].sum()),full144_flags=int(flags[:,j].sum()),full144_flags_fully_visible=int(fv[:,j].sum()),unlabelled106_flags=int(flags[meta.set_role.eq('unlabelled_original').to_numpy(),j].sum()),ref_median=center[j],ref_MAD=spread[j],common_synthetic_floor=floor[j],floor_active=bool(floor[j]>spread[j]),noise95_over_ref_MAD=floor[j]/max(spread[j],1e-12),strict_coverage=bool(n3>=15 and n4>=15),signal_over_chance=bool(auc[:,j].mean()>.5),positive_threshold_contrast=bool(a>b))
 m3=g3&VIS[gi,j];m4=g4&VIS[gi,j]
 if min(n3,n4)>=8:
  rr=G[m4,j];med=np.median(rr);sc=max(float(rsd(rr)),floor[j]);c3=int((abs((G[m3,j]-med)/sc)>3).sum());c4=0
  for i in np.where(m4)[0]:
   tt=G[m4&(np.arange(38)!=i),j];c4+=abs((G[i,j]-np.median(tt))/max(float(rsd(tt)),floor[j]))>3
  # Visible-only holdout cross-validation; subsets/splits are fixed separately for each metric.
  vrng=np.random.default_rng(20262025);va=[]
  for rep in range(30):
   f3=np.array_split(vrng.permutation(np.where(m3)[0]),3);f4=np.array_split(vrng.permutation(np.where(m4)[0]),3);w=0;den=0
   for t3,t4 in zip(f3,f4):
    train=np.setdiff1d(np.where(m4)[0],t4);md=np.median(G[train,j]);diff=abs(G[t3,j]-md)[:,None]-abs(G[t4,j]-md)[None,:];w+=(diff>0).sum()+.5*(diff==0).sum();den+=diff.size
   va.append(w/den)
  row.update(visible_CV_AUC_mean=np.mean(va),visible_G3_flags=c3,visible_G4_LOO_flags=int(c4),visible_excess_rate_pp=100*(c3/n3-c4/n4))
 rows.append(row)
rank=pd.DataFrame(rows).sort_values(['CV_AUC_mean','CV_AUC_split_sd','metric'],ascending=[False,True,True]).reset_index(drop=True);rank.insert(0,'rank_all546',range(1,547))
rank['visibility_tier']=np.where(rank.strict_coverage,'A_15plus_each',np.where((rank.G3_fully_visible>=8)&(rank.G4_fully_visible>=8),'B_8plus_each','C_low_visibility'))
rank['noise_screen']=rank.noise95_over_ref_MAD<=.5
# Auxiliary reliability-aware order retains ALL546, does not replace primary empirical contrast order.
aux=rank.assign(tier_order=rank.visibility_tier.str[0]).sort_values(['tier_order','noise_screen','CV_AUC_mean','CV_AUC_split_sd','metric'],ascending=[True,False,False,True,True]);aux['rank_reliability_first']=range(1,547);rank=rank.merge(aux[['metric','rank_reliability_first']],on='metric',validate='one_to_one')
# Duplicate/correlation audit; keep all rows and clearly mark related descriptors.
sd=X.std(0);std=(X-X.mean(0))/np.maximum(sd,1e-15);corr=std.T@std/len(X);near=[];dups=[]
for j in range(546):
 for k in range(j):
  r=float(np.clip(corr[j,k],-1,1))
  if abs(r)>.98:
   residual=float(np.sqrt(max(0,1-r*r)));row=dict(metric_a=cols[k],metric_b=cols[j],pearson_r=r,standardized_affine_residual=residual,near_exact_affine=residual<1e-6);near.append(row)
   if residual<1e-6:dups.append(row)
for p in near:
 p['rank_a']=int(rank.set_index('metric').loc[p['metric_a'],'rank_all546']);p['rank_b']=int(rank.set_index('metric').loc[p['metric_b'],'rank_all546'])
partners={c:[] for c in cols}
for p in dups:partners[p['metric_a']].append(p['metric_b']);partners[p['metric_b']].append(p['metric_a'])
rank['near_exact_affine_partners']=rank.metric.map(lambda c:';'.join(partners[c]));rank.to_csv(O/'RANK_ALL546.csv',index=False)
rank.sort_values('rank_reliability_first').to_csv(O/'RANK_ALL546_reliability_first.csv',index=False)
full_dictionary=dic.merge(rank[['metric','rank_all546','rank_reliability_first']],on='metric').sort_values('rank_all546');full_dictionary.to_csv(O/'DICTIONARY_ALL546.csv',index=False)
ordered=rank.metric.tolist();indices=[cols.index(c) for c in ordered]
for name,data in [('FULL144_values546',X[:,indices]),('FULL144_signed_scores546',Z[:,indices]),('FULL144_flags546',flags[:,indices].astype(int)),('FULL144_all_points_visible546',VIS[:,indices].astype(int)),('FULL144_defining_visible_fraction546',COVER[:,indices])]:pd.concat([meta,pd.DataFrame(data,columns=ordered)],axis=1).to_csv(O/(name+'.csv'),index=False)
pd.concat([gg,pd.DataFrame(oof[:,indices],columns=ordered)],axis=1).to_csv(O/'CV38_out_of_fold_abs_scores546.csv',index=False)
pd.DataFrame(splitrows).to_csv(O/'CV_split_assignments.csv',index=False)
pd.DataFrame(auc,columns=cols).to_csv(O/'CV50_repeat_AUC546.csv',index=False);pd.DataFrame(near).to_csv(O/'correlations_and_duplicates546.csv',index=False)
# Chronology is frame order, not equal elapsed time; same dates may have alternative frames.
sortidx=meta.sort_values(['date','frame']).index.to_numpy();dstep=abs(np.diff(X[sortidx],axis=0))/scale
steps=pd.DataFrame({'previous_frame':meta.frame.iloc[sortidx[:-1]].to_numpy(),'frame':meta.frame.iloc[sortidx[1:]].to_numpy(),'date':meta.date.iloc[sortidx[1:]].to_numpy(),'elapsed_days':np.diff(meta.date.iloc[sortidx].to_numpy()).astype('timedelta64[D]').astype(int)})
pd.concat([steps,pd.DataFrame(dstep[:,indices],columns=ordered)],axis=1).to_csv(O/'CHRONOLOGY143_adjacent_changes546.csv',index=False)
frame_summary=meta.copy();frame_summary['available_visible_metrics']=VIS.sum(1);frame_summary['flags_all546']=flags.sum(1);frame_summary['flags_fully_visible']=fv.sum(1);frame_summary['visible_flag_fraction']=fv.sum(1)/np.maximum(VIS.sum(1),1);frame_summary['max_abs_score']=abs(Z).max(1);frame_summary.to_csv(O/'FRAME_SUMMARY144.csv',index=False)
# Absolute flags long-form, retaining visibility and reference membership.
rr,cc=np.where(flags);long=pd.DataFrame({'frame':meta.frame.to_numpy()[rr],'date':meta.date.to_numpy()[rr],'set_role':meta.set_role.to_numpy()[rr],'metric':np.array(cols)[cc],'signed_score':Z[rr,cc],'all_points_visible':VIS[rr,cc]});long=long.merge(rank[['metric','rank_all546']],on='metric');long.sort_values(['date','frame','rank_all546']).to_csv(O/'FLAGGED_INSTANCES144.csv',index=False)
e=dict(metrics=546,frames=144,source106=144,source134=144,group3=19,group4=19,unlabelled=106,missing_archive3=31,first_date=str(meta.date.min().date()),last_date=str(meta.date.max().date()),fresh_recompute_old_max_error=err_old,fresh_recompute_new_max_error=err_new,cv_repeats=50,cv_folds=3,cv_metric_evaluations=546*150,noise_replicates=32,noise_reference_frames=19,noise_sigma_over_D=.001,strict_coverage_metrics=int(rank.strict_coverage.sum()),strict_coverage_and_noise=int((rank.strict_coverage&rank.noise_screen).sum()),positive_CV_AUC_metrics=int(rank.signal_over_chance.sum()),positive_threshold_contrast_metrics=int(rank.positive_threshold_contrast.sum()),near_exact_affine_pairs=dups,high_correlation_pairs=len(near),all546_retained=True,ranking_rule='descending mean heldout within-fold AUC of absolute distance from TRAINING reference median;ties lower splitSD then metric code',rank_not_blind_validation=True)
(O/'EVIDENCE.json').write_text(json.dumps(e,ensure_ascii=False,indent=2));print(json.dumps(e,ensure_ascii=False),flush=True)
