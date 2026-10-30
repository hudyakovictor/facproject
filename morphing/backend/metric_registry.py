"""Реестр метрик формы (3DDFA-V3 + MediaPipe) — боевые определения, живут в проде.

Модуль ничего не знает ни о каких кэшах и выборках: чистые функции от точек. Он
боевой — его значения показывает интерфейс (`form_metrics`), и ровно его формулы
использует валидация (`app9/validation/metric_shortlist.py`, `subfrontal_check.py`).
Второго экземпляра формул нигде нет: иначе боевые числа и числа прогона разошлись бы
при первой же правке.

Зачем. Набор метрик набирался из четырёх источников, и все они меряли не то, что
живёт в проде:

  `morphing/backend/identity.form_vector`  — 17 боевых признаков, они же прод-вход
      классификатора (`/api/identify-probability`);
  `Downloads/compute_all_metrics.py`       — «Top-30» других участников: 18 метрик по
      MediaPipe и 12 по 3DDFA, снятые с невыровненных сеток;
  `Downloads/analyze_faces.py`             — 40 подтверждённых гипотез (20 + 20),
      то же MediaPipe/3DDFA;
  `app9/validation/mp_identity_probe.py`   — 21 MediaPipe-метрика нашего прогона.

Здесь определения перенесены на НАШУ нормировку и пересчитаны заново: значения из
исходных скриптов не используются (они мерялись в чужих единицах и, у 3DDFA, на
сетке с мимикой). Важны сами определения — что во что делится.

Конвенции координат.

3DDFA (`ldm_metrics`, вход q — (106, 3) канон `aligner.align_identity_mesh`,
единицы RMS-106, Y вверх, Z вперёд). Роли проверены не по памяти, а по данным:
каждой точке сопоставлена вершина средней формы и её канал 8-канальной сегментации
(`app9/validation/ldm134_layout.py`), получилось стандартное 106-размечение
(33 контур + 18 брови + 15 нос + 18 глаза + 2 центра зрачков + 20 губы = 106):

    0..32   контур головы: 0 и 32 — ВИСКОЧНЫЕ концы (z = -0.55, то есть сзади лица,
            это ширина головы, не челюсти), 16 — середина подбородка (15 и 17 —
            точки рядом, но со смещением в x на 6% половины подбородка)
    33..41  бровь со стороны x<0 (33 — хвост, 34..37 верхний ряд, 38..41 нижний)
    42..50  бровь со стороны x>0 (42..46 верхний ряд с хвостом, 47..50 нижний)
    51..65  нос целиком: 51 переносица, 52..54 спинка (54 — кончик, самая
            выступающая точка), 55..57 левый бок, 58..62 основание
            (58/62 крылья, 60 — середина основания = subnasale), 63..65 правый бок
    66..74  глаз при x<0 (66..70 верхнее веко, 71..73 нижнее, 74 центр),
    75..83  глаз при x>0 (75..79 верхнее, 80..82 нижнее, 83 центр),
            104/105 — центры зрачков того же ряда
    84..95  внешний контур губ (84/90 — уголки, 87 — пик верхней, 93 — середина
            нижней), 96..103 — линия смыкания (97..99 верх, 101..103 низ)

Историческая ошибка, исправленная здесь: раньше глаза считались как 63..70/71..78
(и так же в `app8/expression_qc.py:46-47`), но 63..65 — это боковая поверхность
носа, а 71..74 — нижнее веко + центр того же глаза, что под x<0. То есть «левый eye
centroid» на самом деле усреднял нос с правым глазом. Метрики, которые это использует,
пересчитаны: `naso_orbital_expansion_3d`, `naso_orbital_expansion`-семейство,
`*_midface_3d`, `central_depth_*`, `nose_tip_protrusion_over_ridge_length_3ddfa`,
`chin_depth_to_nose_protrusion_ratio_3ddfa`, `nasolabial_angle_proxy_3ddfa`,
`mouth_center_nose_offset_3ddfa`.

MediaPipe (`mp_metrics`, вход xy — (478, 2) пиксельные координаты после снятия roll
по линии глаз, z — (478,) в тех же пиксельных единицах; scale — RMS 2D-точек):

    0/17 верх/низ внешней границы губ, 13/14 внутренняя линия смыкания,
    33/133 внешний/внутренний уголок левого глаза, 362/263 — правого,
    159/145 и 386/374 верх/низ век левого/правого глаза,
    468/473 центры радужек, 234/454 скулы, 172/397 углы челюсти,
    98/327 крылья носа (широкие), 49/279 носогубный изгиб,
    168 верх спинки носа, 2 основание носа, 1 кончик, 152 подбородок, 10 лоб.

Замечания по переносу (не «улучшили молча», а зафиксировали):

  * у других участников `face_width_3d = distance(p3[0], p3[31])` — при контуре из 33
    точек правый конец это 32, а не 31; берём 32 и помечаем метрику как исправленную;
  * их 3DDFA-метрики считаются на сетке `id + exp` (с мимикой) в камерном пространстве;
    у нас `vertices_identity_only` без мимики и без позы, поэтому признаки вида
    `*_depth_*`/`*convexity*` стали чище по форме, но численно другие;
  * MediaPipe-метрики из «Top-30» берут 3D-расстояния, где z — отдельная, плохо
    масштабированная координата; оставляем их как есть (это определение), но
    помечаем `uses_z=True`, чтобы при утверждении видеть, на чём стоят цифры.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

EPS = 1e-9

# ── ролевые индексы ldm106 (сверены с сегментацией, см. ldm134_layout.py) ─────
# Префиксы L_/R_ читаются как «сторона кадра»: x<0 и x>0 в каноне aligner. Для
# 106-разметки x<0 — это ПРАВЫЙ глаз/бровь субъекта (так же названы каналы
# сегментации модели: `right_eye` лежит при x<0). Не путать с MediaPipe, где
# «left/right» в API зеркалачны боевому отображению.
L_BROW = list(range(33, 42))    # 9 точек: 33 хвост, 34..37 верхний ряд, 38..41 нижний
R_BROW = list(range(42, 51))    # 9 точек: 42..46 верхний ряд с хвостом, 47..50 нижний
L_BROW_UP, L_BROW_LO = list(range(34, 38)), list(range(38, 42))
R_BROW_UP, R_BROW_LO = list(range(42, 46)), list(range(47, 51))
L_EYE = list(range(66, 74))     # веки глаза при x<0 (74 — центр, не входит)
R_EYE = list(range(75, 83))
EYE_L_CENTER, EYE_R_CENTER = 74, 83
L_PUPIL, R_PUPIL = 104, 105
NASION, NOSE_TIP = 51, 54
RIDGE_MID = (52, 53)
ALAR_L, ALAR_R, NOSE_BASE_MID = 58, 62, 60
SUBNASALE = 60                  # середина основания; 57 — бок носа на уровне кончика
MOUTH_L, MOUTH_R = 84, 90
UP_LIP_MID, LO_LIP_MID = 87, 93
UP_LIP_RING = [86, 87, 88]
LO_LIP_RING = [92, 93, 94]
CHIN, JAW_L, JAW_R = 16, 0, 32


def _c(q: np.ndarray, idx) -> np.ndarray:
    return q[np.asarray(idx, dtype=int)].mean(axis=0)


def _d(q: np.ndarray, i: int, j: int) -> float:
    return float(np.linalg.norm(q[i] - q[j]))


def _ratio(num: float, den: float) -> float:
    return float(num / (den + EPS))


def _angle(a: np.ndarray, v: np.ndarray, b: np.ndarray) -> float:
    """Угол ABC в градусах (вершина — v)."""
    u1, u2 = a - v, b - v
    den = np.linalg.norm(u1) * np.linalg.norm(u2)
    if den < EPS:
        return float("nan")
    return float(math.degrees(math.acos(float(np.clip(np.dot(u1, u2) / den, -1.0, 1.0)))))


# ── 3DDFA: боевые 17 ─────────────────────────────────────────────────────────
def form17(q: np.ndarray) -> dict[str, float]:
    """Боевой вектор `identity.form_vector` — здесь он нужен одной таблицей с остальными."""
    from morphing.backend.identity import FEATURE_ORDER, form_vector

    vec = form_vector(q)
    return {name: float(v) for name, v in zip(FEATURE_ORDER, vec, strict=True)}


# ── 3DDFA: «Top-12» других участников, на нашей сетке ────────────────────────
def ldm_top3d(q: np.ndarray) -> dict[str, float]:
    lb, rb = _c(q, L_BROW), _c(q, R_BROW)
    le, re_ = _c(q, L_EYE), _c(q, R_EYE)
    nb = _c(q, [58, 59, 60, 61, 62])
    ul, ll = _c(q, UP_LIP_RING), _c(q, LO_LIP_RING)
    eye_mid = (le + re_) / 2
    m_h = abs(float(ul[1] - ll[1]))
    m_w = _d(q, MOUTH_L, MOUTH_R)
    n_len = _d(q, NASION, NOSE_TIP)
    n_base = _d(q, ALAR_L, ALAR_R)
    b_span = float(np.linalg.norm(lb - rb))
    eye_anc = float(np.linalg.norm(le - re_))
    c_depth = float(q[NOSE_TIP, 2] - q[np.asarray(L_EYE + R_EYE, int), 2].mean())
    mid_ratio = float(np.linalg.norm(eye_mid - nb)) / (eye_anc + EPS)
    return {
        "mouth_aspect_ratio_3d": _ratio(m_h, m_w),
        "alar_base_over_mouth_height_3d": _ratio(n_base, m_h),
        "mouth_height_3d_ldm": m_h,
        "mouth_area_index_3d": _ratio(m_w * m_h, b_span**2),
        "mouth_height_over_ridge_3d": _ratio(m_h, n_len),
        "mouth_height_over_midface_3d": _ratio(m_h, mid_ratio),
        "nose_ridge_to_mouth_width_3d": _ratio(n_len, m_w),
        "oral_to_nasal_planar_ratio_3d": _ratio(m_w * m_h, n_base * n_len),
        "naso_orbital_expansion_3d": _ratio(mid_ratio * eye_anc, m_w),
        "depth_contrast_over_brow_span_3d": _ratio(c_depth, b_span),
        "central_depth_to_mouth_height_3d": _ratio(c_depth, m_h),
        "central_depth_contrast_ldm": c_depth,
    }


# ── 3DDFA: 8 гипотез _3ddfa из analyze_faces.py ──────────────────────────────
def ldm_hypotheses(q: np.ndarray) -> dict[str, float]:
    """Определения перенесены один в один, но на identity-only-сетке без позы.

    Единственное сознательное исправление: ширина челюсти бралась как distance(0, 31),
    при контуре 0..32 правый конец — 32.
    """
    brow_l, brow_r = _c(q, L_BROW), _c(q, R_BROW)
    eye_l, eye_r = _c(q, L_EYE), _c(q, R_EYE)
    brow_c = (brow_l + brow_r) / 2
    eye_c = (eye_l + eye_r) / 2
    tip, root = q[NOSE_TIP], q[NASION]
    nose_base_3d = _c(q, [SUBNASALE, NOSE_BASE_MID, 61])
    mouth_c = (q[MOUTH_L] + q[MOUTH_R]) / 2
    lip_c = (q[UP_LIP_MID] + q[LO_LIP_MID]) / 2
    chin = q[CHIN]

    vert = chin - brow_c
    vert = vert / (np.linalg.norm(vert) + EPS)
    face_w = _d(q, JAW_L, JAW_R)
    face_h = abs(float(np.dot(chin - brow_c, vert)))
    ridge_len = _d(q, NASION, NOSE_TIP)

    # Прямолинейность спинки: среднее отклонение 52/53 от хорды 51->54, на длину хорды.
    rv = tip - root
    dev = []
    for pk in RIDGE_MID:
        p = q[pk]
        t = float(np.dot(p - root, rv) / (float(np.dot(rv, rv)) + EPS))
        dev.append(float(np.linalg.norm(p - (root + t * rv))))
    ridge_straightness = _ratio(float(np.mean(dev)), ridge_len)

    nose_prominence = float(eye_c[2] - tip[2])
    chin_depth = float((lip_c[2] - chin[2]) / (face_w + EPS))
    nose_t = float(np.dot(tip - brow_c, vert)) / (face_h + EPS)
    line_z = float(brow_c[2] + nose_t * (chin[2] - brow_c[2]))
    midface_convexity = float((line_z - tip[2]) / (face_w + EPS))

    return {
        "chin_depth_projection_3ddfa": chin_depth,
        "nose_bridge_straightness_3ddfa": ridge_straightness,
        "midface_profile_convexity_3ddfa": midface_convexity,
        "nose_tip_protrusion_over_ridge_length_3ddfa": _ratio(nose_prominence, ridge_len),
        "alar_width_over_ridge_length_3ddfa": _ratio(_d(q, ALAR_L, ALAR_R), ridge_len),
        "nasolabial_angle_proxy_3ddfa": _angle(tip, nose_base_3d, q[UP_LIP_MID]),
        "chin_depth_to_nose_protrusion_ratio_3ddfa": _ratio(float(lip_c[2] - chin[2]), nose_prominence),
        "nose_upperlip_chin_angle_3ddfa": _angle(tip, q[UP_LIP_MID], chin),
        "mouth_center_nose_offset_3ddfa": _ratio(float(np.linalg.norm(mouth_c[:2] - nose_base_3d[:2])), face_h),
    }


# ── MediaPipe ─────────────────────────────────────────────────────────────────
def _mp_groups(p: np.ndarray) -> dict[str, float]:
    """Базовые длины по MediaPipe (p — (478,3) в пиксельных единицах после roll-правки)."""
    def d(i: int, j: int) -> float:
        return float(np.linalg.norm(p[i] - p[j]))

    def ang(i: int, v: int, j: int) -> float:
        return _angle(p[i], p[v], p[j])

    iris_l, iris_r = p[468], p[473]
    g = {
        "face_w": d(234, 454),
        "face_h": d(168, 152),
        "lower_h": d(2, 152),
        "mid_h": d(168, 2),
        "mouth_w": d(61, 291),
        "palp_w": d(33, 263),
        "alar_w_49": d(49, 279),
        "alar_w_98": d(98, 327),
        "gonion_w": d(172, 397),
        "chin_h": d(17, 152),
        "ipd": float(np.linalg.norm(iris_l - iris_r)),
        "eye_w_l": d(33, 133),
        "eye_w_r": d(362, 263),
        "eye_h_l": d(159, 145),
        "eye_h_r": d(386, 374),
        "lip_total": d(0, 17),
        "vermilion_top": d(0, 13),
        "vermilion_bot": d(14, 17),
        "ridge_from_nasion": d(168, 2),
    }
    return g


def mp_top30(p: np.ndarray) -> dict[str, float]:
    """18 MediaPipe-метрик из «Top-30». Определения — как у авторов (3D-расстояния)."""
    g = _mp_groups(p)

    def d(i: int, j: int) -> float:
        return float(np.linalg.norm(p[i] - p[j]))

    fw, fh = g["face_w"], g["face_h"]
    m_w, ipd = g["mouth_w"], g["ipd"]
    palp, alar, gonion = g["palp_w"], g["alar_w_49"], g["gonion_w"]
    r_w, r_h = g["eye_w_l"], g["eye_h_l"]
    l_w, l_h = g["eye_w_r"], g["eye_h_r"]
    return {
        "ipd_over_face_w": _ratio(ipd, fw),
        "interpupillary_to_mouth_ratio": _ratio(ipd, m_w),
        "palpebral_to_bigonial_ratio": _ratio(palp, gonion),
        "mouth_to_orbit_span_ratio": _ratio(m_w, palp),
        "zygomatic_to_palpebral_width_ratio": _ratio(fw, palp),
        "mouth_width_to_lower_face_ratio": _ratio(m_w, g["lower_h"]),
        "palpebral_area_index": _ratio(0.5 * (r_w * r_h + l_w * l_h), fw * fh) * 1000.0,
        "palpebral_aspect_ratio": 0.5 * (_ratio(r_h, r_w) + _ratio(l_h, l_w)),
        "lip_thick_over_mouth_w": _ratio(g["lip_total"], m_w),
        "nasal_bridge_convergence_angle": _angle(p[49], p[168], p[279]),
        "alar_to_interpupillary_ratio": _ratio(alar, ipd),
        "nasal_dorsal_index": _ratio(alar, g["mid_h"]),
        "vermilion_to_chin_ratio": _ratio(g["vermilion_top"] + g["vermilion_bot"], g["chin_h"]),
        "cupids_bow_angle": _angle(p[37], p[0], p[267]),
        "mandibular_body_to_ramus_ratio": 0.5 * (
            _ratio(d(172, 152), d(234, 172)) + _ratio(d(397, 152), d(454, 397))
        ),
        "mentolabial_sulcus_ratio": _ratio(_perp(p[18], p[17], p[152]), g["chin_h"]),
        "mouth_w_over_face_w": _ratio(m_w, fw),
        "zygomatic_to_mouth_width_ratio": _ratio(fw, m_w),
    }


def _perp(point: np.ndarray, origin: np.ndarray, target: np.ndarray) -> float:
    """Расстояние от point до прямой origin—target (в координатах p)."""
    axis = target - origin
    axis = axis / (np.linalg.norm(axis) + EPS)
    v = point - origin
    return float(np.linalg.norm(v - np.dot(v, axis) * axis))


LIP_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146]
LIP_UPPER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191, 78]
LIP_LOWER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95, 78]
BROW_L = [70, 63, 105, 66, 107]
BROW_R = [336, 296, 334, 293, 300]
# Пары «левое/правое» для проверки симметрии (как MP_SYMMETRY_PAIRS в analyze_faces.py).
SYM_PAIRS = [(234, 454), (33, 263), (133, 362), (61, 291), (98, 327), (172, 397), (70, 300)]


def _polygon_area(pts: np.ndarray) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)


def mp_hypotheses(p: np.ndarray) -> dict[str, float]:
    """40 подтверждённых гипотез из analyze_faces.py (20 + 20 заключительной итерации)."""
    g = _mp_groups(p)

    def d(i: int, j: int) -> float:
        return float(np.linalg.norm(p[i] - p[j]))

    fw, fh = g["face_w"], g["face_h"]
    m_w = g["mouth_w"]
    ipd = g["ipd"]
    intercanthal = d(133, 362)
    lower_jaw_w = d(172, 397)
    nose_w = g["alar_w_98"]
    left_eye = (p[33] + p[133]) / 2
    right_eye = (p[362] + p[263]) / 2
    eye_line = (left_eye + right_eye) / 2
    nose_base = (p[98] + p[327]) / 2
    brow_l, brow_r = p[np.asarray(BROW_L)].mean(0), p[np.asarray(BROW_R)].mean(0)
    brow_eye_l = abs(float(left_eye[1] - brow_l[1]))
    brow_eye_r = abs(float(right_eye[1] - brow_r[1]))
    eye_w_l, eye_w_r = g["eye_w_l"], g["eye_w_r"]
    mean_eye_w = (eye_w_l + eye_w_r) / 2
    nose_len_2d = abs(float(p[168, 1] - nose_base[1]))
    mouth_center = (p[61] + p[291]) / 2
    lower_third = abs(float(p[152, 1] - nose_base[1]))
    brow_line_y = float((brow_l[1] + brow_r[1]) / 2)
    upper_third = abs(float(brow_line_y - p[10, 1]))
    middle_third = abs(float(nose_base[1] - brow_line_y))
    thirds = np.asarray([upper_third, middle_third, lower_third], dtype=float)
    midline_x = float(np.mean([p[168, 0], p[1, 0], p[6, 0]]))
    sym = [
        float(np.linalg.norm([p[i, 0] + p[j, 0] - 2 * midline_x, p[i, 1] - p[j, 1]])) / (fw + EPS)
        for i, j in SYM_PAIRS
    ]
    z_baseline = float(np.mean([p[33, 2], p[263, 2], p[234, 2], p[454, 2]]))

    def arch(idx) -> float:
        bp = p[np.asarray(idx)]
        lo, hi = bp[int(np.argmin(bp[:, 0]))], bp[int(np.argmax(bp[:, 0]))]
        base = float((lo[1] + hi[1]) / 2)
        return _ratio(max(0.0, base - float(bp[:, 1].min())), fh)

    def slope(idx) -> float:
        bp = p[np.asarray(idx)]
        lo, hi = bp[int(np.argmin(bp[:, 0]))], bp[int(np.argmax(bp[:, 0]))]
        return float(math.degrees(math.atan2(hi[1] - lo[1], hi[0] - lo[0] + EPS)))

    def tilt(i: int, j: int) -> float:
        return float(math.degrees(math.atan2(p[j, 1] - p[i, 1], abs(p[j, 0] - p[i, 0]) + EPS)))

    aperture_l = 0.5 * (_ratio(d(159, 145), eye_w_l) + _ratio(d(158, 153), eye_w_l))
    aperture_r = 0.5 * (_ratio(d(386, 374), eye_w_r) + _ratio(d(385, 380), eye_w_r))

    out = {
        # — первые 20 гипотез —
        "facial_thirds_balance_cv_mp": _ratio(float(thirds.std()), float(thirds.mean())),
        "lower_to_upper_third_ratio_mp": _ratio(lower_third, upper_third),
        "inner_canthal_over_ipd_mp": _ratio(intercanthal, ipd),
        "mean_eye_width_over_ipd_mp": _ratio(mean_eye_w, ipd),
        "eye_width_asymmetry_over_mean_mp": _ratio(abs(eye_w_l - eye_w_r), mean_eye_w),
        "brow_arch_asymmetry_mp": abs(arch(BROW_L) - arch(BROW_R)),
        "brow_slope_asymmetry_deg_mp": abs(slope(BROW_L) - slope(BROW_R)),
        "nose_base_width_over_ipd_mp": _ratio(nose_w, ipd),
        "nose_base_to_mouth_width_ratio_mp": _ratio(nose_w, m_w),
        "nose_length_over_midface_height_mp": _ratio(nose_len_2d, abs(float(nose_base[1] - eye_line[1]))),
        "philtrum_length_over_face_height_mp": _ratio(abs(float(p[13, 1] - nose_base[1])), fh),
        "upper_lower_lip_thickness_ratio_mp": _ratio(abs(float(p[0, 1] - p[13, 1])), abs(float(p[17, 1] - p[14, 1]))),
        "outer_mouth_area_over_face_area_mp": _ratio(_polygon_area(p[LIP_OUTER]), fw * fh),
        "mouth_width_over_intercanthal_mp": _ratio(m_w, intercanthal),
        "mouth_corner_tilt_deg_mp": tilt(61, 291),
        "chin_width_over_lower_jaw_width_mp": _ratio(d(148, 377), lower_jaw_w),
        "cheek_depth_asymmetry_mp": _ratio(abs(float(p[234, 2] - p[454, 2])), fw),
        "eye_aperture_left_over_eye_width_mp": aperture_l,
        "eye_aperture_right_over_eye_width_mp": aperture_r,
        "facial_symmetry_rms_mp": float(np.sqrt(np.mean(np.square(sym)))),
        # — 20 заключительной итерации —
        "outer_canthal_span_over_ipd_mp": _ratio(g["palp_w"], ipd),
        "outer_canthal_span_over_cheek_width_mp": _ratio(g["palp_w"], fw),
        "brow_eye_gap_over_eye_width_mp": _ratio((brow_eye_l + brow_eye_r) / 2, mean_eye_w),
        "eye_fissure_tilt_mean_abs_deg_mp": 0.5 * (abs(tilt(133, 33)) + abs(tilt(362, 263))),
        "eye_fissure_tilt_asymmetry_deg_mp": abs(tilt(133, 33) - tilt(362, 263)),
        "nose_base_width_over_intercanthal_mp": _ratio(nose_w, intercanthal),
        "nose_base_width_over_nose_length_mp": _ratio(nose_w, nose_len_2d),
        "nose_base_tilt_abs_deg_mp": abs(tilt(98, 327)),
        "outer_mouth_area_over_width_squared_mp": _ratio(_polygon_area(p[LIP_OUTER]), m_w**2),
        "upper_lower_vermilion_area_ratio_mp": _ratio(_polygon_area(p[LIP_UPPER]), _polygon_area(p[LIP_LOWER])),
        "philtrum_length_over_mouth_width_mp": _ratio(abs(float(p[13, 1] - nose_base[1])), m_w),
        "mouth_to_chin_over_lower_third_mp": _ratio(abs(float(p[152, 1] - mouth_center[1])), lower_third),
        "lower_lip_to_chin_over_lower_third_mp": _ratio(abs(float(p[152, 1] - p[17, 1])), lower_third),
        "jaw_angle_asymmetry_deg_mp": abs(_angle(p[234], p[172], p[152]) - _angle(p[454], p[397], p[152])),
        "chin_width_over_mouth_width_mp": _ratio(d(148, 377), m_w),
        "nose_tip_protrusion_mp_over_cheek_width": _ratio(z_baseline - float(p[1, 2]), fw),
        "brow_height_asymmetry_over_face_height_mp": _ratio(abs(float(brow_l[1] - brow_r[1])), fh),
        "brow_eye_gap_asymmetry_over_face_height_mp": _ratio(abs(brow_eye_l - brow_eye_r), fh),
        "nose_midline_offset_over_cheek_width_mp": _ratio(abs(float(p[1, 0] - midline_x)), fw),
        "mouth_nose_horizontal_offset_over_cheek_width_mp": _ratio(
            abs(float(mouth_center[0] - nose_base[0])), fw
        ),
    }
    return out


def mp_probe(p: np.ndarray, scale: float) -> dict[str, float]:
    """21 метрика нашего MediaPipe-зонда (`mp_identity_probe.metrics`), те же определения."""

    def d2(i: int, j: int) -> float:
        return float(np.linalg.norm(p[i, :2] - p[j, :2]))

    def ang(i: int, v: int, j: int) -> float:
        return _angle(p[i], p[v], p[j])

    face_w = d2(234, 454)
    face_len = d2(10, 152)
    lower_w = d2(58, 288)
    ipd = d2(468, 473)
    m_w = d2(61, 291)
    ew_l, ew_r = d2(33, 133), d2(362, 263)
    eh_l, eh_r = d2(159, 145), d2(386, 374)
    nose_w, nose_len = d2(98, 327), d2(168, 2)
    return {
        "probe_face_w_over_face_len": _ratio(face_w, face_len),
        "probe_lower_w_over_face_w": _ratio(lower_w, face_w),
        "probe_zygomatic_flare": _ratio(face_w, lower_w),
        "probe_brow_span_over_face_w": _ratio(d2(70, 300), face_w),
        "probe_nose_w_over_mouth_w": _ratio(nose_w, m_w),
        "probe_nose_len_over_face_len": _ratio(nose_len, face_len),
        "probe_philtrum_over_face_len": _ratio(d2(2, 0), face_len),
        "probe_mouth_open_over_mouth_w": _ratio(d2(13, 14), m_w),
        "probe_midface_over_face_len": _ratio(d2(2, 152), face_len),
        "probe_eye_open_l": _ratio(eh_l, ew_l),
        "probe_eye_open_r": _ratio(eh_r, ew_r),
        "probe_eye_w_asym": _ratio(abs(ew_l - ew_r), (ew_l + ew_r) / 2),
        "probe_eye_h_asym": _ratio(abs(eh_l - eh_r), (eh_l + eh_r) / 2),
        "probe_brow_thk_l": _ratio(d2(65, 105), scale),
        "probe_brow_thk_r": _ratio(d2(293, 334), scale),
        "probe_nose_tip_to_base_over_len": _ratio(d2(2, 1), nose_len),
        "probe_jaw_contour_angle": 0.5 * (ang(234, 58, 152) + ang(454, 288, 152)),
        "probe_chin_angle": ang(58, 152, 288),
        "probe_ipd_over_face_w": _ratio(ipd, face_w),
        "probe_lip_thick_over_mouth_w": _ratio(d2(0, 17), m_w),
        "probe_mouth_w_over_face_w": _ratio(m_w, face_w),
    }


# ── 3DDFA: 134-набор ─────────────────────────────────────────────────────────
# Что 134 даёт такого, чего нет в 106 (раскладка снята с segmentation-каналов и
# средней формы, `app9/validation/ldm134_layout.py`):
#
#   0..21    веко глаза при x<0: 0..10 нижний край, 11..21 верхний (по 11 точек,
#            идут от наружного уголка к внутреннему)
#   22..43   веко глаза при x>0: 22..32 нижний, 33..43 верхний
#   44..56   бровь при x<0: 44..50 верхний ряд (7), 51..56 нижний (6)
#   57..69   бровь при x>0: 57..63 верхний ряд (7), 64..69 нижний (6)
#   70, 86   уголки рта (совпадают с 106#84 и 106#90)
#   71..85   кожная граница верхней губы (15),  88..102 её же слизистая (15)
#   104..118 слизистая нижней губы (15),        119..133 кожная граница (15)
#   87, 103  точки линии смыкания у уголков
#
# Чего в 134 НЕТ (и поэтому часть идей из «95+» переименована/переписана честно):
# костного края орбиты и глазного яблока — BFM его не моделирует. Всё, что раньше
# называлось «orbital rim / globe», меряется по краю глазной щели и по базисам
# `refs` (скула, глабелла), и это отражено в описаниях `describe`.
E_LID_LO = (list(range(0, 11)), list(range(22, 33)))      # нижнее веко: x<0, x>0
E_LID_UP = (list(range(11, 22)), list(range(33, 44)))     # верхнее веко
B_ROW_UP = (list(range(44, 51)), list(range(57, 64)))     # верхний ряд брови
B_ROW_LO = (list(range(51, 57)), list(range(64, 70)))     # нижний ряд брови
L_CORNER = (70, 86)                                       # уголки рта: x<0, x>0
L_UP_SKIN = list(range(71, 86))       # кожная граница верхней губы
L_UP_WET = list(range(88, 103))       # слизистая (линия смыкания) сверху
L_LO_WET = list(range(104, 119))      # слизистая снизу
L_LO_SKIN = list(range(119, 134))     # кожная граница нижней губы
L_SIDE = (87, 103)                    # «клычки» линии смыкания у уголков

#: Индексы вершин BFM для точек-базисов, которых нет в разметках. Получены из
#: средней формы (`ldm134_layout.anatomy`): топология фиксирована, поэтому номер
#: вершины — то же анатомическое место на любом лице.
ANAT_VERTS = (1994, 14357, 5350, 11009, 7855, 8575, 29891, 7883, 33827)
ANAT_KEYS = ("zygion_l", "zygion_r", "cheek_l", "cheek_r", "philtrum_l", "philtrum_r",
             "glabella", "mentolabial", "pogonion")
ZYG_L, ZYG_R, CHEEK_L, CHEEK_R, PHIL_L, PHIL_R, GLABELLA, MENTOLABIAL, POGONION = range(9)


def _poly_area(pts: np.ndarray) -> float:
    """Площадь плоского многоугольника по 3D-точкам (метод Ньюэлла, порядок важен)."""
    p = np.asarray(pts, dtype=float)
    if p.shape[0] < 3:
        return float("nan")
    nxt = np.roll(p, -1, axis=0)
    cr = np.cross(p, nxt)
    return float(np.linalg.norm(cr.sum(axis=0)) / 2.0)


def _arc_len(pts: np.ndarray) -> float:
    """Длина ломаной в 3D (контур не замыкаем)."""
    p = np.asarray(pts, dtype=float)
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) if p.shape[0] > 1 else float("nan")


def _chord(p: np.ndarray) -> float:
    return float(np.linalg.norm(p[-1] - p[0]))


def _chord_vec(p: np.ndarray) -> np.ndarray:
    """Вектор хорды «первая точка → последняя» (для проекций вдоль дуги)."""
    return np.asarray(p, dtype=float)[-1] - np.asarray(p, dtype=float)[0]


def _bow(pts: np.ndarray) -> float:
    """Среднее расстояние средних точек от хорды «первая → последняя», в единицах длины.

    Это «форма» контура: кривизна, провал, выпуклость — всё одна величина, только
    берём медиану, чтобы одна выбитая точка не делала признак шумовым.
    """
    p = np.asarray(pts, dtype=float)
    rv = p[-1] - p[0]
    den = float(np.dot(rv, rv))
    if p.shape[0] < 3 or den < EPS:
        return float("nan")
    t = ((p - p[0]) @ rv) / den
    dev = np.linalg.norm(p - (p[0] + np.clip(t, 0.0, 1.0)[:, None] * rv), axis=1)
    return float(np.median(dev[1:-1]))


def _plane(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Плоскость по точкам (НКА): (центроид, единичная нормаль с z >= 0).

    Трёх точек НКА не даёт: три точки — это ранг 2, и `s[2]` у них ровно ноль. Для
    базы по глубине (`refs`: глабелла + обе скулы) как раз три точки, поэтому для
    них отдельная ветка — нормаль через векторное произведение.
    """
    p = np.asarray(pts, dtype=float)
    if p.shape[0] < 3:
        return None
    c = p.mean(axis=0)
    if p.shape[0] == 3:
        n = np.cross(p[1] - p[0], p[2] - p[0])
        if float(np.linalg.norm(n)) < 1e-9:      # три точки на одной прямой
            return None
        n = n / float(np.linalg.norm(n))
    else:
        _, s, vt = np.linalg.svd(p - c, full_matrices=False)
        if s[2] <= 1e-6 * max(s[0], EPS):        # точки почти на одной прямой — плоскость фиктивна
            return None
        n = vt[2]
    return c, (n if n[2] >= 0 else -n)


def _dev_from_plane(pts: np.ndarray, base: np.ndarray) -> float:
    """Медианное знаковое отклонение точек от плоскости базы, в единицах длины."""
    pl = _plane(base)
    if pl is None:
        return float("nan")
    c, n = pl
    return float(np.median((np.asarray(pts, float) - c) @ n))


def _tilt_to_frontal(pts: np.ndarray) -> float:
    """Угол (градусы) нормали плоскости точек к фронтальной плоскости лица (0 = ровная)."""
    pl = _plane(pts)
    if pl is None:
        return float("nan")
    cos = float(np.clip(abs(float(np.dot(pl[1], np.array([0.0, 0.0, 1.0])))), 0.0, 1.0))
    return float(math.degrees(math.acos(cos)))


def _eye_frame(p: np.ndarray, k: int) -> dict[str, np.ndarray]:
    """Каркас одной глазной щели: уголки, контур целиком, вертикальные «мерки»."""
    lo, up = p[E_LID_LO[k]], p[E_LID_UP[k]]
    lat = (lo[0] + up[0]) / 2.0          # наружный уголок: начала обеих дуг
    med = (lo[-1] + up[-1]) / 2.0        # внутренний уголок: их концы
    return {"lo": lo, "up": up, "lat": lat, "med": med,
            "loop": np.vstack([up, lo[::-1]]),
            "axis": med - lat}


def _fissure_height(fr: dict[str, np.ndarray]) -> float:
    """Высота щели: средняя дистанция верхнего края до нижнего в 3D.

    Точки лежат на двух дугах одной щели и обходятся без перемаркировки, поэтому
    «вертикаль» считаем просто попарным расстоянием i-й точки верхнего ряда к i-й
    точке нижнего — на анфасе это и есть высота, а на подфронте деградирует плавно.
    """
    return float(np.linalg.norm(fr["up"] - fr["lo"], axis=1).mean())


# ── 134: глаза (по краю глазной щели + базисы) ───────────────────────────────
def ldm134_eyes(p: np.ndarray, q: np.ndarray, r: np.ndarray) -> dict[str, float]:
    """Глубина и форма век. Глазного яблока и края орбиты в BFM нет — базой служит
    плоскость «глабелла + обе скулы», она же отсчёт для «провала» глазницы."""
    face_w = _d(r, ZYG_L, ZYG_R)
    base = r[[GLABELLA, CHEEK_L, CHEEK_R]]
    ipd = _d(q, L_PUPIL, R_PUPIL)
    m_w = _d(q, MOUTH_L, MOUTH_R)
    fr = [_eye_frame(p, k) for k in (0, 1)]
    out: dict[str, float] = {}
    for k, side in ((0, "l"), (1, "r")):
        f = fr[k]
        out[f"lid_depth_vs_orbit_plane_{side}_134"] = _ratio(
            _dev_from_plane(np.vstack([f["lo"], f["up"]]), base), face_w)
        out[f"fissure_height_{side}_134"] = _ratio(_fissure_height(f), ipd)
        out[f"fissure_width_{side}_134"] = _ratio(float(np.linalg.norm(f["axis"])), ipd)
        out[f"fissure_area_{side}_134"] = _ratio(_poly_area(f["loop"]), ipd**2)
        out[f"lid_bow_upper_{side}_134"] = _ratio(_bow(f["up"]), _chord(f["up"]))
        out[f"lid_bow_lower_{side}_134"] = _ratio(_bow(f["lo"]), _chord(f["lo"]))
        out[f"lid_arc_upper_to_lower_{side}_134"] = _ratio(_arc_len(f["up"]), _arc_len(f["lo"]))
        out[f"lid_contour_tilt_{side}_134_deg"] = _tilt_to_frontal(f["loop"])
        out[f"infraorbital_steepness_{side}_134"] = _ratio(
            abs(float(f["lo"][0, 2] - f["lo"][len(f["lo"]) // 2, 2])), _chord(f["lo"]))
        out[f"lateral_canthus_relief_{side}_134"] = _ratio(
            float(f["lat"][2] - np.mean(np.vstack([f["lo"], f["up"]])[:, 2])), face_w)
        out[f"brow_lid_clearance_{side}_134"] = _ratio(
            float(np.linalg.norm(_c(p, B_ROW_LO[k]) - (f["lo"] + f["up"]).mean(0))), face_w)
        out[f"lid_margin_depth_spread_{side}_134"] = _ratio(
            float(np.std(np.vstack([f["lo"], f["up"]])[:, 2])), ipd)
        out[f"fissure_axis_incline_{side}_134_deg"] = _axis_incline(f["axis"])
    out["intercanthal_depth_saddle_134"] = _saddle(p, q, face_w)
    out["medial_canthus_vs_alar_depth_134"] = _ratio(
        float(np.mean([f["med"][2] for f in fr]) - np.mean([q[ALAR_L, 2], q[ALAR_R, 2]])), m_w)
    out["orbit_fissure_over_cheek_span_134"] = _ratio(
        float(np.mean([_poly_area(f["loop"]) for f in fr])) ** 0.5, face_w)
    out["fissure_axis_asym_deg_134"] = abs(
        out["fissure_axis_incline_l_134_deg"] - out["fissure_axis_incline_r_134_deg"])
    # Дуга брови к дуге щели: форма верхнего рельефа относительно нижней. Контур
    # брови — это верхний ряд, затем в обратную сторону нижний (получается «лепесток»).
    out["brow_arc_to_lid_arc_ratio_134"] = _ratio(
        float(np.mean([_arc_len(np.vstack([p[B_ROW_UP[k]], p[B_ROW_LO[k]][::-1]]))
                       for k in (0, 1)])),
        float(np.mean([_arc_len(f["up"]) + _arc_len(f["lo"]) for f in fr])))
    return out


def _axis_incline(axis: np.ndarray) -> float:
    """Наклон оси щели к фронтальной плоскости: насколько уголки разные по глубине."""
    lat_len = float(np.linalg.norm(axis[:2]))
    if lat_len < EPS:
        return float("nan")
    return float(math.degrees(math.atan2(abs(float(axis[2])), lat_len)))


def _saddle(p: np.ndarray, q: np.ndarray, face_w: float) -> float:
    """«Седло» между орбитами: насколько переносица отстоит назад от средней
    глубины всей области обеих щелей (44 точки края)."""
    z = float(np.mean([pt[2] for k in (0, 1)
                       for pt in np.vstack([p[E_LID_LO[k]], p[E_LID_UP[k]]])]))
    return _ratio(float(q[NASION, 2]) - z, face_w)


# ── 134: брови (двойной ряд точек — то, чего в 106 нет) ──────────────────────
# Порядок точек ряда: индекс 0 — ЛАТЕРАЛЬНЫЙ конец (хвост, |x| максимальный),
# последний индекс — МЕДИАЛЬНЫЙ (голова брови у переносицы). Так же устроены ряды
# век: 0 — наружный уголок. Проверено по знаку x на средней форме.
def ldm134_brows(p: np.ndarray, q: np.ndarray, r: np.ndarray) -> dict[str, float]:
    """Форма и рельеф надбровья. Каждый ряд (верхний/нижний) — отдельная дуга,
    между ними «толщина» дуги; база по глубине — глабелла и обе скулы."""
    face_w = _d(r, ZYG_L, ZYG_R)
    ipd = _d(q, L_PUPIL, R_PUPIL)
    base = r[[GLABELLA, CHEEK_L, CHEEK_R]]
    out: dict[str, float] = {}
    for k, side in ((0, "l"), (1, "r")):
        up, lo = p[B_ROW_UP[k]], p[B_ROW_LO[k]]
        arc = np.vstack([up, lo[::-1]])
        # Пары «верхний↔нижний ряд»: у верхнего ряда первая точка — хвост, ей
        # соответствия в нижнем ряду нет, поэтому сдвигаем на одну.
        pairs = np.linalg.norm(up[1:len(lo) + 1] - lo, axis=1)
        out[f"brow_double_row_offset_{side}_134"] = _ratio(float(pairs.mean()), ipd)
        out[f"brow_ridge_depth_{side}_134"] = _ratio(_dev_from_plane(arc, base), face_w)
        out[f"brow_arc_3d_curvature_{side}_134"] = _ratio(_bow(up), _chord(up))
        # «Лепесток» (верхний ряд туда, нижний обратно) — замкнутая петля, её собственная
        # хорда вырождается (начало и конец — соседние точки у хвоста), поэтому делим на
        # удвоенный размах ряда: 1 = две совпадающие дуги, больше — заметная «толщина».
        out[f"brow_length_over_chord_{side}_134"] = _ratio(_arc_len(arc), 2.0 * _chord(up))
        out[f"supraorbital_peak_position_{side}_134"] = _arc_apex_position(up)
        out[f"supraorbital_notch_{side}_134"] = _notch(up)
        out[f"brow_endpoints_depth_drop_{side}_134"] = _ratio(
            abs(float(up[0, 2] - up[-1, 2])), _chord(up))
        out[f"brow_medial_to_glabella_relief_{side}_134"] = _ratio(
            float(up[-1, 2] - r[GLABELLA][2]), face_w)
        out[f"brow_lateral_relief_over_lid_{side}_134"] = _ratio(
            float(up[0, 2] - np.mean(np.vstack([p[E_LID_LO[k]], p[E_LID_UP[k]]])[:, 2])), face_w)
        out[f"brow_chord_frontal_tilt_{side}_134_deg"] = _line_frontal_angle(up[-1] - up[0])
        # Плоскость «лепестка» (два ряда брови) стабильна: разброс по z больше, чем по y,
        # нормаль держится около [±0.4, 0, 0.9] и на двух почти одинаковых кадрах
        # расходится на 0.2°. Та же формула на ленте губ ломалась — см. lip_column_pitch.
        out[f"brow_plane_tilt_{side}_134_deg"] = _tilt_to_frontal(arc)
        out[f"brow_depth_spread_{side}_134"] = _ratio(float(np.std(arc[:, 2])), ipd)
        out[f"brow_sagittal_end_position_{side}_134"] = _ratio(
            abs(float(up[-1, 0])), abs(float(up[0, 0]) - float(up[-1, 0])))
    out["glabella_brow_convergence_deg_134"] = _convergence(p, r)
    out["brow_arc_torsion_deg_134"] = abs(
        out["brow_plane_tilt_l_134_deg"] - out["brow_plane_tilt_r_134_deg"])
    out["brow_tangent_parallelism_deg_134"] = _tangent_parallelism(p)
    rows = np.vstack([p[B_ROW_UP[k]] for k in (0, 1)])
    roots = np.array([p[B_ROW_UP[k]][-1] for k in (0, 1)])
    out["medial_brow_root_setback_134"] = _ratio(
        float(rows[:, 2].mean() - roots[:, 2].mean()), face_w)
    # «Плоскость» лба между дугами: насколько глабелла отстоит назад от средних
    # глубин обеих дуг — в единицах разброса глубин самих дуг.
    arcs = np.vstack([np.vstack([p[B_ROW_UP[k]], p[B_ROW_LO[k]]]) for k in (0, 1)])
    out["glabella_flatness_index_134"] = _ratio(
        abs(float(np.median(arcs[:, 2]) - r[GLABELLA][2])), float(np.std(arcs[:, 2])))
    return out


def _notch(pts: np.ndarray) -> float:
    """Локальный провал края: насколько самая «утопленная» точка отстоит от плавной
    дуги глубже остальных, в долях хорды. Отклонение — вдоль нормали плоскости дуги,
    знак приводим к тому, чтобы медиана была положительной (то есть «наружу»)."""
    rv = _chord_vec(pts)
    den = float(np.dot(rv, rv))
    pl = _plane(pts)
    if pts.shape[0] < 4 or den < EPS or pl is None:
        return float("nan")
    t = np.clip(((pts - pts[0]) @ rv) / den, 0.0, 1.0)
    perp = (pts - (pts[0] + t[:, None] * rv)) @ pl[1]
    if float(np.median(perp)) < 0:
        perp = -perp
    return _ratio(float(np.median(perp) - perp.min()), float(np.sqrt(den)))



# ── 134: губы (двойной контур — кожная граница и слизистая) ───────────────────
def ldm134_lips(p: np.ndarray, q: np.ndarray, r: np.ndarray) -> dict[str, float]:
    """Рельеф и форма губ. 106 даёт один периметр рта, 134 — четыре границы:
    кожную и слизистую у каждой губы. Из них и собираются «толщина», «отворот
    каймы», «скрученность линии смыкания» — то, чего на 106 построить нельзя."""
    face_w = _d(r, ZYG_L, ZYG_R)
    m_w = _d(p, L_CORNER[0], L_CORNER[1])
    base = r[[GLABELLA, ZYG_L, ZYG_R]]
    corner_l, corner_r = p[L_CORNER[0]], p[L_CORNER[1]]
    up_skin, up_wet = p[L_UP_SKIN], p[L_UP_WET]
    lo_wet, lo_skin = p[L_LO_WET], p[L_LO_SKIN]
    wet_line = np.vstack([up_wet, lo_wet[::-1], p[list(L_SIDE)]])
    lip_c = wet_line.mean(0)
    # Профильная выпуклость губ относительно той же базы, что у лидера списка:
    # хорда «брови → подбородок», отсчёт по глубине на уровне губ.
    brow_c = np.vstack([np.vstack([p[B_ROW_UP[k]], p[B_ROW_LO[k]]]) for k in (0, 1)]).mean(0)
    chin = q[CHIN]
    vert = chin - brow_c
    vert = vert / (np.linalg.norm(vert) + EPS)
    face_h = float(np.linalg.norm(chin - brow_c))
    t_lip = float(np.dot(lip_c - brow_c, vert)) / (face_h + EPS)
    line_z = float(brow_c[2] + t_lip * (chin[2] - brow_c[2]))
    out: dict[str, float] = {
        "lip_profile_convexity_134": _ratio(line_z - float(lip_c[2]), face_w),
        "chin_lip_protrusion_ratio_134": _ratio(
            _dev_from_plane(wet_line, base), _dev_from_plane(np.vstack([r[[POGONION]]]), base)),
        "vermilion_protrusion_upper_vs_lower_134": _ratio(
            _dev_from_plane(np.vstack([up_skin, up_wet]), base),
            _dev_from_plane(np.vstack([lo_skin, lo_wet]), base)),
        "mouth_corner_setback_over_width_134": _ratio(
            float(lip_c[2] - np.mean([corner_l[2], corner_r[2]])), m_w),
        "mouth_corner_depth_gradient_134": _ratio(float(np.mean(
            [abs(float(c[2] - lip_c[2])) for c in (corner_l, corner_r)])), m_w),
        "vermilion_eversion_upper_134": _ratio(
            float(np.median(up_wet[:, 2] - up_skin[:len(up_wet), 2])), m_w),
        "vermilion_eversion_lower_134": _ratio(
            float(np.median(lo_wet[:, 2] - lo_skin[:len(lo_wet), 2])), m_w),
        "lip_vermilion_thickness_upper_134": _ratio(
            float(np.median(np.linalg.norm(up_skin[:len(up_wet)] - up_wet, axis=1))), m_w),
        "lip_vermilion_thickness_lower_134": _ratio(
            float(np.median(np.linalg.norm(lo_wet[:len(lo_skin)] - lo_skin, axis=1))), m_w),
        # Наклон «столбика» губ в профиле: вектор от середины кожной границы верхней
        # губы к середине нижней. Раньше тут была НКА-плоскость всех четырёх границ, но
        # полоса губ растянута по x и неглубока по y, поэтому собственная плоскость
        # такой ленты вырождается в горизонталь (нормаль уходит к ±y), и «наклон к
        # фронту» превращался в сравнение разбросов по z и y с прыжком на десятки
        # градусов между двумя почти одинаковыми кадрами (замерено: 67° и 74°).
        "lip_column_pitch_deg_134": _line_frontal_angle(
            lo_skin[len(lo_skin) // 2] - up_skin[len(up_skin) // 2]),
        "mouth_line_planarity_134": _plane_rms_over(wet_line, m_w),
        "mouth_contour_over_chord_ratio_134": _ratio(
            _arc_len(up_skin) + _arc_len(lo_skin), m_w),
        "wet_dry_border_length_ratio_134": _ratio(
            float(np.mean([_arc_len(up_wet), _arc_len(lo_wet)])),
            float(np.mean([_arc_len(up_skin), _arc_len(lo_skin)]))),
        "upper_lip_peak_position_134": _peak_position(up_skin),
        "lower_lip_peak_position_134": _peak_position(lo_skin),
        "philtrum_relief_134": _ratio(
            float(np.mean([r[PHIL_L][2], r[PHIL_R][2]]) - q[NOSE_BASE_MID][2]),
            abs(float(lip_c[1] - q[NOSE_BASE_MID][1]))),
        "philtrum_columns_depth_convergence_134": _ratio(
            float(np.mean([r[PHIL_L][2], r[PHIL_R][2]]) - q[NOSE_BASE_MID][2]),
            _d(r, PHIL_L, PHIL_R)),
        "ala_to_commissure_relief_134": _ratio(
            float(np.mean([q[ALAR_L][2], q[ALAR_R][2]]) - np.mean([corner_l[2], corner_r[2]])),
            m_w),
        "mentolabial_relief_3d_134": _ratio(
            float(r[POGONION][2] - r[MENTOLABIAL][2]),
            _d(r, MENTOLABIAL, POGONION)),
        "lower_lip_to_chin_convexity_134": _ratio(
            float(lo_skin[len(lo_skin) // 2][2]
                  - (r[MENTOLABIAL][2] + r[POGONION][2]) / 2.0),
            _d(r, MENTOLABIAL, POGONION)),
        "lip_border_undulation_134": _ratio(
            float(np.mean([_bow(up_skin), _bow(lo_skin)])), m_w),
    }
    # Луковичный изгиб: провал середины кожной границы верхней губы между её двумя
    # пиками. Берём окно из 7 точек вокруг средней (пики — соседи через 3).
    mid = len(up_skin) // 2
    window = up_skin[mid - 3:mid + 4]
    peaks = float(np.delete(window[:, 1], 3).max())
    out["cupid_bow_drop_134"] = _ratio(peaks - float(window[3][1]), m_w)
    out["cupid_bow_3d_angle_134"] = _angle(
        p[L_UP_SKIN][mid - 3], p[L_UP_SKIN][mid], p[L_UP_SKIN][mid + 3])
    return out


def _plane_rms_over(pts: np.ndarray, den: float) -> float:
    """Среднеквадратичное отклонение точек от их собственной плоскости, в долях `den`.

    Это «скрученность» линии: идеальная плоская линия даёт 0, торсионная — больше.
    """
    pl = _plane(pts)
    if pl is None or den < EPS:
        return float("nan")
    dev = (np.asarray(pts, float) - pl[0]) @ pl[1]
    return _ratio(float(np.sqrt((dev ** 2).mean())), den)



def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > EPS else np.array([np.nan, np.nan, np.nan])


def _peak_position(pts: np.ndarray) -> float:
    """Где вдоль дуги лежит её самая выступающая вперёд точка (0 = начало, 1 = конец)."""
    rv = _chord_vec(pts)
    den = float(np.dot(rv, rv))
    if den < EPS:
        return float("nan")
    t = ((pts - pts[0]) @ rv) / den
    i = int(np.argmax(pts[:, 2]))
    return float(np.clip(t[i], 0.0, 1.0))


def _arc_apex_position(pts: np.ndarray) -> float:
    """Где вдоль хорды лежит вершина дуги — точка с наибольшим перпендикулярным
    отступом от хорды (0 = начало, 1 = конец).

    Для бровей «выступание вперёд» не годится: самая глубокая по z точка ряда —
    всегда её медиальный конец у переносицы, то есть признак на всех лицах равен 1.
    Вершина именно ДУГИ (где бровка выгнута сильнее всего) устойчива.
    """
    p = np.asarray(pts, dtype=float)
    rv = _chord_vec(p)
    den = float(np.dot(rv, rv))
    if p.shape[0] < 4 or den < EPS:
        return float("nan")
    t = np.clip(((p - p[0]) @ rv) / den, 0.0, 1.0)
    dev = np.linalg.norm(p - (p[0] + t[:, None] * rv), axis=1)
    return float(t[int(np.argmax(dev[1:-1])) + 1])


def _line_frontal_angle(vec: np.ndarray) -> float:
    """Угол отрезка к фронтальной плоскости лица: 0 = отрезок лежит в ней."""
    lat = float(np.linalg.norm(vec[:2]))
    return float(math.degrees(math.atan2(abs(float(vec[2])), lat))) if lat > EPS else float("nan")


def _convergence(p: np.ndarray, r: np.ndarray) -> float:
    """Насколько медиальные концы бровей сходятся под переносицей: угол при глабелле
    между векторами к голове каждой брови, приведённый к отклонению от прямой (0 = концы
    и глабелла лежат на одной прямой, то есть брови «не сходятся» вовсе).
    Индекс -1 у ряда — голова брови у переносицы, 0 — хвост.

    Сам угол около 180° (концы бровей по разные стороны от переносицы), поэтому
    показываем дополнение: малое число = малое схождение, и читается без сюрприза.
    """
    return 180.0 - _angle(p[B_ROW_UP[0]][-1], r[GLABELLA], p[B_ROW_UP[1]][-1])


def _tangent_parallelism(p: np.ndarray) -> float:
    """Средняя угловая разница касательных дуги брови и верхнего края века:
    «повторяет ли бровка форму орбиты». Точки сопоставляются по параметру дуги,
    касательные — разностью соседей (по 5 средних точек на глаз)."""
    devs = []
    for k in (0, 1):
        brow, lid = p[B_ROW_UP[k]], p[E_LID_UP[k]]
        n = min(len(brow), len(lid))
        for i in range(1, n - 1):
            ub, ue = _unit(brow[i + 1] - brow[i - 1]), _unit(lid[i + 1] - lid[i - 1])
            if not (np.all(np.isfinite(ub)) and np.all(np.isfinite(ue))):
                continue
            devs.append(math.degrees(math.acos(float(np.clip(np.dot(ub, ue), -1.0, 1.0)))))
    return float(np.mean(devs)) if devs else float("nan")


# ── крест: радужка MediaPipe × глазная щель 3DDFA(ldm134) ─────────────────────
# Единая единица. Числа из двух каркасов несопоставимы по масштабам: у 3DDFA канон
# RMS-106, у MediaPipe — пиксели после снятия roll. Но и то, и другое делим на СВОЁ
# зрачковое расстояние (3DDFA: |q[104] − q[105]|, MediaPipe: d2(468, 473)) — величина
# анатомически одна и та же, поэтому отношение «радужка к щели» уже законно: размер
# радужки в IPD-долях (MP) делится на размер щели в IPD-долях (134). Это и есть
# заявленная связка «белок почти не видно», которую ни одним каркасом отдельно не
# померить: MediaPipe не даёт 3D-рельеф век, 3DMM не видит радужку.
#
# Соответствие сторон проверено по данным, а не по конвенциям API:
# `app9/validation/iris_fissure_pairing.py` (знаковая межглазовая асимметрия ширины
# коррелирует +0.68) — глаз при x<0 у 3DDFA это те же индексы MediaPipe, что 33/133,
# 159/145, 468. Ниже сторона `l` = (x<0, MP «a»), сторона `r` = (x>0, MP «b»).
MP_EYE = (
    # (внешний уголок, внутренний уголок, верх века, низ века, центр радужки,
    #  радужка: левый/правый/верхний/нижний края, середина брови)
    (33, 133, 159, 145, 468, 469, 471, 470, 472, 105),
    (263, 362, 386, 374, 473, 474, 476, 475, 477, 334),
)


def cross_iris_fissure(q3: np.ndarray, pmp: np.ndarray, p: np.ndarray,
                        r: np.ndarray) -> dict[str, float]:
    """Радужка (MediaPipe) против моделируемой глазной щели (ldm134).

    Единая безразмерная единица: длина из MediaPipe делится на MP-IPD, длина из 134 —
    на 3DDFA-IPD. Оба IPD — анатомически одно и то же расстояние, поэтому отношение
    «радужка к щели» законно, хотя сами сетки несопоставимы (пиксели против канона
    RMS-106). Ось y в MediaPipe направлена вниз, поэтому «просвет снизу» = y(нижнее
    веко) − y(нижний край радужки), а «просвет сверху» = y(верхний край радужки) −
    y(верхнее веко); оба положительны, когда белок виден.
    """
    ipd3 = _d(q3, L_PUPIL, R_PUPIL)
    ipd_mp = _dist2(pmp, 468, 473)
    fr = [_eye_frame(p, k) for k in (0, 1)]
    medial = np.array([f["med"] for f in fr])
    iris_d_h = 0.5 * (_dist2(pmp, MP_EYE[0][5], MP_EYE[0][6])
                      + _dist2(pmp, MP_EYE[1][5], MP_EYE[1][6])) / ipd_mp
    sides: dict[str, dict[str, float]] = {}
    for k, side in ((0, "l"), (1, "r")):
        out_c, in_c, up_lid, lo_lid, iris_c, ir_l, ir_r, ir_t, ir_b, brow = MP_EYE[k]
        d_h = _dist2(pmp, ir_l, ir_r) / ipd_mp
        d_v = _dist2(pmp, ir_t, ir_b) / ipd_mp
        mp_w = _dist2(pmp, out_c, in_c) / ipd_mp
        mp_h = _dist2(pmp, up_lid, lo_lid) / ipd_mp
        f = fr[k]
        m_w = float(np.linalg.norm(f["axis"])) / ipd3
        m_h = _fissure_height(f) / ipd3
        m_area = _poly_area(f["loop"]) / ipd3 ** 2
        sides[side] = {
            # размер радужки относительно моделируемой щели — «большой глаз на узкой
            # щели» в одной величине
            "iris_over_fissure_width": _ratio(d_h, m_w),
            "iris_over_fissure_height": _ratio(d_v, m_h),
            "iris_over_fissure_area": _ratio(math.pi / 4 * d_h * d_v, m_area),
            "iris_over_lid_bow": _ratio(d_v, _bow(f["up"]) / ipd3),
            # видимая щель (MP) против смоделированной (134): насколько 3DMM
            # недотягивывает/переборщит в раскрытии глаза этого лица
            "aperture_height_agreement": _ratio(mp_h, m_h),
            "aperture_area_agreement": _ratio(math.pi / 4 * mp_w * mp_h, m_area),
            "fissure_width_deficit": mp_w - m_w,
            # главный инсайт: сколько белка остаётся в щели после радужки
            "sclera_show": _ratio(mp_h - d_v, m_h),
            "sclera_band_lower": _ratio(float(pmp[lo_lid, 1] - pmp[ir_b, 1]) / ipd_mp, m_h),
            "sclera_band_upper": _ratio(float(pmp[ir_t, 1] - pmp[up_lid, 1]) / ipd_mp, m_h),
            "sclera_band_balance": _ratio(
                float(pmp[ir_t, 1] - pmp[up_lid, 1] - pmp[lo_lid, 1] + pmp[ir_b, 1]) / ipd_mp, m_h),
            # положение радужки в щели: насколько её «съедают» веко и смещение вбок
            "iris_clip_upper": _ratio(float(pmp[iris_c, 1] - pmp[up_lid, 1]) / ipd_mp, m_h),
            "iris_clip_lower": _ratio(float(pmp[lo_lid, 1] - pmp[iris_c, 1]) / ipd_mp, m_h),
            "iris_lateral_offset": _ratio(
                float(pmp[iris_c, 0] - 0.5 * (pmp[out_c, 0] + pmp[in_c, 0])) / ipd_mp, mp_w),
            # бровь–глаз из двух каркасов: MP-пролёт против 3D-зазора над веком
            "brow_eye_gap_ratio": _ratio(
                float(pmp[iris_c, 1] - pmp[brow, 1]) / ipd_mp,
                float(np.linalg.norm(_c(p, B_ROW_LO[k]) - (f["lo"] + f["up"]).mean(0))) / ipd3),
            # наклон линии щели: «косой глаз» по пикселям против наклонной оси щели по
            # сетке. Разница показывает, где расходятся видимый край века и смоделированный
            "fissure_tilt_disagreement_deg": abs(
                _planar_tilt(pmp[in_c, :2] - pmp[out_c, :2]) - _planar_tilt(f["axis"])),
        }
    out: dict[str, float] = {}
    for base in sides["l"]:
        for side in ("l", "r"):
            out[f"cross_{base}_{side}_x134mp"] = sides[side][base]
        # Среднее по обоим глазам: шум одного глаза (у MP он в разы больше, чем у 134)
        # здесь сокращается вдвое, а смысл остаётся «в среднем ли у лица радужка велика
        # для своей щели».
        out[f"cross_{base}_mean_x134mp"] = 0.5 * (sides["l"][base] + sides["r"][base])
    out["cross_iris_over_intercanthal_x134mp"] = _ratio(
        iris_d_h, float(np.linalg.norm(medial[0, :2] - medial[1, :2])) / ipd3)
    out["cross_iris_over_bizygomatic_x134mp"] = _ratio(iris_d_h, _d(r, ZYG_L, ZYG_R) / ipd3)
    out["cross_iris_over_alar_width_x134mp"] = _ratio(iris_d_h, _d(q3, ALAR_L, ALAR_R) / ipd3)
    return out


def _dist2(pts: np.ndarray, i: int, j: int) -> float:
    return float(np.hypot(*(pts[i, :2] - pts[j, :2])))


def _planar_tilt(vec: np.ndarray) -> float:
    """Наклон отрезка к горизонтали в ПЛОСКОСТИ КАДРА (не к фронтальной плоскости!),
    градусы в (−90, 90]. Знак x приводим к положительному, чтобы направление обхода
    (наружный уголок → внутренний) у двух глаз не меняло знак признака.

    Нужен именно плоскостной наклон: у MediaPipe это «насколько косая глазная щель»,
    и сравнивать надо с тем же, а не с `_axis_incline` (тот меряет разницу глубин
    уголков, то есть совсем другой угол).
    """
    dx, dy = float(vec[0]), float(vec[1])
    if dx < 0:
        dx, dy = -dx, -dy
    return float(math.degrees(math.atan2(dy, dx + EPS)))





# kind: ratio (безразмерная) | absolute (зависит от нормировки) | angle (градусы)
# expr: метрика физически зависит от выражения (открывание рта, прищур, улыбка)
SOURCES = {
    "form17": "morphing/backend/identity.form_vector",
    "ldm_top3d": "compute_all_metrics.py Top-30 (3DDFA)",
    "ldm_hypotheses": "analyze_faces.py (гипотезы _3ddfa)",
    "mp_top30": "compute_all_metrics.py Top-30 (MediaPipe)",
    "mp_hypotheses": "analyze_faces.py (гипотезы _mp)",
    "mp_probe": "app9/validation/mp_identity_probe.py",
    # Батч «90+»: идеи по ldm134 (веки/брови/губы) и кросс-идеи радужка × щель.
    "ldm134_eyes": "гипотезы по ldm134: край глазной щели (батч 90+)",
    "ldm134_brows": "гипотезы по ldm134: двойной ряд брови (батч 90+)",
    "ldm134_lips": "гипотезы по ldm134: кожная граница и слизистая губ (батч 90+)",
    "cross_iris_fissure": "кросс: радужка MediaPipe × щель ldm134 (батч 90+)",
}

ABSOLUTE_3DDFA = {"mouth_height_3d_ldm", "central_depth_contrast_ldm"}
#: Всё, что зависит от раскрытия глаз. У 3DMM-ветки (134) сетка identity-only, то есть
#: мимики в входе физически нет, поэтому флагов от 134-групп здесь нет намеренно —
#: возможную утечку выражения проверяет `rho_jawopen` в воронке, а не этот список.
#: Кросс-метрики помечаются целиком по префиксу (см. `meta`): в них радужка и просвет
#: берутся из MediaPipe, а они морганием и щурятся напрямую.
EXPRESSION_SENSITIVE = {
    # рот: открытие/высота губ, площадь губ, ширина рта при улыбке
    "mouth_aspect_ratio_3d", "alar_base_over_mouth_height_3d", "mouth_height_3d_ldm",
    "mouth_area_index_3d", "mouth_height_over_ridge_3d", "mouth_height_over_midface_3d",
    "nose_ridge_to_mouth_width_3d", "oral_to_nasal_planar_ratio_3d",
    "naso_orbital_expansion_3d", "central_depth_to_mouth_height_3d",
    "mouth_opening_over_mouth_width_mp", "lip_thick_over_mouth_w", "vermilion_to_chin_ratio",
    "cupids_bow_angle", "outer_mouth_area_over_face_area_mp",
    "outer_mouth_area_over_width_squared_mp", "upper_lower_vermilion_area_ratio_mp",
    "upper_lower_lip_thickness_ratio_mp", "philtrum_length_over_face_height_mp",
    "philtrum_length_over_mouth_width_mp", "mouth_corner_tilt_deg_mp",
    "mouth_to_chin_over_lower_third_mp", "lower_lip_to_chin_over_lower_third_mp",
    "mouth_w_over_face_w", "zygomatic_to_mouth_width_ratio",
    "interpupillary_to_mouth_ratio", "mouth_to_orbit_span_ratio",
    "mouth_width_to_lower_face_ratio", "nose_base_to_mouth_width_ratio_mp",
    "mouth_width_over_intercanthal_mp", "chin_width_over_mouth_width_mp",
    "probe_mouth_open_over_mouth_w", "probe_lip_thick_over_mouth_w",
    "probe_mouth_w_over_face_w", "probe_nose_w_over_mouth_w",
    "probe_philtrum_over_face_len", "probe_chin_angle", "probe_jaw_contour_angle",
    # глаза: прищур и моргание
    "palpebral_area_index", "palpebral_aspect_ratio", "eye_open_l", "eye_open_r",
    "probe_eye_open_l", "probe_eye_open_r", "eye_aperture_left_over_eye_width_mp",
    "eye_aperture_right_over_eye_width_mp", "eye_fissure_tilt_mean_abs_deg_mp",
    "eye_fissure_tilt_asymmetry_deg_mp", "brow_eye_gap_over_eye_width_mp",
    "brow_arch_asymmetry_mp", "brow_slope_asymmetry_deg_mp",
    "probe_brow_thk_l", "probe_brow_thk_r",
}
USES_Z = {
    "cheek_depth_asymmetry_mp", "nose_tip_protrusion_mp_over_cheek_width",
    "palpebral_to_bigonial_ratio", "mandibular_body_to_ramus_ratio",
    "nasal_bridge_convergence_angle", "cupids_bow_angle", "mentolabial_sulcus_ratio",
    "palpebral_area_index", "palpebral_aspect_ratio", "ipd_over_face_w",
    "interpupillary_to_mouth_ratio", "mouth_to_orbit_span_ratio",
    "zygomatic_to_palpebral_width_ratio", "mouth_width_to_lower_face_ratio",
    "lip_thick_over_mouth_w", "alar_to_interpupillary_ratio", "nasal_dorsal_index",
    "vermilion_to_chin_ratio", "mouth_w_over_face_w", "zygomatic_to_mouth_width_ratio",
}


GROUPS_3DDFA = (
    ("form17", SOURCES["form17"], form17),
    ("ldm_top3d", SOURCES["ldm_top3d"], ldm_top3d),
    ("ldm_hypotheses", SOURCES["ldm_hypotheses"], ldm_hypotheses),
)
GROUPS_MP = (
    ("mp_top30", SOURCES["mp_top30"], mp_top30),
    ("mp_hypotheses", SOURCES["mp_hypotheses"], mp_hypotheses),
)
#: 134-набор живёт в том же каноне, что и 106 (`v_aligned` — вся сетка, центр и RMS по
#: 106 точкам), поэтому боевая паритетность выравнивания на него распространяется сама.
#: Сигнатура 134-групп: (p — 134 точки, q — 106 точек, r — 9 точек-базисов ANAT_VERTS).
GROUPS_134 = (
    ("ldm134_eyes", SOURCES["ldm134_eyes"], ldm134_eyes),
    ("ldm134_brows", SOURCES["ldm134_brows"], ldm134_brows),
    ("ldm134_lips", SOURCES["ldm134_lips"], ldm134_lips),
)


def compute_all(q3: np.ndarray | None, pmp: np.ndarray | None, scale: float,
                q134: np.ndarray | None = None, refs: np.ndarray | None = None) -> dict[str, float]:
    """Полный набор кандидатов для одного фото: 3DDFA-ветка + MediaPipe-ветка + 134.

    `q134` (134, 3) и `refs` (9, 3) — те же канонические единицы RMS-106, только снятые
    с других индексов сетки; если их нет (кэш старого формата), 134-ветка просто
    отсутствует, а не подменяется нулями.
    """
    values: dict[str, float] = {}
    if q3 is not None:
        for _, _, fn in GROUPS_3DDFA:
            values.update(fn(q3))
    if pmp is not None:
        for _, _, fn in GROUPS_MP:
            values.update(fn(pmp))
        values.update(mp_probe(pmp, scale))
    if q3 is not None and q134 is not None and refs is not None:
        for _, _, fn in GROUPS_134:
            values.update(fn(q134, q3, refs))
        # Кросс-ветка требует оба каркаса: без MediaPipe радужку взять неоткуда.
        if pmp is not None:
            values.update(cross_iris_fissure(q3, pmp, q134, refs))
    for k, v in values.items():
        values[k] = float(v) if v is not None and math.isfinite(float(v)) else float("nan")
    return values


_META_CACHE: dict[str, dict[str, str]] | None = None


def _arc(a, b, bow: float, n: int) -> np.ndarray:
    """Дуга из `n` точек между `a` и `b` с перпендикулярным прогибом `bow` — только для
    заглушки, чтобы перечислить ключи метрик (см. `_probe_134`)."""
    t = np.linspace(0.0, 1.0, n)
    base = np.asarray(a, dtype=float) + t[:, None] * (np.asarray(b, float) - np.asarray(a, float))
    perp = np.array([-(b[1] - a[1]), b[0] - a[0], 0.0])
    norm = float(np.hypot(perp[0], perp[1])) or 1.0
    return base + (bow * np.sin(np.pi * t))[:, None] * (perp / norm)


def _probe_134() -> tuple[np.ndarray, np.ndarray]:
    """Скелет 134-сетки и девяти базисов — нужен ОДНОРАЗОВО, чтобы `_all_meta` перечислил
    имена новых метрик без переснятых фото. Геометрия грубая, но не вырожденная (дуги,
    две стороны, разная глубина), а координаты базисов сняты с средней формы BFM.
    Никаких числовых результатов из этого скелета не берётся."""
    p = np.zeros((134, 3))
    for k, s in ((0, -1.0), (1, 1.0)):
        p[E_LID_LO[k]] = _arc((s * 0.72, 0.50, 0.05), (s * 0.20, 0.54, 0.22), -0.03, 11)
        p[E_LID_UP[k]] = _arc((s * 0.72, 0.57, 0.05), (s * 0.20, 0.58, 0.22), 0.05, 11)
        p[B_ROW_UP[k]] = _arc((s * 0.62, 0.72, 0.00), (s * 0.13, 0.78, 0.30), 0.04, 7)
        p[B_ROW_LO[k]] = _arc((s * 0.60, 0.66, 0.02), (s * 0.14, 0.73, 0.28), 0.03, 6)
    corner = (0.30, -0.55, 0.35)
    p[L_CORNER[0]], p[L_CORNER[1]] = (-corner[0], corner[1], corner[2]), corner
    p[L_UP_SKIN] = _arc((-0.30, -0.55, 0.35), (0.30, -0.55, 0.35), 0.09, 15)
    p[L_UP_WET] = _arc((-0.30, -0.55, 0.35), (0.30, -0.55, 0.35), 0.04, 15)
    p[L_LO_WET] = _arc((-0.30, -0.55, 0.35), (0.30, -0.55, 0.35), -0.05, 15)
    p[L_LO_SKIN] = _arc((-0.30, -0.55, 0.35), (0.30, -0.55, 0.35), -0.11, 15)
    p[list(L_SIDE)] = [(-0.28, -0.50, 0.36), (0.28, -0.50, 0.36)]
    refs = np.array([
        (-0.778, 0.122, 0.069), (0.774, 0.177, 0.062),      # zygion l/r
        (-0.312, 0.084, 0.284), (0.313, 0.085, 0.277),      # anterior cheek l/r
        (-0.045, -0.368, 0.489), (0.045, -0.368, 0.489),    # philtrum columns l/r
        (-0.026, 0.888, 0.389),                             # glabella
        (-0.072, -0.764, 0.339), (0.003, -0.933, 0.382),    # mentolabial, pogonion
    ])
    return p, refs


def _all_meta() -> dict[str, dict[str, str]]:
    """Имя метрики -> (каркас, кто придумал). Строится вызовом групп на заглушке."""
    global _META_CACHE
    if _META_CACHE is None:
        from morphing.backend.identity import FEATURE_ORDER

        cache: dict[str, dict[str, str]] = {}

        def register(names, framework: str, source: str, group: str = "") -> None:
            for name in names:
                cache[name] = {"framework": framework, "source": source, "group": group}

        probe3 = np.zeros((106, 3))
        probe3[JAW_L] = (-1, 0, 0); probe3[JAW_R] = (1, 0, 0)
        probe3[CHIN] = (0, -1, 0); probe3[NASION] = (0, 1, 0)
        probe3[NOSE_TIP] = (0, 0.5, 1); probe3[UP_LIP_MID] = (0, -0.5, 0.5)
        probe3[LO_LIP_MID] = (0, -0.7, 0.5); probe3[MOUTH_L] = (-0.3, -0.6, 0.4)
        probe3[MOUTH_R] = (0.3, -0.6, 0.4)
        # Зрачки: без них IPD = 0 и все 134-отношения схлопываются в 0/eps — ключи-то
        # перечислятся, но проще задать скелету осмысленный масштаб сразу.
        probe3[L_PUPIL] = (-0.46, 0.55, 0.16); probe3[R_PUPIL] = (0.46, 0.55, 0.16)
        register(FEATURE_ORDER, "3ddfa", SOURCES["form17"], "form17")
        register(ldm_top3d(probe3), "3ddfa", SOURCES["ldm_top3d"], "ldm_top3d")
        register(ldm_hypotheses(probe3), "3ddfa", SOURCES["ldm_hypotheses"], "ldm_hypotheses")

        # Заглушка не должна быть вырожденной: на нулевых точках углы дают NaN, а
        # ключи словаря всё равно перечисляются — но удобнее задать живой скелет.
        probe2 = np.zeros((478, 3))
        probe2[234] = (-1, 0, 0); probe2[454] = (1, 0, 0)
        probe2[33] = (-0.5, 0.2, 0); probe2[133] = (-0.8, 0.2, 0)
        probe2[362] = (0.8, 0.2, 0); probe2[263] = (0.5, 0.2, 0)
        probe2[168] = (0, 0.5, 0); probe2[2] = (0, 0.1, 0.3); probe2[152] = (0, -1, 0)
        probe2[61] = (-0.3, -0.5, 0); probe2[291] = (0.3, -0.5, 0)
        probe2[0] = (0, -0.42, 0); probe2[17] = (0, -0.62, 0)
        probe2[13] = (0, -0.47, 0); probe2[14] = (0, -0.57, 0)
        probe2[468] = (-0.4, 0.2, 0.1); probe2[473] = (0.4, 0.2, 0.1)
        # Кольца радужек, века и середины бровей — чтобы кросс-ветка на заглушке не
        # делила на ноль (y в MediaPipe растёт вниз, поэтому «верх» — это меньший y).
        probe2[469] = (-0.5, 0.2, 0.1); probe2[471] = (-0.3, 0.2, 0.1)
        probe2[470] = (-0.4, 0.1, 0.1); probe2[472] = (-0.4, 0.3, 0.1)
        probe2[474] = (0.3, 0.2, 0.1); probe2[476] = (0.5, 0.2, 0.1)
        probe2[475] = (0.4, 0.1, 0.1); probe2[477] = (0.4, 0.3, 0.1)
        probe2[159] = (-0.65, 0.12, 0.0); probe2[145] = (-0.65, 0.28, 0.0)
        probe2[386] = (0.65, 0.12, 0.0); probe2[374] = (0.65, 0.28, 0.0)
        probe2[105] = (-0.4, 0.0, 0.0); probe2[334] = (0.4, 0.0, 0.0)
        register(mp_top30(probe2), "mediapipe", SOURCES["mp_top30"], "mp_top30")
        register(mp_hypotheses(probe2), "mediapipe", SOURCES["mp_hypotheses"], "mp_hypotheses")
        register(mp_probe(probe2, 1.0), "mediapipe", SOURCES["mp_probe"], "mp_probe")

        p134, probe_refs = _probe_134()
        for group, source, fn in GROUPS_134:
            register(fn(p134, probe3, probe_refs), "3ddfa", source, group)
        register(cross_iris_fissure(probe3, probe2, p134, probe_refs),
                 "cross", SOURCES["cross_iris_fissure"], "cross_iris_fissure")
        _META_CACHE = cache
    return _META_CACHE


def metric_sources() -> dict[str, str]:
    """Имя метрики -> кто её придумал (для отчётов)."""
    return {name: m["source"] for name, m in _all_meta().items()}


def metric_frameworks() -> dict[str, str]:
    """Имя метрики -> каркас: `3ddfa` | `mediapipe` | `cross`."""
    return {name: m["framework"] for name, m in _all_meta().items()}


def metric_groups() -> dict[str, str]:
    """Имя метрики -> группа-источник (`form17`, `ldm134_eyes`, `cross_iris_fissure`…).

    Нужна отчёту: «что из надуманного подтвердилось» — вопрос про группу, а не про
    отдельные формулы, и каркас на группы не разбивает (134-ветка тоже `3ddfa`).
    """
    return {name: m["group"] for name, m in _all_meta().items()}


def meta(name: str) -> dict[str, Any]:
    """Карточка метрики: каркас, группа, источник, тип величины, чувствительность к мимике и z."""
    known = _all_meta().get(name, {"framework": "unknown", "source": "?", "group": "?"})
    kind = "absolute" if name in ABSOLUTE_3DDFA else (
        "angle" if ("_deg" in name or "_angle" in name) else "ratio"
    )
    return {
        "framework": known["framework"],
        "source": known["source"],
        "group": known["group"],
        "kind": kind,
        # Кросс-ветка помечается целиком по префиксу: в ней и радужка, и просвет берутся
        # из MediaPipe, а это прямые следы мимики (моргание, прищур).
        "expression_sensitive": name in EXPRESSION_SENSITIVE or name.startswith("cross_"),
        "uses_z": name in USES_Z,
    }


# ── чем метрика «пахнет» словами ─────────────────────────────────────────────
# Список метрик утверждает человек, поэтому для лидеров ранжирования нужно описание
# формулы, а не только eta2. Покрываем тир A и заметных кандидатов из тира B; для
# остальных `describe` возвращает пустую строку — отчёт их просто не описывает.
DESCRIPTIONS = {
    # 3DDFA (сетка 106 точек после боевого выравнивания)
    "midface_profile_convexity_3ddfa":
        "отклонение кончика носа по глубине от хорды «центр бровей → подбородок», "
        "на ширину лица: профильная кривизна средней зоны",
    "chin_depth_projection_3ddfa":
        "глубина подбородка относительно ширины лица: проекция «центр губ → подбородок» "
        "по оси z / face_width",
    "chin_depth_to_nose_protrusion_ratio_3ddfa":
        "выраженность подбородка (по глубине) к выступанию носа относительно линии глаз",
    "naso_orbital_expansion_3d":
        "«пролёт» средней зоны (глаза + нос) к ширине рта",
    "nose_ridge_to_mouth_width_3d":
        "длина спинки носа (насион → кончик) к ширине рта",
    "mouth_aspect_ratio_3d":
        "высота рта к его ширине по 3D-сетке (определение про выражение)",
    "mouth_width_3d": "ширина рта (боевой признак)",
    "midface_ratio":
        "высота средней зоны (линия глаз → основание носа) к ширине между центрами глаз",
    "depth_contrast_over_brow_span_3d":
        "насколько кончик носа глубже уровня глаз, на ширину бровей",
    "nose_upperlip_chin_angle_3ddfa":
        "угол «кончик носа → центр губ → подбородок» в градусах (профильная гармония)",
    "alar_width_over_ridge_length_3ddfa": "ширина крыльев носа к длине спинки",
    # MediaPipe (478 точек после roll-правки, нормировка своя)
    "palpebral_to_bigonial_ratio":
        "разведение внешних уголков глаз к ширине углов нижней челюсти",
    "mouth_width_to_lower_face_ratio":
        "ширина рта к высоте нижней трети лица (определение про выражение)",
    "eye_aperture_right_over_eye_width_mp":
        "раскрытие правого глаза: средняя высота щели к её ширине (определение про "
        "мимику)",
    "palpebral_area_index":
        "площадь обеих глазных щелей к площади лица ×1000 (зависит от раскрытия глаз)",
    "nasal_bridge_convergence_angle":
        "угол схождения спинки носа: кончик — переносица — крыло (градусы)",
    "lower_lip_to_chin_over_lower_third_mp":
        "расстояние «нижняя губа → подбородок» к высоте нижней трети лица",
    "nasal_dorsal_index": "ширина крыльев носа к высоте средней трети лица",
    "mandibular_body_to_ramus_ratio":
        "средняя по двум сторонам «ветвь челюсти → подбородок» к «скула → ветвь»",
    "lip_thick_over_mouth_w": "полная толщина губ (верх + низ) к ширине рта",
    "probe_eye_open_l": "высота левой глазной щели к её ширине (раскрытие глаза)",
    "inner_canthal_over_ipd_mp":
        "расстояние между внутренними уголками глаз к зрачковому расстоянию",
    "probe_lower_w_over_face_w":
        "ширина нижней челюсти (58 ↔ 288) к ширине лица по скулам",
    "interpupillary_to_mouth_ratio": "зрачковое расстояние к ширине рта",
    "alar_to_interpupillary_ratio": "ширина крыльев носа к зрачковому расстоянию",
    "probe_ipd_over_face_w": "зрачковое расстояние к ширине лица по скулам",
    "zygomatic_to_palpebral_width_ratio":
        "ширина скул к разведению внешних уголков глаз",
    "probe_brow_span_over_face_w": "ширина бровей (70 ↔ 300) к ширине лица",
    "mean_eye_width_over_ipd_mp": "средняя ширина глазной щели к зрачковому расстоянию",
    # ── новое: ldm134 (веки, двойные ряды бровей, четыре границы губ) ──────────
    "brow_ridge_depth_l_134":
        "насколько левая дуга брови (оба ряда точек) выступает вперёд из базы "
        "«глабелла + обе скулы», на ширину лица",
    "brow_medial_to_glabella_relief_l_134":
        "разница глубин головы левой брови и глабеллы: «нависает» ли бровь над "
        "переносицей или лежит с ней в одной плоскости",
    "lateral_canthus_relief_r_134":
        "глубина наружного уголка правого глаза относительно средних глубин всех "
        "точек его века, на ширину лица",
    "lid_margin_depth_spread_r_134":
        "разброс глубин по всем точкам края правой глазной щели: насколько «объёмная» "
        "у глаза чаша (на зрачковое расстояние)",
    "orbit_fissure_over_cheek_span_134":
        "средняя площадь глазной щели (корень из неё) к ширине скул: «размер глаз "
        "относительно ширины лица»",
    "lip_profile_convexity_134":
        "насколько центр губ уходит вперёд относительно хорды «центр бровей → "
        "подбородок» на уровне губ (отрицательное = выступает), на ширину лица",
    "chin_lip_protrusion_ratio_134":
        "выступание красной каймы губ из базы «глабелла + скулы» к тому же выступанию "
        "подбородка (погониона): «губы против подбородка» в профиле",
    "mentolabial_relief_3d_134":
        "глубина губоподбородочной борозды в профиле: разница глубин погониона и "
        "борозды на расстояние между ними",
    "lip_vermilion_thickness_upper_134":
        "вертикальная толщина верхней красной каймы (медиана расстояний кожной границы "
        "до слизистой) к ширине рта",
    "lip_vermilion_thickness_lower_134":
        "то же для нижней губы: толщина слизистой от её границы до кожной",
    "wet_dry_border_length_ratio_134":
        "длина двух слизистых границ рта к длине двух кожных: «складчатость» каймы "
        "против растянутости кожи над/под губами",
    "lip_border_undulation_134":
        "средний прогиб кожных границ губ от их хорд («луковичный» изгиб верхней и "
        "изгиб нижней) к ширине рта",
    # ── новое: крест радужка(MediaPipe) × щель(ldm134) ─────────────────────────
    "cross_sclera_show_mean_x134mp":
        "сколько вертикального просвета (белка) остаётся в глазной щели после радужки: "
        "разница видимой высоты щели (MediaPipe, по своему IPD) и вертикального диаметра "
        "радужки, на высоту смоделированной щели (134, по своему IPD). Отрицательное = "
        "радужка больше щели, белок не виден — ровно заявленная разница put против "
        "vas/udmurt",
    "cross_sclera_band_lower_r_x134mp":
        "нижняя белковая полоса правого глаза: зазор от нижнего края радужки до нижнего "
        "века (MediaPipe, в долях MP-IPD) на высоту моделируемой щели (134, в долях "
        "3DDFA-IPD)",
}


def describe(name: str) -> str:
    """Человеческое описание формулы; пусто — если метрика не описана."""
    return DESCRIPTIONS.get(name, "")

