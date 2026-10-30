import numpy as np

BASE=[66,70,75,79]
CHAINS={
 'upper_lid_L':('Верхнее веко L',[66,67,68,69,70]),
 'upper_lid_R':('Верхнее веко R',[75,76,77,78,79]),
 'lower_lid_L':('Нижнее веко L',[66,73,72,71,70]),
 'lower_lid_R':('Нижнее веко R',[75,82,81,80,79]),
 'upper_brow_L':('Верхняя граница брови L',[33,34,35,36,37]),
 'upper_brow_R':('Верхняя граница брови R',[42,43,44,45,46]),
 'lower_brow_L':('Нижняя граница брови L',[33,41,40,39,38,37]),
 'lower_brow_R':('Нижняя граница брови R',[42,50,49,48,47,46]),
 'nasal_ridge':('Спинка–кончик–основание носа',[51,52,53,54,60]),
 'nasal_side_L':('Боковой носовой путь L',[51,55,56,57,58,59,60]),
 'nasal_side_R':('Боковой носовой путь R',[51,65,64,63,62,61,60]),
 'upper_lip':('Верхний контур губ',list(range(84,91))),
 'lower_lip':('Нижний контур губ',[84,95,94,93,92,91,90]),
 'jaw_L':('Ветвь контура L',list(range(17))),
 'jaw_R':('Ветвь контура R',list(range(32,15,-1))),
}
DESCRIPTORS=[
 ('total_turn','Суммарный поворот','sum(arccos(dot(unit_e_i,unit_e_next)))/pi'),
 ('turn_concentration','Концентрация изгиба','max(turn_angles)/sum(turn_angles)'),
 ('turn_cv','Неравномерность изгиба','SD_population(turn_angles)/mean(turn_angles)'),
 ('mean_dihedral','Средний поворот соседних плоскостей','mean(arccos(dot(unit_cross_i,unit_cross_next)))/pi'),
 ('sagitta_rms','RMS отклонения от хорды','sqrt(mean(squared_distance(interior_points,chord_line)))/chord_length'),
 ('arc_center_offset','Сдвиг центра длины вдоль хорды','dot(length_weighted_segment_midpoint-Q0,unit_chord)/chord_length-0.5'),
]
QUADS=[
 ('eyes_brows_outer','Брови–наружные уголки',(35,44,66,79)),
 ('eyes_brows_inner','Брови–внутренние уголки',(35,44,70,75)),
 ('upper_lower_eyes','Верхние–нижние точки глаз',(68,77,72,81)),
 ('eye_corners','Четыре уголка глаз',(66,70,75,79)),
 ('brow_bounds','Границы обеих бровей',(33,37,42,46)),
 ('bridge_base','Верх–основание носа',(55,65,58,62)),
 ('nose_wings_base','Крылья–основание носа',(57,63,58,62)),
 ('nose_ridge_sides','Спинка–боковые точки носа',(51,54,56,64)),
 ('mouth_corners_peaks','Уголки–центры губ',(84,90,87,93)),
 ('mouth_sides','Боковые точки губ',(85,89,91,95)),
 ('eyes_mouth_outer','Наружные уголки глаз–рот',(66,79,84,90)),
 ('eyes_mouth_inner','Внутренние уголки глаз–рот',(70,75,84,90)),
 ('nose_mouth','Крылья носа–уголки рта',(57,63,84,90)),
 ('jaw_upper_lower','Верх–низ челюстного контура',(3,29,10,22)),
 ('chin_sides','Низ контура–подбородок',(10,22,13,19)),
 ('eyes_jaw','Глаза–средний контур',(66,79,6,26)),
 ('mouth_jaw','Рот–нижний контур',(84,90,10,22)),
 ('brow_nose','Брови–верх носа',(35,44,55,65)),
 ('ridge_chin_mouth','Нос–подбородок–уголки рта',(51,16,84,90)),
 ('inner_outer_lips','Уголки внутреннего–наружного контура',(84,90,96,100)),
]
TETRA=[
 ('nose_full','Корень–верх–кончик носа',(51,55,65,54)),
 ('nose_side_L','Боковой носовой объём L',(55,57,54,60)),
 ('nose_side_R','Боковой носовой объём R',(65,63,54,60)),
 ('nostril_L','Основание–кончик носа L',(57,58,60,54)),
 ('nostril_R','Основание–кончик носа R',(63,62,60,54)),
 ('eye_L','Контур глаза L',(66,70,68,72)),
 ('eye_R','Контур глаза R',(75,79,77,81)),
 ('brow_L','Контур брови L',(33,35,37,39)),
 ('brow_R','Контур брови R',(42,44,46,49)),
 ('lips','Уголки–центры губ',(84,90,87,93)),
 ('cheek_L','Глаз–нос–рот–контур L',(66,57,84,3)),
 ('cheek_R','Глаз–нос–рот–контур R',(79,63,90,29)),
 ('central_nose','Внутренние уголки–основание–кончик',(70,75,60,54)),
 ('lower_cheek_L','Нижняя щека L',(3,10,16,84)),
 ('lower_cheek_R','Нижняя щека R',(29,22,16,90)),
 ('face','Глаза–корень носа–подбородок',(66,79,51,16)),
 ('lower_face','Рот–основание носа–подбородок',(84,90,60,16)),
 ('bridge_eye_L','Переносица–верхнее веко L',(55,65,51,68)),
 ('bridge_eye_R','Переносица–верхнее веко R',(55,65,51,77)),
 ('nose_lip','Основание носа–нижняя губа',(57,63,60,93)),
]
PAIRS=[
 ('outer_canthus','Наружные уголки глаз',66,79),
 ('inner_canthus','Внутренние уголки глаз',70,75),
 ('upper_lids','Верхние точки век',68,77),
 ('lower_lids','Нижние точки век',72,81),
 ('brow_peaks','Пики бровей',35,44),
 ('brow_lower','Низ бровей',39,49),
 ('bridge','Верх носа',55,65),
 ('nose_wings','Крылья носа',57,63),
 ('mouth','Уголки рта',84,90),
 ('jaw','Низ челюстного контура',10,22),
]
ANCHORS=[51,54,60,16]

def chain_metrics(Q):
    e=np.diff(Q,axis=0);lens=np.linalg.norm(e,axis=1)
    assert lens.min()>1e-12
    u=e/lens[:,None]
    turns=np.arccos(np.clip(np.sum(u[:-1]*u[1:],axis=1),-1,1))
    norms=np.cross(u[:-1],u[1:]);sines=np.linalg.norm(norms,axis=1)
    assert sines.min()>1e-12
    normals=norms/sines[:,None]
    dihedrals=np.arccos(np.clip(np.sum(normals[:-1]*normals[1:],axis=1),-1,1))
    chord=Q[-1]-Q[0];length=np.linalg.norm(chord);axis=chord/length
    delta=Q[1:-1]-Q[0];perp=delta-(delta@axis)[:,None]*axis
    centroid=((Q[:-1]+Q[1:])/2*lens[:,None]).sum(0)/lens.sum()
    vals=[turns.sum()/np.pi,turns.max()/turns.sum(),turns.std()/turns.mean(),
          dihedrals.mean()/np.pi,np.sqrt(np.mean(np.sum(perp*perp,axis=1)))/length,
          np.dot(centroid-Q[0],axis)/length-.5]
    return vals,float(sines.min())

def compute(P,quality=False):
    values=[];minimum_sine=1.
    for _,ids in CHAINS.values():
        v,s=chain_metrics(P[ids]);values.extend(v);minimum_sine=min(s,minimum_sine)
    d=lambda a,b:np.linalg.norm(P[a]-P[b])
    for _,_,(a,b,c,e) in QUADS:
        values.append(d(a,b)*d(c,e)/(d(a,c)*d(b,e)))
    ex=(P[75]+P[79]-P[66]-P[70])/2;D=np.linalg.norm(ex);ex=ex/D
    for _,_,(a,b,c,e) in TETRA:
        values.append(np.dot(P[b]-P[a],np.cross(P[c]-P[a],P[e]-P[a]))/(6*D**3))
    # Root-anchored plane avoids built-in equality of inner/outer canthal
    # residuals caused by defining its origin from the same four canthi.
    origin=P[51]
    for _,_,a,b in PAIRS:
        reflected=P[b]-2*np.dot(P[b]-origin,ex)*ex
        values.append(np.linalg.norm(P[a]-reflected)/D)
        dl=np.linalg.norm(P[a]-P[ANCHORS],axis=1)
        dr=np.linalg.norm(P[b]-P[ANCHORS],axis=1)
        values.append(np.mean((dl-dr)/(dl+dr)))
    result=np.array(values)
    assert result.shape==(150,) and np.isfinite(result).all()
    return (result,minimum_sine) if quality else result

def dictionary():
    rows=[]
    def add(code,label,family,region,formula,ids,unit='ratio',signed=False):
        rows.append(dict(metric='v5_'+code,label_ru=label,family=family,region=region,
                         formula=formula,ids106=','.join(map(str,sorted(set(ids)))),
                         unit=unit,signed=signed))
    for region,(label,ids) in CHAINS.items():
        for code,desc,formula in DESCRIPTORS:
            add(region+'_'+code,label+': '+desc,code,region,formula,ids,
                'angle_pi' if code in ['total_turn','mean_dihedral'] else 'ratio',
                code=='arc_center_offset')
    for code,label,ids in QUADS:
        a,b,c,d=ids
        add('quad_'+code,label+': произведение расстояний','four_point_ratio','cross_region',
            f'd({a},{b})*d({c},{d})/(d({a},{c})*d({b},{d}))',ids)
    for code,label,ids in TETRA:
        a,b,c,d=ids
        add('tetra_'+code,label+': ориентированный объём / D³','tetra_volume','cross_region',
            f'dot(P{b}-P{a},cross(P{c}-P{a},P{d}-P{a}))/(6*D^3)',list(ids)+BASE,
            signed=True)
    for code,label,a,b in PAIRS:
        add('mirror_'+code,label+': ошибка зеркального совмещения','mirror_residual',code,
            f'norm(P{a}-(P{b}-2*dot(P{b}-P51,ex)*ex))/D',BASE+[51,a,b])
        add('profile_'+code,label+': асимметрия расстояний до осевых якорей','anchor_profile',code,
            f'mean((d({a},k)-d({b},k))/(d({a},k)+d({b},k)), k={ANCHORS})',
            [a,b]+ANCHORS,signed=True)
    assert len(rows)==150
    return rows