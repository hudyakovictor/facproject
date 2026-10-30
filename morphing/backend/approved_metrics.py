#!/usr/bin/env python
"""Утверждённый набор метрик (30) — единственный источник правды для прода.

Утверждён владельцем 27.10.2026 по итогам `metric_shortlist.py --n-perm 2000` на
257 фронтальных фото (put 150 / vas 76 / udmurt 31, нейтральных по мимике 204).
Воронка: 253 кандидата -> 240 без строгих дублей -> 188 без мягких -> 30 утверждено.

Здесь только имена, каркас и опорные числа с фронта. Определения живут в
`metric_registry.py`, человеческие описания — в `metric_registry.describe()`:
дублировать их тут значило бы расходиться с ними при первой же правке.

Числа (`eta2_neutral`, `auc_neutral`, `rho_jawopen`) — с нейтрального по мимике
подмножества. Нужны они затем, что проверка на подфронтальном ракурсе
(`subfrontal_check.py`) и вживление в прод сравнивают себя именно с ними:
«метрика подтвердилась» = не потеряла разделение и не изменила знак, когда фото
повёрнуто на 10–25°.
"""
from __future__ import annotations

from dataclasses import dataclass

# Каркасы: `3ddfa` — только боевая сетка; `mediapipe` — только MP-пиксели;
# `cross` — оба каркаса в одной величине (числитель MP, знаменатель ldm134).
FRAMEWORKS = ("3ddfa", "mediapipe", "cross")

# Группы кандидатов, из которых взято утверждённое.
GROUPS_134 = ("ldm134_eyes", "ldm134_brows", "ldm134_lips")


@dataclass(frozen=True)
class Approved:
    name: str
    framework: str
    group: str
    eta2_neutral: float
    auc_neutral: float
    rho_jawopen: float


APPROVED: tuple[Approved, ...] = (
    # --- 3DDFA: координаты сетки + ldm134 (16) ---
    Approved("midface_profile_convexity_3ddfa", "3ddfa", "ldm_hypotheses", 0.5923, 0.8315, -0.2714),
    Approved("lip_profile_convexity_134", "3ddfa", "ldm134_lips", 0.6732, 0.8326, -0.4424),
    Approved("brow_ridge_depth_l_134", "3ddfa", "ldm134_brows", 0.5818, 0.8527, -0.1663),
    Approved("chin_lip_protrusion_ratio_134", "3ddfa", "ldm134_lips", 0.5852, 0.8258, 0.4513),
    Approved("lip_vermilion_thickness_lower_134", "3ddfa", "ldm134_lips", 0.5361, 0.8796, 0.2520),
    Approved("wet_dry_border_length_ratio_134", "3ddfa", "ldm134_lips", 0.4923, 0.8799, -0.3506),
    Approved("mouth_aspect_ratio_3d", "3ddfa", "ldm_top3d", 0.5365, 0.8653, 0.2884),
    Approved("mentolabial_relief_3d_134", "3ddfa", "ldm134_lips", 0.5243, 0.8089, -0.4195),
    Approved("lip_vermilion_thickness_upper_134", "3ddfa", "ldm134_lips", 0.4513, 0.8017, 0.1978),
    Approved("lateral_canthus_relief_r_134", "3ddfa", "ldm134_eyes", 0.5532, 0.8092, -0.3630),
    Approved("lid_margin_depth_spread_r_134", "3ddfa", "ldm134_eyes", 0.5082, 0.8090, 0.2946),
    Approved("orbit_fissure_over_cheek_span_134", "3ddfa", "ldm134_eyes", 0.5075, 0.8858, 0.4480),
    Approved("brow_medial_to_glabella_relief_l_134", "3ddfa", "ldm134_brows", 0.4021, 0.8057, -0.0648),
    Approved("nose_ridge_to_mouth_width_3d", "3ddfa", "ldm_top3d", 0.3323, 0.8196, 0.4474),
    Approved("lip_border_undulation_134", "3ddfa", "ldm134_lips", 0.3654, 0.8106, 0.2019),
    Approved("naso_orbital_expansion_3d", "3ddfa", "ldm_top3d", 0.3566, 0.8558, 0.4526),
    # --- MediaPipe: 2D-пиксели + 468–477 (12) ---
    Approved("palpebral_to_bigonial_ratio", "mediapipe", "mp_top30", 0.4465, 0.8301, 0.2446),
    Approved("mouth_width_to_lower_face_ratio", "mediapipe", "mp_top30", 0.3771, 0.8117, -0.4506),
    Approved("eye_aperture_right_over_eye_width_mp", "mediapipe", "mp_hypotheses", 0.4142, 0.8807, 0.3118),
    Approved("palpebral_area_index", "mediapipe", "mp_top30", 0.4126, 0.8729, 0.3056),
    Approved("nasal_bridge_convergence_angle", "mediapipe", "mp_top30", 0.3892, 0.8683, -0.4477),
    Approved("lower_lip_to_chin_over_lower_third_mp", "mediapipe", "mp_hypotheses", 0.4198, 0.8695, -0.2893),
    Approved("nasal_dorsal_index", "mediapipe", "mp_top30", 0.4029, 0.8882, -0.3859),
    Approved("mandibular_body_to_ramus_ratio", "mediapipe", "mp_top30", 0.4110, 0.8686, -0.4739),
    Approved("lip_thick_over_mouth_w", "mediapipe", "mp_top30", 0.3759, 0.8297, 0.2802),
    Approved("probe_eye_open_l", "mediapipe", "mp_probe", 0.3480, 0.8369, 0.3830),
    Approved("inner_canthal_over_ipd_mp", "mediapipe", "mp_hypotheses", 0.3090, 0.8431, -0.1939),
    Approved("probe_lower_w_over_face_w", "mediapipe", "mp_probe", 0.3166, 0.8325, -0.2278),
    # --- Крест радужка(MP) × щель(ldm134) (2) ---
    Approved("cross_sclera_show_mean_x134mp", "cross", "cross_iris_fissure", 0.4437, 0.8642, 0.3579),
    Approved("cross_sclera_band_lower_r_x134mp", "cross", "cross_iris_fissure", 0.4374, 0.8699, 0.3364),
)

APPROVED_NAMES: tuple[str, ...] = tuple(a.name for a in APPROVED)
_BY_NAME: dict[str, Approved] = {a.name: a for a in APPROVED}

# Девять метрик, которые НЕ потеряли разделение на подфронтальном ракурсе
# (|yaw| 10–25°, separate прогон `app9/validation/subfrontal_check.py`, отчёт
# `app9/validation/report/subfrontal_check.md`, приговор «держится»: значимость на
# перестановочном нуле, AUC ≥ 0.80, eta2 ≥ 0.30, мимика не течёт, порядок личностей
# на месте, уровень ушёл не больше 1.5 MAD, слабый коррелят с самим поворотом).
# Все девять — из 3D-сетки; вся MediaPipe-ветка на повороте просела, потому что
# 2D-расстояния укорачиваются проекцией.
#
# В интерфейсе ячейки этих девяти жирнее остальных 21 при том же цвете: это НЕ
# «считать только их» — считаются и показываются все 30, просто эти девять
# переживают поворот.
POSE_STABLE: frozenset[str] = frozenset({
    "midface_profile_convexity_3ddfa",
    "lip_profile_convexity_134",
    "brow_ridge_depth_l_134",
    "chin_lip_protrusion_ratio_134",
    "lip_vermilion_thickness_lower_134",
    "wet_dry_border_length_ratio_134",
    "mouth_aspect_ratio_3d",
    "lateral_canthus_relief_r_134",
    "lid_margin_depth_spread_r_134",
})


def pose_stable(name: str) -> bool:
    """Метрика из девяти переживших поворот (см. POSE_STABLE)."""
    return name in POSE_STABLE


def approved(framework: str | None = None) -> tuple[Approved, ...]:
    """Утверждённые записи; `framework=None` — все."""
    return APPROVED if framework is None else tuple(a for a in APPROVED if a.framework == framework)


def requires_mediapipe(name: str) -> bool:
    """Нужен ли MediaPipe, чтобы посчитать метрику (касается и `cross`)."""
    return _BY_NAME[name].framework in ("mediapipe", "cross")


def framework(name: str) -> str:
    return _BY_NAME[name].framework


def group(name: str) -> str:
    return _BY_NAME[name].group


def requires_ldm134(name: str) -> bool:
    """Нужен ли расширенный набор ldm134 (или опорные vertices BFM) сверх таблицы ролей ldm106."""
    rec = _BY_NAME.get(name)
    if rec is None:
        return False
    return rec.group in GROUPS_134 or rec.framework == "cross"


def baseline(name: str) -> tuple[float, float, float]:
    """Опорные числа с фронта: (eta2_neutral, auc_neutral, rho_jawopen)."""
    rec = _BY_NAME[name]
    return rec.eta2_neutral, rec.auc_neutral, rec.rho_jawopen
