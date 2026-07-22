"""⚠️ NOT WIRED (AUDIT-5): модуль НЕ импортируется ничем в продакшн-путях и тестах —
471 строка кандидат-реализации атласа v3, которая так и не была подключена.
Актуальный live-путь атласа: stage1/skin/projection.py (rasterize_surface/project_atlas)
+ генерация канонических слоёв: skin_zone_atlas.py (legacy) через scripts/render_skin_zone_atlas.py.
🚪 API (если будет подключён): validate_definitions(), build_primary_triangle_zone(),
  project_atlas_to_photo(), export_contract(), load_canonical_atlas()
🔗 DEPENDS ON: assets face_model + mask_atlas npz (внешний ассет, отсутствует в гите)
📊 METRIC: zone_role_for_pose() — роль зоны по pose bin (аппликабельность в stage2)
💡 NOTE: не удалять — задел под skin v3 (см. test_skin_v3_foundation, test_wrinkle_zones).
"""
from __future__ import annotations

"""Canonical anatomical skin atlas v4 (40 zones).

This version follows the detailed 40-zone anatomical layout: forehead thirds,
temples, glabella, full nose sub-regions, eyelids, infraorbital, zygomatic,
cheeks, nasolabial folds, perioral skin, lips, chin and jawline.

Design principles (same as v3, extended):
- One primary label per mesh triangle inside the face support.
- Zones are placed by anatomically symmetric UV seeds and grown by an
  anisotropic nearest-seed partition, so the map is complete and non-overlapping.
- Small anatomical structures (columella, alae, mouth corners, eyelids, lips)
  are allowed to be small; a `small_ok` flag marks them so QA does not penalize.
- Lips and eye openings may receive a label here, but the per-photo working mask
  always intersects with the skin segmentation mask, so real lips/eyes/brows are
  removed downstream. Analysis always runs on original photo pixels.

UV convention: u=0 left of image, u=1 right; v=1 forehead/top, v=0 jaw/bottom.
"""

import colorsys
import json
import logging
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)
import logging
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import logging
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

ATLAS_VERSION = "skin-zone-atlas-v4.0"
UV_ORIENTATION = "u=0 left; u=0.5 center; u=1 right; v=1 forehead; v=0 jaw"
PRIMARY_POLICY = "one_label_per_triangle_inside_face_support"

POSE_BINS = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)

Side = Literal["left", "right", "midline"]
Group = Literal[
    "forehead", "temple", "glabella", "nose", "eyelid", "infraorbital",
    "zygomatic", "cheek", "nasolabial", "perioral", "lip", "chin", "jaw",
]


@dataclass(frozen=True)
class Zone:
    num: int
    zone_id: str
    name: str
    label_ru: str
    side: Side
    group: Group
    seed_uv: tuple[float, float]
    scale_uv: tuple[float, float]
    bonus: float = 0.0          # additive win bias for small central structures
    small_ok: bool = False      # exempt from min-area QA
    excluded_by_segmentation: bool = False  # lips/eye openings removed per photo
    pair: str | None = None
    notes: str = ""


# 40 anatomically symmetric zones (center u=0.5; *_left has u<0.5).
ZONES: tuple[Zone, ...] = (
    Zone(1,  "Z01", "forehead_center",     "лоб центр",              "midline", "forehead",   (0.50,0.86), (0.16,0.095)),
    Zone(2,  "Z02", "forehead_left",       "лоб левый",              "left",    "forehead",   (0.29,0.86), (0.15,0.095), pair="forehead_right"),
    Zone(3,  "Z03", "forehead_right",      "лоб правый",             "right",   "forehead",   (0.71,0.86), (0.15,0.095), pair="forehead_left"),
    Zone(4,  "Z04", "temple_left",         "висок левый",            "left",    "temple",     (0.11,0.77), (0.10,0.15),  pair="temple_right"),
    Zone(5,  "Z05", "temple_right",        "висок правый",           "right",   "temple",     (0.89,0.77), (0.10,0.15),  pair="temple_left"),
    Zone(6,  "Z06", "glabella",            "межбровье",             "midline", "glabella",   (0.50,0.715),(0.065,0.05), bonus=0.03),
    Zone(7,  "Z07", "nasion",              "переносица",            "midline", "nose",       (0.50,0.655),(0.05,0.045), bonus=0.03),
    Zone(8,  "Z08", "nose_dorsum",         "спинка носа",           "midline", "nose",       (0.50,0.575),(0.05,0.065), bonus=0.02),
    Zone(9,  "Z09", "nose_tip",            "кончик носа",           "midline", "nose",       (0.50,0.505),(0.055,0.05), bonus=0.03, small_ok=True),
    Zone(10, "Z10", "ala_left",            "крыло носа левое",      "left",    "nose",       (0.425,0.49),(0.038,0.04), bonus=0.04, small_ok=True, pair="ala_right"),
    Zone(11, "Z11", "ala_right",           "крыло носа правое",     "right",   "nose",       (0.575,0.49),(0.038,0.04), bonus=0.04, small_ok=True, pair="ala_left"),
    Zone(12, "Z12", "columella",           "колумелла",             "midline", "nose",       (0.50,0.455),(0.03,0.03),  bonus=0.05, small_ok=True),
    Zone(13, "Z13", "upper_eyelid_left",   "верхнее веко левое",    "left",    "eyelid",     (0.335,0.70),(0.07,0.032), bonus=0.02, small_ok=True, excluded_by_segmentation=True, pair="upper_eyelid_right"),
    Zone(14, "Z14", "upper_eyelid_right",  "верхнее веко правое",   "right",   "eyelid",     (0.665,0.70),(0.07,0.032), bonus=0.02, small_ok=True, excluded_by_segmentation=True, pair="upper_eyelid_left"),
    Zone(15, "Z15", "lower_eyelid_left",   "нижнее веко левое",    "left",    "eyelid",     (0.335,0.655),(0.06,0.028), bonus=0.02, small_ok=True, excluded_by_segmentation=True, pair="lower_eyelid_right"),
    Zone(16, "Z16", "lower_eyelid_right",  "нижнее веко правое",   "right",   "eyelid",     (0.665,0.655),(0.06,0.028), bonus=0.02, small_ok=True, excluded_by_segmentation=True, pair="lower_eyelid_left"),
    Zone(17, "Z17", "infraorbital_left",   "подглазничная левая",  "left",    "infraorbital",(0.32,0.605),(0.07,0.038), pair="infraorbital_right"),
    Zone(18, "Z18", "infraorbital_right",  "подглазничная правая", "right",   "infraorbital",(0.68,0.605),(0.07,0.038), pair="infraorbital_left"),
    Zone(19, "Z19", "zygomatic_left",      "скуловая левая",        "left",    "zygomatic",  (0.21,0.61), (0.09,0.08),  pair="zygomatic_right"),
    Zone(20, "Z20", "zygomatic_right",     "скуловая правая",       "right",   "zygomatic",  (0.79,0.61), (0.09,0.08),  pair="zygomatic_left"),
    Zone(21, "Z21", "upper_cheek_left",    "верхняя щека левая",    "left",    "cheek",      (0.26,0.51), (0.10,0.07),  pair="upper_cheek_right"),
    Zone(22, "Z22", "upper_cheek_right",   "верхняя щека правая",   "right",   "cheek",      (0.74,0.51), (0.10,0.07),  pair="upper_cheek_left"),
    Zone(23, "Z23", "mid_cheek_left",      "средняя щека левая",    "left",    "cheek",      (0.21,0.41), (0.11,0.08),  pair="mid_cheek_right"),
    Zone(24, "Z24", "mid_cheek_right",     "средняя щека правая",   "right",   "cheek",      (0.79,0.41), (0.11,0.08),  pair="mid_cheek_left"),
    Zone(25, "Z25", "nasolabial_left",     "носогубная левая",      "left",    "nasolabial", (0.385,0.44),(0.05,0.07),  pair="nasolabial_right"),
    Zone(26, "Z26", "nasolabial_right",    "носогубная правая",     "right",   "nasolabial", (0.615,0.44),(0.05,0.07),  pair="nasolabial_left"),
    Zone(27, "Z27", "philtrum",            "область над губой",     "midline", "perioral",   (0.50,0.415),(0.06,0.032), bonus=0.02),
    Zone(28, "Z28", "upper_lip",           "верхняя губа",          "midline", "lip",        (0.50,0.378),(0.07,0.024), bonus=0.02, small_ok=True, excluded_by_segmentation=True),
    Zone(29, "Z29", "lower_lip",           "нижняя губа",          "midline", "lip",        (0.50,0.342),(0.07,0.024), bonus=0.02, small_ok=True, excluded_by_segmentation=True),
    Zone(30, "Z30", "mouth_corner_left",   "угол рта левый",        "left",    "perioral",   (0.375,0.375),(0.04,0.04), bonus=0.03, small_ok=True, pair="mouth_corner_right"),
    Zone(31, "Z31", "mouth_corner_right",  "угол рта правый",       "right",   "perioral",   (0.625,0.375),(0.04,0.04), bonus=0.03, small_ok=True, pair="mouth_corner_left"),
    Zone(32, "Z32", "below_lip",           "область под губой",     "midline", "perioral",   (0.50,0.305),(0.08,0.035), bonus=0.02),
    Zone(33, "Z33", "chin_center",         "подбородок центр",       "midline", "chin",       (0.50,0.215),(0.10,0.06)),
    Zone(34, "Z34", "chin_left",           "подбородок левый",       "left",    "chin",       (0.395,0.205),(0.07,0.05), pair="chin_right"),
    Zone(35, "Z35", "chin_right",          "подбородок правый",      "right",   "chin",       (0.605,0.205),(0.07,0.05), pair="chin_left"),
    Zone(36, "Z36", "jawline_left",        "линия челюсти левая",   "left",    "jaw",        (0.16,0.31), (0.10,0.11),  pair="jawline_right"),
    Zone(37, "Z37", "jawline_right",       "линия челюсти правая",  "right",   "jaw",        (0.84,0.31), (0.10,0.11),  pair="jawline_left"),
    Zone(38, "Z38", "lower_jaw_left",      "нижняя челюсть левая",  "left",    "jaw",        (0.30,0.135),(0.10,0.07),  pair="lower_jaw_right"),
    Zone(39, "Z39", "lower_jaw_right",     "нижняя челюсть правая", "right",   "jaw",        (0.70,0.135),(0.10,0.07),  pair="lower_jaw_left"),
    Zone(40, "Z40", "submental",           "подчелюстная область",  "midline", "jaw",        (0.50,0.075),(0.15,0.06)),
)

ZONES_BY_NAME = {z.name: z for z in ZONES}

FACE_SUPPORT_POLYGON = (
    (0.16,0.99),(0.84,0.99),(0.93,0.86),(0.97,0.60),(0.95,0.30),
    (0.86,0.09),(0.70,0.005),(0.30,0.005),(0.14,0.09),(0.05,0.30),
    (0.03,0.60),(0.07,0.86),
)


# ✅ VERIFIED → валидация определений зон (полигоны UV)
def validate_definitions() -> None:
    nums = [z.num for z in ZONES]
    ids = [z.zone_id for z in ZONES]
    names = [z.name for z in ZONES]
    if nums != list(range(1, 41)):
        raise ValueError("zone numbers must be 1..40 in order")
    if len(set(ids)) != 40 or len(set(names)) != 40:
        raise ValueError("duplicate zone id/name")
    for z in ZONES:
        if not (0 <= z.seed_uv[0] <= 1 and 0 <= z.seed_uv[1] <= 1):
            raise ValueError(f"seed out of range {z.zone_id}")
        if min(z.scale_uv) <= 0:
            raise ValueError(f"bad scale {z.zone_id}")
        if z.pair and z.pair not in ZONES_BY_NAME:
            raise ValueError(f"missing pair for {z.name}")


# 🔢 Центроиды треугольников в UV
def triangle_centroids_uv(uv_coords: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    uv = np.asarray(uv_coords, np.float32)[:, :2]
    tri = np.asarray(triangles, np.int64)
    return uv[tri].mean(axis=1)


# 🔢 Point-in-polygon тест для UV-точек
def points_in_polygon(points: np.ndarray, polygon) -> np.ndarray:
    contour = np.asarray(polygon, np.float32)
    return np.asarray(
        [cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0 for x, y in points],
        bool,
    )


# 🎯 CRITICAL → одна зона на треугольник внутри face support
def build_primary_triangle_zone(uv_coords: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Assign one zone per triangle inside the face support.

    score = sum(((c-seed)/scale)^2) - bonus
    The zone with the smallest score wins. `bonus` lets small central
    structures reliably claim their own neighborhood.
    """
    c = triangle_centroids_uv(uv_coords, triangles)
    support = points_in_polygon(c, FACE_SUPPORT_POLYGON)
    seeds = np.asarray([z.seed_uv for z in ZONES], np.float32)
    scales = np.asarray([z.scale_uv for z in ZONES], np.float32)
    bonus = np.asarray([z.bonus for z in ZONES], np.float32)
    d = (((c[:, None, :] - seeds[None, :, :]) / scales[None, :, :]) ** 2).sum(axis=2)
    d = d - bonus[None, :]
    out = np.full(len(c), -1, np.int16)
    out[support] = np.argmin(d[support], axis=1).astype(np.int16)
    return out, support


# 📊 Роль зоны по pose bin (аппликабельность)
def zone_role_for_pose(zone: Zone, pose: str) -> str:
    if pose == "frontal":
        return "primary"
    if zone.side == "midline":
        return "primary" if pose.endswith(("light", "mid")) else "support"
    near = "left" if pose.startswith("left_") else "right"
    if zone.side == near:
        return "primary" if not pose.endswith("profile") else "support"
    if pose.endswith("light"):
        return "support"
    if pose.endswith("mid"):
        return "limited"
    return "exclude"


# 📤 Экспорт контракта атласа для внешних потребителей
def export_contract() -> dict:
    payload = {
        "schema_version": ATLAS_VERSION,
        "uv_orientation": UV_ORIENTATION,
        "primary_policy": PRIMARY_POLICY,
        "zone_count": len(ZONES),
        "zones": [asdict(z) for z in ZONES],
        "face_support_polygon": FACE_SUPPORT_POLYGON,
        "pose_bins": POSE_BINS,
        "photo_mask_formula": "projected_zone AND skin_segmentation AND visibility AND safe_boundary AND quality_gate",
        "analysis_space": "original photo pixels",
        "segmentation_excluded_zones": [z.name for z in ZONES if z.excluded_by_segmentation],
    }
    payload["atlas_hash"] = sha256(repr(payload).encode()).hexdigest()
    return payload


validate_definitions()


# ---------------------------------------------------------------------------
# Per-photo projection (canonical atlas -> original photo pixels)
# ---------------------------------------------------------------------------

# ✅ Загрузка канонического атласа без пересчёта
def load_canonical_atlas(atlas_dir) -> dict:
    """Загрузить канонический атлас из диска (без пересчёта).

    Схема npz (финальный атлас):
      primary_triangle_zone : (T,) int16, -1 = фон, 0..N-1 = индекс зоны
      zone_names            : (N,) str
      zone_excluded_by_segmentation : (N,) bool
      triangles             : (T, 3) int64
      uv_coords             : (V, 2) float32
    """
    atlas_dir = Path(atlas_dir)
    with np.load(atlas_dir / "skin_zone_atlas.npz", allow_pickle=False) as z:
        primary = z["primary_triangle_zone"].astype(np.int64)
        zone_names = [str(x) for x in z["zone_names"]]
        excluded = [bool(x) for x in z["zone_excluded_by_segmentation"]]
        triangles = z["triangles"].astype(np.int64)
        uv_coords = z["uv_coords"].astype(np.float32)
    return {
        "primary_triangle_zone": primary,
        "zone_names": zone_names,
        "zone_excluded": excluded,
        "triangles": triangles,
        "uv_coords": uv_coords,
        "atlas_dir": atlas_dir,
    }


def _boundary_safe_mask(uv_coords: np.ndarray, margin: float = 0.02) -> np.ndarray:
    uv = np.asarray(uv_coords, np.float32)
    return (uv[:, 0] >= margin) & (uv[:, 0] <= 1 - margin) & (uv[:, 1] >= margin) & (uv[:, 1] <= 1 - margin)


def _uv_to_original(uv: np.ndarray, trans_params: np.ndarray, W: int, H: int) -> np.ndarray:
    pts_224 = np.zeros((uv.shape[0], 2), np.float32)
    pts_224[:, 0] = uv[:, 0] * 224.0
    pts_224[:, 1] = (1.0 - uv[:, 1]) * 224.0
    from .geometry import to_original_image
    return to_original_image(pts_224, trans_params)


def _zone_colors(n: int):
    colors = []
    for i in range(n):
        h = (i * 47) % 180
        c = np.zeros((1, 1, 3), np.uint8)
        c[0, 0] = (h, 230, 220)
        colors.append(tuple(int(x) for x in cv2.cvtColor(c, cv2.COLOR_HSV2BGR)[0, 0]))
    return colors


# 🎯 CRITICAL → проекция атласа на фото (актуальный путь)
def project_atlas_to_photo(
    atlas: dict,
    bgr: np.ndarray,
    uv_coords: np.ndarray,
    triangles: np.ndarray,
    skin_mask_original: np.ndarray | None,
    combined_visible: np.ndarray | None,
    trans_params: np.ndarray,
    pose_bin: str,
    out,
    png_size: int = 1000,
    vertices_2d: np.ndarray | None = None,
) -> dict:
    """Применить канонический атлас к КОНКРЕТНОМУ фото.

    Рабочая зона на фото =
        каноническая зона (primary_triangle_zone)
        ∩ segmentation mask кожи (skin_mask_original)
        ∩ 3D visibility (combined_visible)
        ∩ boundary safe mask (отступ от краёв UV)
        ∩ quality gates (покрытие/видимость)

    Сохраняет:
        skin_zone_projection.npz  — маски зон, bbox, метрики качества
        skin_zone_quality.json    — статус/исключения по каждой зоне
        _zones_overlay.png        — РЕНДЕР: на фото поверх оригинала сплошной
                                    заливкой (alpha=0.35) отображаются спроецированные
                                    зоны атласа (без вычитания сегментации кожи, чтобы
                                    заливка была цельной, а не «сеткой» из лоскутов).

    ВАЖНО: зоны рисуются ПО 3D-МОДЕЛИ. Для fillPoly используются 3D-вершины,
    спроецированные в 2D оригинального фото (vertices_2d = to_original_image(
    vertices_image_224, trans_params)), а НЕ плоская UV-развёртка. Благодаря
    этому на профиле/повороте заливаются только видимые треугольники mesh
    (combined_visible), а не весь атлас целиком.
    """
    out = Path(out)
    primary = np.asarray(atlas["primary_triangle_zone"], np.int64)
    zone_names = list(atlas["zone_names"])
    zone_excluded = list(atlas["zone_excluded"])
    tri = np.asarray(triangles, np.int64)
    uv = np.asarray(uv_coords, np.float32)
    H, W = bgr.shape[:2]

    # vertex zone = argmax priority among incident triangles (primary уже 0..N-1)
    vertex_zone = np.full(uv.shape[0], -1, dtype=np.int64)
    for ti in range(tri.shape[0]):
        zi = int(primary[ti])
        if zi < 0:
            continue
        for vi in tri[ti]:
            vi = int(vi)
            if vertex_zone[vi] < 0:
                vertex_zone[vi] = zi

    if skin_mask_original is None:
        skin_mask = np.zeros((H, W), bool)
        skin_coverage = 0.0
    else:
        skin_mask = np.asarray(skin_mask_original, bool)
        skin_coverage = float(np.mean(skin_mask)) if skin_mask.size else 0.0

    if combined_visible is None:
        vis = np.ones(uv.shape[0], bool)
    else:
        vis = np.asarray(combined_visible, bool).reshape(-1)
        if vis.size != uv.shape[0]:
            vis = np.ones(uv.shape[0], bool)

    safe = _boundary_safe_mask(uv, margin=0.02)
    # Рендер ПО 3D-МОДЕЛИ: берём спроецированные 3D-вершины (vertices_2d),
    # а не плоскую UV-развёртку. Тогда зоны ложатся на видимую поверхность mesh.
    if vertices_2d is None:
        verts_2d = _uv_to_original(uv, trans_params, W, H)
    else:
        verts_2d = np.asarray(vertices_2d, np.float32).reshape(-1, 2)

    zone_id_map = np.zeros(uv.shape[0], dtype=np.int64)
    zone_masks_photo: dict[str, np.ndarray] = {}
    zone_bbox: dict[str, list[int]] = {}
    zone_visible_fraction: dict[str, float] = {}
    zone_skin_pixels: dict[str, int] = {}
    zone_quality: dict[str, float] = {}
    zone_status: dict[str, str] = {}
    zone_reasons: dict[str, list[str]] = {}

    for idx, name in enumerate(zone_names):
        vidx = np.where(vertex_zone == idx)[0]
        if vidx.size == 0:
            zone_status[name] = "empty"
            zone_reasons[name] = ["no_triangles_in_atlas"]
            zone_masks_photo[name] = np.zeros((H, W), bool)
            zone_bbox[name] = [0, 0, 0, 0]
            zone_visible_fraction[name] = 0.0
            zone_skin_pixels[name] = 0
            zone_quality[name] = 0.0
            continue
        work = np.zeros(uv.shape[0], bool)
        work[vidx] = True
        work &= vis
        work &= safe
        # Сплошная заливка области зоны через её треугольники
        # (без дыр от редких вершин у маленьких зон).
        # photo_mask_render — цельная заливка ВСЕЙ зоны (без вычитания
        # сегментации кожи), используется для визуального рендера _zones_overlay.
        # photo_mask — рабочая маска зоны (∩ skin_mask) для метрик качества/bbox.
        photo_mask_render = np.zeros((H, W), np.uint8)
        tri_in_zone = np.all(work[tri], axis=1)
        if np.any(tri_in_zone):
            pts = np.round(verts_2d[tri[tri_in_zone]]).astype(int)
            pts[:, :, 0] = np.clip(pts[:, :, 0], 0, W - 1)
            pts[:, :, 1] = np.clip(pts[:, :, 1], 0, H - 1)
            polys = [p.astype(np.int32) for p in pts]
            cv2.fillPoly(photo_mask_render, polys, 1)
        photo_mask_render = photo_mask_render.astype(bool)
        photo_mask = photo_mask_render & skin_mask
        ys, xs = np.where(photo_mask)
        skin_pixels = int(xs.size)
        vis_frac = float(np.mean(vis[vidx])) if vidx.size else 0.0
        reasons: list[str] = []
        if zone_excluded[idx]:
            reasons.append("excluded_by_segmentation")
        if skin_pixels < 50:
            reasons.append("insufficient_skin_pixels")
        if vis_frac < 0.5:
            reasons.append("low_3d_visibility")
        status = "active" if not reasons else "excluded"
        zone_id_map[vidx] = idx
        zone_masks_photo[name] = photo_mask_render
        if xs.size and ys.size:
            zone_bbox[name] = [int(xs.min()), int(ys.min()), int(xs.max() - xs.min()), int(ys.max() - ys.min())]
        else:
            zone_bbox[name] = [0, 0, 0, 0]
        zone_visible_fraction[name] = vis_frac
        zone_skin_pixels[name] = skin_pixels
        zone_quality[name] = round(min(1.0, skin_pixels / 2000.0) * vis_frac, 4)
        zone_status[name] = status
        zone_reasons[name] = reasons

    np.savez_compressed(
        out / "skin_zone_projection.npz",
        zone_id_map=zone_id_map.astype(np.int64),
        zone_names=np.array(zone_names, dtype=object),
        zone_masks_photo=zone_masks_photo,
        zone_bbox_original=np.array([zone_bbox[n] for n in zone_names], np.int32),
        zone_visible_fraction=np.array([zone_visible_fraction[n] for n in zone_names], np.float32),
        zone_skin_pixels=np.array([zone_skin_pixels[n] for n in zone_names], np.int64),
        uv_coords=uv.astype(np.float32),
        triangles=tri.astype(np.int64),
        skin_mask_coverage=np.array([skin_coverage], np.float32),
    )

    quality_doc = {
        "schema_version": ATLAS_VERSION,
        "pose_bin": pose_bin,
        "skin_mask_coverage": skin_coverage,
        "zones": {
            name: {
                "status": zone_status[name],
                "exclusion_reasons": zone_reasons[name],
                "visible_fraction": zone_visible_fraction[name],
                "skin_pixels": zone_skin_pixels[name],
                "quality": zone_quality[name],
                "bbox_original": zone_bbox[name],
            }
            for name in zone_names
        },
    }
    (out / "skin_zone_quality.json").write_text(
        json.dumps(quality_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # _zones_overlay: РЕНДЕР спроецированных зон атласа на фото.
    # Сплошная заливка каждой зоны цветом с прозрачностью 35% (поверх оригинала).
    # Заливается цельная область зоны (photo_mask_render), НО поверх неё
    # накладывается маска кожи (skin_mask), чтобы НЕ окрашивались глаза, брови
    # и губы — они не входят в face_mask.png, по которому пойдёт анализ кожи.
    # Благодаря fillPoly заливка остаётся сплошной (с «окнами» только в местах
    # глаз/бровей/губ), а не превращается в «сетку» из лоскутов.
    colors = _zone_colors(len(zone_names))
    zones_overlay = bgr.astype(np.float32)
    alpha = 0.35
    for i, name in enumerate(zone_names):
        m = zone_masks_photo[name]
        if not np.any(m):
            continue
        # Исключаем области вне маски кожи (глаза/брови/губы), если маска есть.
        if skin_mask is not None and skin_mask.size:
            m = m & skin_mask
            if not np.any(m):
                continue
        c = np.array(colors[i], np.float32)
        zones_overlay[m] = zones_overlay[m] * (1.0 - alpha) + c * alpha
    if not cv2.imwrite(str(out / "_zones_overlay.png"), zones_overlay.astype(np.uint8)):
        raise OSError(f"failed to write _zones_overlay.png to {out}")

    return {
        "skin_zone_projection": "skin_zone_projection.npz",
        "skin_zone_quality": "skin_zone_quality.json",
        "zones_overlay": "_zones_overlay.png",
    }
