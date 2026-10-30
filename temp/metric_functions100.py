import numpy as np
DICT=[]
baseids=[66,70,75,79]
axisids=baseids+[51,16]

def dist(P,i,j):return np.linalg.norm(P[i]-P[j])

def vecarea(P):return np.linalg.norm(np.cross(P,np.roll(P,-1,axis=0)).sum(0))/2

def triangle(P,t):return np.linalg.norm(np.cross(P[t[1]]-P[t[0]],P[t[2]]-P[t[0]]))/2

def compute(P,record=False):
    O=(P[66]+P[70]+P[75]+P[79])/4
    ex=(P[75]+P[79]-P[66]-P[70])/2
    D=np.linalg.norm(ex);ex=ex/D
    up=P[51]-P[16];up=up-ex*np.dot(up,ex);up=up/np.linalg.norm(up)
    ez=np.cross(ex,up)
    local=np.stack([(P-O)@ex,(P-O)@up,(P-O)@ez],axis=1)/D
    values=[]
    def add(code,label,family,value,formula,ids,unit='ratio',signed=False):
        values.append(float(value))
        if record:DICT.append(dict(metric=code,label_ru=label,family=family,formula=formula,
                                   ids106=','.join(map(str,sorted(set(ids)))),
                                   unit=unit,signed=signed))
    slopes=[
        ('canthal_L',66,70,'Хорда уголков L'),('canthal_R',75,79,'Хорда уголков R'),
        ('brow_top_L',33,37,'Верхняя хорда брови L'),('brow_top_R',42,46,'Верхняя хорда брови R'),
        ('brow_low_L',40,38,'Нижняя хорда брови L'),('brow_low_R',50,48,'Нижняя хорда брови R'),
        ('lid_upper_L',67,69,'Склон верхнего века L'),('lid_upper_R',76,78,'Склон верхнего века R'),
        ('lid_lower_L',73,71,'Склон нижнего века L'),('lid_lower_R',82,80,'Склон нижнего века R'),
        ('nose_upper',55,65,'Поперечник верхнего носа'),('nose_mid',56,64,'Поперечник середины носа'),
        ('nose_alar',57,63,'Поперечник крыльев носа'),
        ('mouth_chord',84,90,'Хорда уголков рта'),('mouth_upper',86,88,'Верхние пики губ'),
        ('mouth_lower',94,92,'Нижний контур губ'),
        ('contour_upper',3,29,'Верхняя хорда лицевого контура'),
        ('contour_mid',6,26,'Средняя хорда лицевого контура'),
        ('contour_lower',10,22,'Нижняя хорда лицевого контура'),
        ('chin',13,19,'Хорда подбородка')]
    for name,i,j,label in slopes:
        delta=local[j]-local[i]
        add('tilt_'+name,label+' — наклон / π','tilts',
            np.arctan2(delta[1],delta[0])/np.pi,
            f'atan2((P{j}-P{i})·up,(P{j}-P{i})·ex)/pi',axisids+[i,j],'angle_pi',True)
    pairs=[
        ('outer_canthus',66,79,'Наружные уголки глаз'),('inner_canthus',70,75,'Внутренние уголки глаз'),
        ('upper_lid',68,77,'Верхние точки век'),('lower_lid',72,81,'Нижние точки век'),
        ('brow_peak',35,44,'Пики бровей'),('brow_low',39,49,'Нижние точки бровей'),
        ('nose_upper',55,65,'Верхние боковые точки носа'),('nose_mid',56,64,'Средние боковые точки носа'),
        ('nose_alar',57,63,'Крылья носа'),('contour_upper',3,29,'Верхние точки контура'),
        ('contour_lower',10,22,'Нижние точки контура'),('mouth_corner',84,90,'Уголки рта')]
    for name,i,j,label in pairs:
        for coord,axis,nm in [('vertical',1,'вертикальная'),('depth',2,'глубинная')]:
            add('asym_'+name+'_'+coord,label+' — '+nm+' асимметрия','asymmetries',
                local[i,axis]-local[j,axis],f'(P{i}-P{j})·{coord}_axis/D',axisids+[i,j],signed=True)
    triangles=[
        ('eye_upper_L',(66,68,70),'Верхняя половина глаза L'),
        ('eye_upper_R',(75,77,79),'Верхняя половина глаза R'),
        ('eye_lower_L',(66,72,70),'Нижняя половина глаза L'),
        ('eye_lower_R',(75,81,79),'Нижняя половина глаза R'),
        ('nasal_side_L',(55,54,57),'Боковая зона носа L'),
        ('nasal_side_R',(65,54,63),'Боковая зона носа R'),
        ('midface_L',(66,57,84),'Глаз–нос–рот L'),
        ('midface_R',(79,63,90),'Глаз–нос–рот R'),
        ('mandible_L',(3,10,16),'Контур–подбородок L'),
        ('mandible_R',(29,22,16),'Контур–подбородок R'),
        ('cheek_L',(70,57,84),'Внутренний уголок–нос–рот L'),
        ('cheek_R',(75,63,90),'Внутренний уголок–нос–рот R'),
        ('nose_full',(51,57,63),'Корень–крылья носа'),
        ('nose_bridge',(55,54,65),'Верхний носовой треугольник'),
        ('nose_tip',(57,54,63),'Крылья–кончик носа'),
        ('face',(66,79,16),'Наружные уголки–подбородок'),
        ('central',(70,75,60),'Внутренние уголки–основание носа'),
        ('mouth_upper',(84,86,90),'Верхний треугольник рта'),
        ('mouth_lower',(84,93,90),'Нижний треугольник рта'),
        ('jaw',(3,16,29),'Верхний контур–подбородок')]
    for name,t,label in triangles:
        add('triangle_area_'+name,label+' — площадь / D²','triangle_areas',triangle(P,t)/D**2,
            f'0.5*norm(cross(P{t[1]}-P{t[0]},P{t[2]}-P{t[0]}))/D^2',baseids+list(t))
    for name,t,label in triangles[:8]:
        lens=np.array([dist(P,t[0],t[1]),dist(P,t[1],t[2]),dist(P,t[2],t[0])])
        add('triangle_compactness_'+name,label+' — компактность','triangle_shapes',
            4*np.sqrt(3)*triangle(P,t)/(lens*lens).sum(),
            f'4*sqrt(3)*A{t}/sum(edge_lengths^2)',list(t))
        add('triangle_elongation_'+name,label+' — вытянутость','triangle_shapes',
            lens.max()/lens.min(),f'max(edge_lengths{t})/min(edge_lengths{t})',list(t))
    proportions=[
        ('brow_eye_L',35,68,66,70,'Зазор бровь–глаз L / ширина глаза'),
        ('brow_eye_R',44,77,75,79,'Зазор бровь–глаз R / ширина глаза'),
        ('brow_root_L',35,51,51,60,'Бровь–корень носа L / длина носа'),
        ('brow_root_R',44,51,51,60,'Бровь–корень носа R / длина носа'),
        ('outer_eye_mouth_L',66,84,51,16,'Наружный уголок–рот L / высота'),
        ('outer_eye_mouth_R',79,90,51,16,'Наружный уголок–рот R / высота'),
        ('inner_eye_tip_L',70,54,51,60,'Внутренний уголок–кончик L / длина носа'),
        ('inner_eye_tip_R',75,54,51,60,'Внутренний уголок–кончик R / длина носа'),
        ('jaw_side_L',3,16,51,16,'Ветвь контура L / высота'),
        ('jaw_side_R',29,16,51,16,'Ветвь контура R / высота'),
        ('bridge_intercanthal',55,65,70,75,'Верхняя ширина носа / межвнутреннее расстояние'),
        ('height_mouth',51,16,84,90,'Высота корень–подбородок / ширина рта')]
    for name,i,j,k,l,label in proportions:
        add('prop_'+name,label,'proportions',dist(P,i,j)/dist(P,k,l),
            f'd({i},{j})/d({k},{l})',[i,j,k,l])
    polygons=[
        ('brow_L',list(range(33,42)),'Площадь контура брови L'),
        ('brow_R',list(range(42,51)),'Площадь контура брови R'),
        ('nose_upper',[51,55,54,65],'Площадь верхнего носового контура'),
        ('nose_lower',[56,57,58,60,62,63,64,54],'Площадь нижнего носового контура'),
        ('midface_L',[66,70,60,84],'Площадь центральной щеки L'),
        ('midface_R',[75,79,90,60],'Площадь центральной щеки R'),
        ('lower_face_L',[3,6,10,13,16,84],'Площадь нижнего контура L'),
        ('lower_face_R',[29,26,22,19,16,90],'Площадь нижнего контура R')]
    for name,ids,label in polygons:
        add('polygon_area_'+name,label+' / D²','polygon_areas',vecarea(P[ids])/D**2,
            f'norm(sum cross(P_i,P_next) for ordered {ids})/(2*D^2)',baseids+ids)
    assert len(values)==100
    return np.array(values),D