from pathlib import Path
import json, hashlib, zipfile
import numpy as np
import pandas as pd

ROOT=Path('/data')
OUT=ROOT/'output_v4'
OUT.mkdir(exist_ok=True)
SEED=20261021
rng=np.random.default_rng(SEED)

# Closed, ordered 106-point proxy polygons, not dense mesh/UV surface masks.
# The path split is explicit and reproducible, not an assumed anatomical half.
REGIONS={
 'eye_L':('Глаз L',list(range(66,74)),4),
 'eye_R':('Глаз R',list(range(75,83)),4),
 'brow_L':('Бровь L',list(range(33,42)),4),
 'brow_R':('Бровь R',list(range(42,51)),4),
 'nose':('Нос',[51,55,56,57,58,59,60,61,62,63,64,65],6),
 'nose_base':('Основание носа',[57,58,59,60,61,62,63,54],3),
 'mouth_outer':('Наружный контур губ',list(range(84,96)),6),
 'mouth_inner':('Внутренний контур губ',list(range(96,104)),4),
 'cheek_L':('Щёчно-челюстной патч L',[0,66,55,57,84,8,4],4),
 'cheek_R':('Щёчно-челюстной патч R',[32,79,65,63,90,24,28],4),
}
DESCRIPTORS=[
 ('fan_compactness','Компактность веерной площади','4*pi*A_fan/perimeter^2'),
 ('vector_fan','Векторная / веерная площадь','A_vector/A_fan'),
 ('radius_cv','Неравномерность радиусов','SD_population(distance(vertices,centroid))/mean(radius)'),
 ('edge_cv','Неравномерность рёбер','SD_population(edge_lengths)/mean(edge_lengths)'),
 ('pca_flat','Отношение главных размеров','sqrt(lambda2/lambda1)'),
 ('pca_depth','Относительная внеплоскостность','sqrt(lambda3/lambda1)'),
 ('first_path_area','Доля площади первого пути','sum(fan_triangle_areas[:split])/A_fan'),
 ('first_path_arc','Доля длины первого пути','sum(edge_lengths[:split])/perimeter'),
]
AREA_PAIRS=[
 ('eye_L_to_R',['eye_L'],['eye_R'],'Глаза L / R'),
 ('brow_L_to_R',['brow_L'],['brow_R'],'Брови L / R'),
 ('cheek_L_to_R',['cheek_L'],['cheek_R'],'Щёки L / R'),
 ('inner_to_outer_mouth',['mouth_inner'],['mouth_outer'],'Внутренний / наружный контур губ'),
 ('base_to_nose',['nose_base'],['nose'],'Основание / весь нос'),
 ('eye_brow_L',['eye_L'],['brow_L'],'Глаз / бровь L'),
 ('eye_brow_R',['eye_R'],['brow_R'],'Глаз / бровь R'),
 ('eye_cheek_L',['eye_L'],['cheek_L'],'Глаз / щека L'),
 ('eye_cheek_R',['eye_R'],['cheek_R'],'Глаз / щека R'),
 ('brow_cheek_L',['brow_L'],['cheek_L'],'Бровь / щека L'),
 ('brow_cheek_R',['brow_R'],['cheek_R'],'Бровь / щека R'),
 ('nose_mouth',['nose'],['mouth_outer'],'Нос / наружный контур губ'),
 ('base_inner_mouth',['nose_base'],['mouth_inner'],'Основание носа / внутренний контур губ'),
 ('eyes_brows',['eye_L','eye_R'],['brow_L','brow_R'],'Оба глаза / обе брови'),
 ('eyes_cheeks',['eye_L','eye_R'],['cheek_L','cheek_R'],'Оба глаза / обе щеки'),
 ('brows_cheeks',['brow_L','brow_R'],['cheek_L','cheek_R'],'Обе брови / обе щеки'),
 ('mouth_cheeks',['mouth_outer'],['cheek_L','cheek_R'],'Наружный контур губ / обе щеки'),
 ('nose_cheeks',['nose'],['cheek_L','cheek_R'],'Нос / обе щеки'),
 ('eyes_nose',['eye_L','eye_R'],['nose'],'Оба глаза / нос'),
 ('inner_mouth_eyes',['mouth_inner'],['eye_L','eye_R'],'Внутренний контур губ / оба глаза'),
]

def geometry(Q,split):
    C=Q-Q.mean(0)
    nxt=np.roll(C,-1,axis=0)
    crosses=np.cross(C,nxt)/2
    triangles=np.linalg.norm(crosses,axis=1)
    area=triangles.sum()
    vector=np.linalg.norm(crosses.sum(0))
    edges=np.linalg.norm(nxt-C,axis=1)
    rad=np.linalg.norm(C,axis=1)
    eig=np.linalg.eigvalsh(C.T@C/len(C))[::-1]
    assert area>1e-12 and edges.min()>1e-12 and eig[0]>1e-12
    vals=[4*np.pi*area/edges.sum()**2,vector/area,
          rad.std()/rad.mean(),edges.std()/edges.mean(),
          np.sqrt(max(eig[1],0)/eig[0]),np.sqrt(max(eig[2],0)/eig[0]),
          triangles[:split].sum()/area,edges[:split].sum()/edges.sum()]
    return np.array(vals),area

def compute(P):
    vals=[];areas={}
    for code,(_,ids,split) in REGIONS.items():
        v,a=geometry(P[ids],split);vals.extend(v);areas[code]=a
    for code,nums,dens,label in AREA_PAIRS:
        vals.append(sum(areas[x] for x in nums)/sum(areas[x] for x in dens))
    assert len(vals)==100 and np.isfinite(vals).all()
    return np.array(vals)

def dictionary():
    rows=[]
    for region,(label,ids,split) in REGIONS.items():
        for code,desc,formula in DESCRIPTORS:
            rows.append(dict(metric='v4_'+region+'_'+code,label_ru=label+' — '+desc,
                             family=code,region=region,formula=formula,ids106=','.join(map(str,ids)),
                             split_after_edges=split,unit='ratio',
                             definition_kind='ordered_106_proxy_polygon'))
    for code,nums,dens,label in AREA_PAIRS:
        ids=sorted(set(i for r in nums+dens for i in REGIONS[r][1]))
        rows.append(dict(metric='v4_area_'+code,label_ru='Площади: '+label,
                         family='area_ratios',region='cross_region',
                         formula='('+'+'.join('A_fan('+r+')' for r in nums)+')/('+
                         '+'.join('A_fan('+r+')' for r in dens)+')',
                         ids106=','.join(map(str,ids)),split_after_edges=None,
                         unit='ratio',definition_kind='ratio_of_fan_proxy_areas'))
    return pd.DataFrame(rows)

def robust_sd(x):
    return 1.4826*np.median(abs(x-np.median(x,axis=0)),axis=0)

def mdtable(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |',
                     '| '+' | '.join(['---']*len(headers))+' |']+
                    ['| '+' | '.join(str(x).replace('|','/') for x in row)+' |' for row in rows])

def main():
    dic=dictionary();cols=dic.metric.tolist()
    dic.to_csv(OUT/'additional100_dictionary.csv',index=False)
    pd.DataFrame([dict(region=c,label_ru=l,ordered_ids=','.join(map(str,ids)),
                       first_path_edges=split,second_path_edges=len(ids)-split)
                  for c,(l,ids,split) in REGIONS.items()]).to_csv(OUT/'regions10.csv',index=False)
    meta=[];Ps=[];Vs=[];X=[]
    for p in sorted((ROOT/'raw/1').glob('ldm106_aligned_*.csv')):
        a=pd.read_csv(p).sort_values('landmark_id')
        assert a.landmark_id.tolist()==list(range(106))
        P=a[['x','y','z']].to_numpy(float)
        assert P.shape==(106,3) and np.isfinite(P).all()
        frame=p.stem.removeprefix('ldm106_aligned_')
        meta.append(dict(frame=frame,date=pd.Timestamp(frame[:10].replace('_','-'))))
        Ps.append(P);Vs.append(a.visible.to_numpy());X.append(compute(P))
    M=pd.DataFrame(meta);P=np.array(Ps);V=np.array(Vs);X=np.array(X)
    assert X.shape==(144,100)
    allvalues=pd.concat([M,pd.DataFrame(X,columns=cols)],axis=1)
    allvalues.to_csv(OUT/'additional100_all144.csv',index=False)
    manifest=pd.read_csv(ROOT/'output_v3/all69_coverage_manifest.csv')
    group=manifest[['frame','date','archive','coordinates_available']].copy()
    group['date']=pd.to_datetime(group.date)
    matched=group.merge(allvalues,on=['frame','date'],how='left',validate='one_to_one')
    matched.to_csv(OUT/'additional100_all69_missing_explicit.csv',index=False)
    G=matched[matched.coordinates_available].copy().reset_index(drop=True)
    assert len(G)==38 and G[cols].notna().all().all()
    G.to_csv(OUT/'additional100_groups38.csv',index=False)
    lookup={f:i for i,f in enumerate(M.frame)}
    ix=np.array([lookup[f] for f in G.frame]);Y=G[cols].to_numpy()
    gp=P[ix];gv=V[ix];g3=G.archive.eq(3).to_numpy();g4=~g3
    assert g3.sum()==19 and g4.sum()==19
    coverage=np.empty_like(Y)
    for j,r in dic.iterrows():
        ids=list(map(int,r.ids106.split(',')));coverage[:,j]=gv[:,ids].mean(1)
    pd.concat([G[['frame','date','archive']],pd.DataFrame(coverage,columns=cols)],axis=1).to_csv(
        OUT/'defining_visibility38.csv',index=False)
    # Independent proper-similarity invariance check, for every descriptor.
    R,_=np.linalg.qr(rng.normal(size=(3,3)))
    if np.linalg.det(R)<0:R[:,0]*=-1
    invariant=np.max(abs(compute(3.7*gp[0]@R+np.array([11.,-4.,8.]))-Y[0]))
    assert invariant<1e-10
    # Raw export is a similarity counterpart, not an independent observation.
    raw_errors=[]
    for i in range(len(G)):
        raw=pd.read_csv(ROOT/'raw/1'/('ldm106_raw_'+G.frame[i]+'.csv')).sort_values('landmark_id')
        raw_errors.append(np.max(abs(compute(raw[['x','y','z']].to_numpy())-Y[i])))
    assert max(raw_errors)<1e-4
    # Numerical uniqueness against previous descriptors and supplied feature columns.
    previous=pd.read_csv(ROOT/'output_v2/all146_by_frame.csv')
    previous_metric_ids=(pd.read_csv(ROOT/'output/metric_dictionary.csv').metric.tolist()+
                         pd.read_csv(ROOT/'output_v3/metric_dictionary100.csv').metric.tolist())
    previous=previous[['frame','date']+previous_metric_ids]
    prevcols=[c for c in previous if c not in ['frame','date']]
    prevnum=previous.select_dtypes('number').columns.tolist()
    old=previous[['frame']+prevnum].merge(allvalues,on='frame',validate='one_to_one')
    priorX=old[prevnum].to_numpy()
    newX=old[cols].to_numpy()
    duplicates=[]
    for j,c in enumerate(cols):
        for k,oldc in enumerate(prevnum):
            if np.allclose(newX[:,j],priorX[:,k],rtol=1e-8,atol=1e-10):
                duplicates.append((c,oldc))
    assert not duplicates
    supplied=pd.read_csv(ROOT/'raw/region_descriptions/keypoint_features_90plus.csv')
    suppliedcols=[c for c in supplied.select_dtypes('number') if
                  c not in ['geometry_anomaly_score','features_over_2_5mad']]
    supplied_join=supplied.rename(columns={'stem':'frame'}).merge(allvalues,on='frame')
    for c in cols:
        for oldc in suppliedcols:
            assert not np.allclose(supplied_join[c],supplied_join[oldc],rtol=1e-8,atol=1e-10)
    assert len(supplied_join)==144 and len(suppliedcols)==17
    # Consistent operational reference contract, not a calibrated measurement error.
    errors=[]
    for i in np.where(g4)[0]:
        D=np.linalg.norm((gp[i,75]+gp[i,79]-gp[i,66]-gp[i,70])/2)
        reps=[compute(gp[i]+rng.normal(0,.001*D,gp[i].shape))-Y[i] for _ in range(60)]
        errors.append(np.std(reps,axis=0,ddof=1))
    floor=np.median(errors,axis=0)
    center=np.median(Y[g4],axis=0);spread=robust_sd(Y[g4])
    scale=np.maximum(spread,floor)
    assert (scale>0).all()
    Z=(Y-center)/scale
    for i in np.where(g4)[0]:
        ref=Y[g4 & (np.arange(len(G))!=i)]
        Z[i]=(Y[i]-np.median(ref,axis=0))/np.maximum(robust_sd(ref),floor)
    pd.concat([G[['frame','date','archive']],pd.DataFrame(Z,columns=cols)],axis=1).to_csv(
        OUT/'additional100_scores38_G4_LOO.csv',index=False)
    stats=[];ranking=[]
    for j,c in enumerate(cols):
        row=dict(metric=c,label_ru=dic.iloc[j].label_ru,region=dic.iloc[j].region,
                 family=dic.iloc[j].family,ref_median=center[j],ref_MAD_sd=spread[j],
                 synthetic_floor=floor[j],floor_active=bool(floor[j]>spread[j]),
                 G3_mean=Y[g3,j].mean(),G4_mean=Y[g4,j].mean(),
                 G3_median=np.median(Y[g3,j]),G4_median=np.median(Y[g4,j]),
                 G3_fully_visible=int((coverage[g3,j]==1).sum()),
                 G4_fully_visible=int((coverage[g4,j]==1).sum()),
                 G3_median_abs_score=np.median(abs(Z[g3,j])))
        for t,tag in [(2.5,'2p5'),(3,'3'),(3.5,'3p5')]:
            row['G3_count_'+tag]=int((abs(Z[g3,j])>t).sum())
            row['G4_LOO_count_'+tag]=int((abs(Z[g4,j])>t).sum())
        row['excess_count']=row['G3_count_3']-row['G4_LOO_count_3']
        ranking.append(row)
        for ar,mask in [(3,g3),(4,g4)]:
            vals=Y[mask,j]
            stats.append(dict(metric=c,label_ru=row['label_ru'],archive=ar,n=19,
                              mean=vals.mean(),median=np.median(vals),sd=vals.std(ddof=1),
                              robust_sd=robust_sd(vals),p10=np.quantile(vals,.1),
                              p90=np.quantile(vals,.9),min=vals.min(),max=vals.max(),
                              n_fully_visible=int((coverage[mask,j]==1).sum())))
    rank=pd.DataFrame(ranking).sort_values(
        ['G3_count_3','excess_count','G3_median_abs_score','metric'],
        ascending=[False,False,False,True]).reset_index(drop=True)
    rank.insert(0,'rank',np.arange(1,101))
    top=set(rank.head(10).metric);overlaps={}
    for tag in ['2p5','3p5']:
        cand=rank.sort_values(['G3_count_'+tag,'G4_LOO_count_'+tag,'G3_median_abs_score','metric'],
                             ascending=[False,True,False,True]).head(10)
        overlaps[tag]=len(top&set(cand.metric))
    # Reference bootstrap describes composition sensitivity, not true defect rates.
    boot=[]
    for _ in range(1000):
        ref=Y[g4][rng.integers(0,19,19)]
        boot.append((abs((Y[g3]-np.median(ref,axis=0))/np.maximum(robust_sd(ref),floor))>3).sum(0))
    for q,label in [(0.05,'p05'),(.5,'p50'),(.95,'p95')]:
        vals=np.quantile(boot,q,axis=0)
        rank['bootstrap_count_'+label]=rank.metric.map(dict(zip(cols,vals)))
    # Visible-only screen is secondary and often underpowered.
    visible_screen=[]
    for j,c in enumerate(cols):
        vref=g4 & (coverage[:,j]==1);v3=g3 & (coverage[:,j]==1)
        r=dict(metric=c,G3_eligible=int(v3.sum()),G4_reference_eligible=int(vref.sum()),
               G3_count_over3=None,reason='fewer_than_8_fully_visible_reference_frames')
        if vref.sum()>=8:
            r['G3_count_over3']=int((abs((Y[v3,j]-np.median(Y[vref,j]))/
                                        max(robust_sd(Y[vref,j]),floor[j]))>3).sum())
            r['reason']='secondary_fully_visible_reference_no_independent_validation'
        visible_screen.append(r)
    pd.DataFrame(visible_screen).to_csv(OUT/'visible_only_sensitivity100.csv',index=False)
    pd.DataFrame(stats).to_csv(OUT/'statistics_new100_groups.csv',index=False)
    rank.to_csv(OUT/'ranking_new100.csv',index=False)
    rank.head(10).to_csv(OUT/'TOP10_new100.csv',index=False)
    events=[]
    for i in range(len(G)):
        for j in np.where(abs(Z[i])>3)[0]:
            events.append(dict(frame=G.frame[i],date=G.date[i],archive=int(G.archive[i]),
                               metric=cols[j],value=Y[i,j],score=Z[i,j],visible_fraction=coverage[i,j]))
    pd.DataFrame(events).to_csv(OUT/'flagged_instances_new100.csv',index=False)
    ff=G[['frame','date','archive']].copy()
    ff['n_new100_flags']=(abs(Z)>3).sum(1)
    ff.to_csv(OUT/'frame_flags_new100.csv',index=False)
    # Region and family summaries retain all regions, not only the top-N.
    summaries=[]
    for cut in ['region','family']:
        for key in dic[cut].unique():
            js=np.where(dic[cut].eq(key))[0]
            r=dict(cut=cut,name=key,metrics=len(js))
            for ar,mask in [(3,g3),(4,g4)]:
                flags=abs(Z[mask][:,js])>3
                r[f'G{ar}_flagged_cells']=int(flags.sum())
                r[f'G{ar}_eligible_cells']=int(flags.size)
                r[f'G{ar}_flagged_percent']=100*flags.mean()
                r[f'G{ar}_median_flags_per_frame']=np.median(flags.sum(1))
            summaries.append(r)
    pd.DataFrame(summaries).to_csv(OUT/'region_family_summary.csv',index=False)
    # Date window sensitivity, no inferred speed between irregularly spaced frames.
    window=g3 & (G.date<=G.loc[g4,'date'].max()).to_numpy()
    pd.DataFrame(dict(metric=cols,n_G3_in_date_window=int(window.sum()),
                      flags_over3=(abs(Z[window])>3).sum(0))).to_csv(
                          OUT/'date_window_sensitivity.csv',index=False)
    # Preserve all 246 values, not 246 independent pieces of evidence.
    combined=previous.merge(allvalues.drop(columns='date'),on='frame',validate='one_to_one')
    assert len(combined)==144 and len(combined.select_dtypes('number').columns)==246
    combined.to_csv(OUT/'all246_original144.csv',index=False)
    G[['frame','archive']].merge(combined,on='frame',validate='one_to_one').to_csv(
        OUT/'all246_groups38.csv',index=False)
    # Independent raw-data check of the leading count and centroid-fan area algebra.
    lead=rank.iloc[0];j=cols.index(lead.metric)
    directcount=0
    for i in np.where(g3)[0]:
        path=ROOT/'raw/1'/('ldm106_aligned_'+G.frame[i]+'.csv')
        pp=pd.read_csv(path).sort_values('landmark_id')[['x','y','z']].to_numpy()
        if abs((compute(pp)[j]-center[j])/scale[j])>3:directcount+=1
    assert directcount==lead.G3_count_3
    ids=REGIONS['eye_L'][1];q=gp[0,ids];cc=q.mean(0)
    independent_area=sum(np.linalg.norm(np.cross(q[k]-cc,q[(k+1)%len(q)]-cc))/2
                         for k in range(len(q)))
    assert np.isclose(independent_area,geometry(q,4)[1],rtol=1e-12)
    saved=pd.read_csv(OUT/'additional100_scores38_G4_LOO.csv')
    for _,r in rank.iterrows():
        assert (saved.loc[saved.archive==3,r.metric].abs()>3).sum()==r.G3_count_3
        assert (saved.loc[saved.archive==4,r.metric].abs()>3).sum()==r.G4_LOO_count_3
    common=G[['frame','archive']].merge(
        pd.read_csv(ROOT/'output_v3/frame_stability38.csv')[['frame','n_of100_over3']],on='frame')
    # Do not pool old and new ranks: each family has its own descriptor contract.
    evidence=dict(
        scope=dict(original_frames=144,new_metrics=100,previous_metrics=146,total_descriptors=246,
                   group3_images=50,group3_measured=19,group4_measured=19,missing31_unchanged=True,
                   new_attachment_is_definitions_and_prior_results_not_new_coordinates=True),
        top10=rank.head(10).to_dict('records'),
        all_region_family_summaries=summaries,
        median_flags={str(ar):float(ff.loc[ff.archive==ar,'n_new100_flags'].median()) for ar in [3,4]},
        percent_flagged_cells={str(ar):float((abs(Z[G.archive==ar])>3).mean()*100) for ar in [3,4]},
        top10_overlap_threshold=overlaps,
        baseline_floor_active_metrics=int(rank.floor_active.sum()),
        similarity_invariance_max_abs=float(invariant),
        raw_aligned_max_abs=float(max(raw_errors)),
        exact_duplicates_vs_previous146=duplicates,
        supplied_archive_numeric_features_checked=len(suppliedcols),
        seed=SEED,
        method='G4 median, max(1.4826MAD, synthetic iid sigma=.001D propagated SD); G4 LOO; threshold abs(score)>3',
        noise_trials_per_reference=60,reference_bootstraps=1000,
        independent_leading_metric_count=directcount,
        visual_plan=[dict(question='Which new metrics flag most archive3 frames vs control?',
                         grain='metric × group',population='19 available G3,19 G4',unit='flagged frames',
                         disposition='chart',reason='five leading descriptors, complete top10 in table',
                         finding=f'Leader flags {int(lead.G3_count_3)} of19 vs {int(lead.G4_LOO_count_3)} of19 LOO'),
                     dict(question='What is omitted by top5?',grain='all10 regions and families',
                          population='38 measured',unit='flagged descriptor cells, not defect probability',
                          disposition='table',reason='preserve all100 and region counterexamples in CSV/report')])
    (OUT/'evidence_new100.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
    # Short lookup labels avoid wrapping away the plotted data.
    top5=rank.head(5)
    short_labels={
        'v4_nose_pca_flat':'Нос: форма',
        'v4_nose_radius_cv':'Нос: радиусы',
        'v4_area_base_to_nose':'Основание / нос',
        'v4_cheek_R_first_path_arc':'Щека R: дуга',
        'v4_cheek_L_first_path_arc':'Щека L: дуга',
    }
    chart=dict(version=1,form='categorical-bars',mode='grouped',orientation='vertical',
               title='Пять лидеров среди ещё 100 новых метрик',
               aside='Измерены 19/50 кадров архива 3 и 19/19 архива 4',
               labels=[short_labels.get(r.metric,r.label_ru) for _,r in top5.iterrows()],
               tooltipLabels=top5.label_ru.tolist(),
               axis=dict(zero=True),derived=True,
               derivationReason='Number of measured frames with abs(robust score)>3; reference G4, controls leave-one-out',
               colorMap={'Архив 3':'orange','Архив 4, LOO':'blue'},
               series=[dict(label='Архив 3',valueKind='count',role='subject',
                            data=top5.G3_count_3.astype(int).tolist()),
                       dict(label='Архив 4, LOO',valueKind='count',role='base',
                            data=top5.G4_LOO_count_3.astype(int).tolist())])
    (ROOT/'analysis/v4/chart_spec.json').write_text(json.dumps(chart,ensure_ascii=False,indent=2))
    write_report(dic,rank,pd.DataFrame(stats),evidence,ff)
    print(json.dumps(dict(scope=evidence['scope'],top10=rank.head(10)[[
        'rank','metric','label_ru','G3_count_3','G4_LOO_count_3','G3_mean','G4_mean',
        'floor_active','G3_fully_visible','G4_fully_visible']].to_dict('records'),
        median_flags=evidence['median_flags'],flagged_cells=evidence['percent_flagged_cells'],
        floors=evidence['baseline_floor_active_metrics'],invariance=evidence['similarity_invariance_max_abs'],
        raw_aligned=evidence['raw_aligned_max_abs'],threshold_stability=overlaps),ensure_ascii=False,indent=2))

def write_report(dic,rank,stats,e,ff):
    text='''# Ещё 100 метрик: региональные площади и пропорции 3DDFA-V3

## Объём и источник

Добавлены ровно 100 дескрипторов к предыдущим 146; теперь сохранены 246 значений на кадр исходной серии из 144 реконструкций. Это НЕ 246 независимых тестов. Новые 100 вычислены заново по исходным координатам, не скопированы из нового ZIP.

В последнем «Архив.zip» находятся описания и результаты прежнего анализа: 17 геометрических признаков, скрипты, кросс-проверки 106/134, списки экстремумов. Он использован как справочник анатомических областей, а не как новые исходные координаты. Название 90plus означает отбор точек по >=90% видимости в прежней серии, а не 90 новых независимых метрик.

Покрытие групп не изменилось: архив 3 — 19 измеримых из 50 PNG, архив 4 — 19 из 19. Для остальных 31 координат по-прежнему нет. Они сохранены как пропуски в таблице всех 69, не нули. Новые числа относятся к тому же доступному периоду архива 3 до 2012-03-05, не к поздним изображениям до 2025 года.

## Что именно добавлено

10 областей × 8 относительных дескрипторов = 80; ещё 20 отношений площадей между областями = 100.

Области: оба глаза, обе брови, нос, основание носа, наружный и внутренний контуры губ, два щёчно-челюстных патча. У патчей есть контурные точки 0/4/8 и 32/28/24; это прокси области щеки и верхней ветви челюсти, НЕ вся нижняя челюсть. Лоб, уши и поверхность кожи без опорных точек не выдумывались.

Для каждой области определён замкнутый упорядоченный полигон Q и арифметический центр C. Веерная площадь:

`A_fan = sum_i 0.5*||cross(Q_i-C,Q_(i+1)-C)||`.

Это сумма плоских треугольников между центром и границей. Она не равна площади кожи, площади текстурного дефекта или плотной поверхности mesh. Для вогнутого/скрученного контура возможны перекрытия; поэтому это воспроизводимый дескриптор, а не физическая площадь. Векторная площадь `A_vector=0.5*||sum cross(Q_i-C,Q_(i+1)-C)||` может быть меньше веерной при неплоской границе.

Восемь дескрипторов на область:
1. Компактность веерной площади `4π A_fan / perimeter²`.
2. Отношение векторной площади к веерной.
3. CV радиусов вершин относительно центра: population SD / mean.
4. CV длин рёбер: population SD / mean. Зависит от фиксированной плотности размещения вершин.
5. Главный поперечный размер / продольный: `sqrt(λ2/λ1)`.
6. Внеплоскостность: `sqrt(λ3/λ1)`; λ — собственные значения ковариации координат вершин по убыванию.
7. Доля веерной площади первого явно заданного пути границы.
8. Доля периметра первого пути.

Для глаз первый путь проходит по верхней дуге; для рта — по верхнему контуру; у остальных областей это технический путь указанных рёбер, не обязательно ровно половина анатомического участка. Точный порядок, замыкающее ребро и число рёбер первого пути — regions10.csv.

Все 100 значений безразмерны и инвариантны к общему масштабу, переносу и собственному повороту. L/R — техническая сторона схемы индексов; анатомическая сторона человека не устанавливалась.

## Сравнение групп

Рабочий референс — все 19 кадров архива 4, без отбора по числу будущих отклонений. Центр — медиана; масштаб — max(1.4826 MAD, synthetic floor). Порог флага — |score|>3. Для архива 4 центр/MAD вычисляются без проверяемого кадра (leave-one-out).

Synthetic floor — медиана SD метрики по 19 референсным кадрам при 60 независимых координатных возмущениях с σ=0.001D; D — расстояние между серединами хорд уголков глаз. Это гипотетический сценарий чувствительности, не измеренный шум 3DDFA. Для обоих наборов используется один floor. Если MAD меньше floor, частота флагов зависит от этого предположения; столбец floor_active это явно отмечает.

Рейтинг новых 100: число флагов архива 3; при равенстве — превышение над LOO-частотой архива 4, затем медиана |score| и код. Это исследовательский скрининг, не z-тест, не вероятность ошибки и не классификатор с установленной точностью.

## Топ‑10 только новых метрик

'''
    text+=mdtable(['№','Метрика','А3: флаги из19','А4: LOO из19','Среднее А3','Среднее А4','floor активен'],
                  [[int(r['rank']),r.label_ru,int(r.G3_count_3),int(r.G4_LOO_count_3),
                    f'{r.G3_mean:.6f}',f'{r.G4_mean:.6f}','да' if r.floor_active else 'нет']
                   for _,r in rank.head(10).iterrows()])
    text+='\n\nЭто не замена прошлого топ‑10: здесь другой набор новых дескрипторов. Не следует смешивать ранги двух серий. Первые две метрики связаны по частоте (по 13/19), а порядок внутри равенства определяется контрольной частотой.\n\n'
    text+='### В какую сторону отличаются значения\n\n'
    text+=mdtable(['Метрика','Среднее А3','Среднее А4','Направление среднего А3−А4'],
                  [[r.label_ru,f'{r.G3_mean:.6f}',f'{r.G4_mean:.6f}',
                    'выше' if r.G3_mean>r.G4_mean else 'ниже' if r.G3_mean<r.G4_mean else 'равно']
                   for _,r in rank.head(10).iterrows()])
    text+='\n\nУвеличение частоты флагов не означает, что все значения выше: например, неравномерность радиусов носа в среднем ниже в архиве 3. Аномалии определены по модулю отклонения в обе стороны.\n\n'
    text+='### Видимость определяющих вершин топ‑10\n\n'
    text+=mdtable(['Метрика','Все вершины visible=1 А3, из19','Все вершины visible=1 А4, из19'],
                  [[r.label_ru,int(r.G3_fully_visible),int(r.G4_fully_visible)]
                   for _,r in rank.head(10).iterrows()])
    text+='\n\nУ трёх лидирующих носовых дескрипторов ни в одной группе нет кадра со всеми вершинами visible=1 одновременно. Эти результаты нельзя считать подтверждёнными измерениями полностью видимой границы. Они описывают также восстановленные моделью участки. Поле visible предоставлено экспортёром и не является проверенной мерой точности.\n\n'
    text+=f"Медиана числа флагов новых100 на кадр: А3 {e['median_flags']['3']:g}, А4 {e['median_flags']['4']:g}. Доля flagged ячеек: {e['percent_flagged_cells']['3']:.2f}% против {e['percent_flagged_cells']['4']:.2f}%. Это не доля дефектных фото: метрики зависимы.\n\n"
    text+='## Все области и семейства, включая не вошедшие в топ\n\n'
    text+=mdtable(['Срез','Область/семейство','Метрик','А3 флагов / ячеек','А4 LOO флагов / ячеек'],
                  [[r['cut'],r['name'],r['metrics'],
                    f"{r['G3_flagged_cells']}/{r['G3_eligible_cells']}",
                    f"{r['G4_flagged_cells']}/{r['G4_eligible_cells']}"] for r in e['all_region_family_summaries']])
    reg={r['name']:r for r in e['all_region_family_summaries'] if r['cut']=='region'}
    text+='\n\nНовые дескрипторы особенно выделяют нос и щёчно-челюстной патч R, но не все области: '
    text+=f"для брови L доля флагов одинакова — {reg['brow_L']['G3_flagged_percent']:.2f}% и {reg['brow_L']['G4_flagged_percent']:.2f}% из 19×8 ячеек на группу. "
    text+='Это не сравнение вероятностей дефекта.\n\nОбратные случаи (в контроле флагов больше):\n\n'
    reverse=rank[rank.G4_LOO_count_3>rank.G3_count_3]
    text+=mdtable(['Метрика','А3, из19','А4 LOO, из19'],
                  [[r.label_ru,int(r.G3_count_3),int(r.G4_LOO_count_3)]
                   for _,r in reverse.iterrows()])
    text+='\n\n## Проверки устойчивости и ограничения\n\n'
    text+=f"- Ни одна из новых колонок не совпала по всем 144 кадрам с предыдущими 146 или с 17 признаками из нового ZIP (допуск rtol1e-8, atol1e-10). Это проверка отсутствия точного повтора, НЕ независимости: дескрипторы коррелированы и некоторые функционально связаны.\n- Максимальная абсолютная разность после случайного поворота, переноса и масштаба: {e['similarity_invariance_max_abs']:.3g}; raw/aligned: {e['raw_aligned_max_abs']:.3g}. Raw/aligned — не независимые измерения.\n- Floor активен у {e['baseline_floor_active_metrics']} из 100 метрик.\n- В топ‑10 сохраняется {e['top10_overlap_threshold']['2p5']}/10 при пороге2.5 и {e['top10_overlap_threshold']['3p5']}/10 при3.5; точный порядок и числа не фиксированы.\n"
    lead=rank.iloc[0]
    text+=f"- Перевыборка референса: 1000 bootstrap. Для лидера основной счёт {int(lead.G3_count_3)}, а 5–95 процентили по составу референса — {lead.bootstrap_count_p05:g}…{lead.bootstrap_count_p95:g}. Это чувствительность, не доверительный интервал истинной частоты ошибок.\n"
    text+='''- В defining_visibility38.csv указана доля определяющих вершин с visible=1, отдельно от значений. Невидимые точки остаются модельными, не нулевыми. visible не калиброванная уверенность. Видимость первичных составных метрик часто неполная; visible_only_sensitivity100.csv рассчитывает вторичную проверку только при >=8 полностью видимых референсных кадрах. При меньшем числе результат оставлен пустым.
- Возраст/выражение/ракурс/свет не разделены причинно. Реконструкция 3DDFA-V3 содержит identity и expression; особенно рот может отличаться из-за мимики, а не сбоя.
- Геометрические площади не локализуют пиксели дефектов UV. Без mesh↔UV↔фото соответствия нельзя доказать, что конкретное пятно вызвано конкретной вершиной.
- Области с криволинейными границами аппроксимируются редкими вершинами. Отношения площади небольших зон могут усиливать отклонения в знаменателе.
- Референс мал и не идеально чист. Флаги архива 4 показывают его собственную изменчивость, а не доказанные ложные срабатывания.
- Для окон дат есть date_window_sensitivity.csv. Нерегулярный шаг кадров не трактовался как скорость изменения лица.

## Хронология доступных кадров

'''
    for ar in [3,4]:
        text+=f'### Архив {ar}\n\n'
        text+=mdtable(['Кадр','Флагов новых100'],
                      [[r.frame,int(r.n_new100_flags)] for _,r in ff[ff.archive==ar].sort_values('frame').iterrows()])+'\n\n'
    text+='## Словарь ровно 100 новых дескрипторов\n\n'
    text+=mdtable(['Код','Название','Формула','Упорядоченные ID106'],[
        [r.metric,r.label_ru,r.formula,r.ids106] for _,r in dic.iterrows()])
    text+='''\n\n## Файлы

- additional100_all144.csv — новые100 по исходной серии.
- additional100_groups38.csv — те же значения по двум пользовательским группам.
- additional100_all69_missing_explicit.csv — покрытие всех69 с явными пропусками31.
- all246_original144.csv, all246_groups38.csv — объединённые146+100.
- statistics_new100_groups.csv — среднее, медиана, SD, robustSD, P10/P90, min/max по каждой группе.
- ranking_new100.csv, TOP10_new100.csv — основной рейтинг и bootstrap-перевыборки.
- regions10.csv, additional100_dictionary.csv — регионы, формулы, порядок вершин.
- defining_visibility38.csv, visible_only_sensitivity100.csv — ограничения видимости.
- frame_flags_new100.csv, flagged_instances_new100.csv — хронология и каждый флаг.
- region_family_summary.csv — все области, не только лидеры.
- scripts/additional100.py — воспроизводимый расчёт; требует исходных CSV и таблиц предыдущего этапа по путям /data.

Диаграмма показывает первые пять строк топ‑10; полные названия в подсказках и таблице.

## Источники

Исходные координаты: первоначальный «Архив 2.zip»; пользовательские группы: «Архив 3.zip», «Архив 4.zip». Новый ZIP с описаниями использован как справочник, код из него не запускался. Структура проверена профилировщиком: даты текущих измерений разобраны как даты; даты прежних экстремумов/ABA не использованы в расчёте; эти строки не принимались за независимые фото. Поля landmark_ids и sizes — списки, не одиночные числа; постоянное all_144_values_present — метаданные, не измерение. Кластерные метки не переиспользовались как истинные классы. Старое визуальное деление A/B/C и служебный order не включены в объединённые 246 метрик.

Официальное описание модели: https://github.com/wang-zidu/3DDFA-V3 и https://github.com/wang-zidu/3DDFA-V3/blob/main/model/recon.py
'''
    (OUT/'REPORT_ADDITIONAL100_RU.md').write_text(text)

if __name__=='__main__':
    main()