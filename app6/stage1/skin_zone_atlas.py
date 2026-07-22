"""app6/stage1/skin_zone_atlas.py — канонический атлас зон кожи лица на UV.

ДВА УРОВНЯ:

1) КАНОНИЧЕСКИЙ АТЛАС (генерируется ОДИН РАЗ на версию атласа):
   app6/atlas/skin_zone_atlas_v1/
     skin_zone_atlas_v1.json          (смысловой контракт: зоны, правила, версия)
     skin_zone_atlas_triangles.npz    (машинный: primary_triangle_zone, индексы)
     skin_zone_atlas_uv.png           (визуальная проверка человеком)
     skin_zone_atlas_pose_policy.csv  (зона x ракурс -> применимость)
   Строится функцией generate_canonical_atlas(atlas_dir, uv_coords, triangles).

2) ПРОЕКЦИЯ АТЛАСА НА ФОТО (для КАЖДОГО фото в Stage 1):
   photo_result/
     skin_zone_projection.npz   (zone_id_map, zone_masks_photo, bbox, fractions...)
     skin_zone_quality.json     (status/exclusion/quality по зонам)
     skin_zone_overlay.png      (визуальная накладка зон на фото)
   Строится функцией project_atlas_to_photo(...).
   ⚠️ AUDIT-5: из assets.py больше НЕ вызывается (там явно отключён legacy-fallback) —
   live-путь проекции атласа: stage1/skin/projection.py. Функция оставлена для
   render_skin_zone_atlas.py и совместимости.

ОРИЕНТАЦИЯ UV (проверено по mesh_zone_indices.json на BFM-35709):
  u: 0 = левый край атласа, 1 = правый край
  v: 0 = подбородок,        1 = лоб
Каждая зона задана uv_box = (u_min, v_min, u_max, v_max) в [0, 1]^2.

ПРАВИЛО PRIORITY (зафиксировано явно):
  "higher_priority_wins" — бОЛЬШЕЕ число = ВАЖНЕЕ.
  100 — морщинные focus-зоны (перекрывают широкие анатомические)
   70 — анатомические зоны полного покрытия лица
   30 — reference-зоны (шум/цвет/качество)
  При конфликте перекрытия выигрывает зона с бОльшим priority.

ГУБЫ ИСКЛЮЧЕНЫ: зоны вокруг рта называются perioral_skin (околоротовые зоны
кожи), губы (upper_lip/lower_lip) исключаются segmentation mask и не входят
в атлас как зоны кожи.
⚠️ CONVENTIONS v2 → «legacy» по имени, но единственный ЖИВОЙ генератор канонического
атласа (через scripts/render_skin_zone_atlas.py). skin_zone_atlas_final.py НЕ подключён
(AUDIT-5). Live-проекция зон: stage1/skin/projection.py.
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# 9 канонических ракурсов (совпадают с app6/stage1/config.py POSE_BINS).
POSE_BINS = (
    "left_profile", "left_deep", "left_mid", "left_light",
    "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)

ATLAS_SCHEMA_VERSION = "skin-zone-atlas-v1.0"
PRIORITY_RULE = "higher_priority_wins"  # больше priority = важнее

# 38 зон кожи. kind: anatomical_region | wrinkle_focus | perioral_skin | reference.
# side: left | right | center. priority: 100 морщины, 70 анатомия, 30 reference.
ZONE_SPECS: list[dict[str, Any]] = [
    # --- Анатомические регионы (23) — priority 70 ---
    dict(zone_id="F00", name="forehead", label_ru="лоб", parent="forehead",
         side="center", kind="anatomical_region", priority=70, min_level=1,
         uv_box=(0.20, 0.80, 0.80, 0.98)),
    dict(zone_id="BR_L", name="brow_ridge_L", label_ru="левая надбровная дуга", parent="brow",
         side="left", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.25, 0.70, 0.45, 0.80)),
    dict(zone_id="BR_R", name="brow_ridge_R", label_ru="правая надбровная дуга", parent="brow",
         side="right", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.55, 0.70, 0.75, 0.80)),
    dict(zone_id="OR_L", name="orbit_L", label_ru="левая орбитальная область (глаз)", parent="orbit",
         side="left", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.28, 0.58, 0.44, 0.72)),
    dict(zone_id="OR_R", name="orbit_R", label_ru="правая орбитальная область (глаз)", parent="orbit",
         side="right", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.56, 0.58, 0.72, 0.72)),
    dict(zone_id="NBT", name="nose_bridge_tip", label_ru="спинка и кончик носа", parent="nose",
         side="center", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.44, 0.42, 0.56, 0.72)),
    dict(zone_id="NW_L", name="nose_wing_L", label_ru="левое крыло носа", parent="nose",
         side="left", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.36, 0.38, 0.47, 0.52)),
    dict(zone_id="NW_R", name="nose_wing_R", label_ru="правое крыло носа", parent="nose",
         side="right", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.53, 0.38, 0.64, 0.52)),
    dict(zone_id="CB_L", name="cheekbone_L", label_ru="левая скула", parent="cheek",
         side="left", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.18, 0.52, 0.38, 0.68)),
    dict(zone_id="CB_R", name="cheekbone_R", label_ru="правая скула", parent="cheek",
         side="right", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.62, 0.52, 0.82, 0.68)),
    dict(zone_id="CS_L", name="cheek_soft_L", label_ru="левая мягкая щека", parent="cheek",
         side="left", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.28, 0.68, 0.42, 0.82)),
    dict(zone_id="CS_R", name="cheek_soft_R", label_ru="правая мягкая щека", parent="cheek",
         side="right", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.58, 0.18, 0.72, 0.32)),
    dict(zone_id="JW_L", name="jaw_L", label_ru="левая челюсть", parent="jaw",
         side="left", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.22, 0.12, 0.45, 0.35)),
    dict(zone_id="JW_R", name="jaw_R", label_ru="правая челюсть", parent="jaw",
         side="right", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.55, 0.12, 0.78, 0.35)),
    dict(zone_id="CH", name="chin", label_ru="подбородок", parent="chin",
         side="center", kind="anatomical_region", priority=70, min_level=1,
         uv_box=(0.40, 0.02, 0.60, 0.18)),
    dict(zone_id="LZ_L", name="ligament_zygomatic_L", label_ru="левая скуловая связка", parent="ligament",
         side="left", kind="anatomical_region", priority=70, min_level=3,
         uv_box=(0.30, 0.55, 0.42, 0.65)),
    dict(zone_id="LZ_R", name="ligament_zygomatic_R", label_ru="правая скуловая связка", parent="ligament",
         side="right", kind="anatomical_region", priority=70, min_level=3,
         uv_box=(0.58, 0.55, 0.70, 0.65)),
    dict(zone_id="LO_L", name="ligament_orbital_L", label_ru="левая орбитальная связка", parent="ligament",
         side="left", kind="anatomical_region", priority=70, min_level=3,
         uv_box=(0.30, 0.60, 0.42, 0.70)),
    dict(zone_id="LO_R", name="ligament_orbital_R", label_ru="правая орбитальная связка", parent="ligament",
         side="right", kind="anatomical_region", priority=70, min_level=3,
         uv_box=(0.58, 0.60, 0.70, 0.70)),
    dict(zone_id="JA_L", name="jaw_angle_L", label_ru="левый угол челюсти", parent="jaw",
         side="left", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.10, 0.10, 0.25, 0.30)),
    dict(zone_id="JA_R", name="jaw_angle_R", label_ru="правый угол челюсти", parent="jaw",
         side="right", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.75, 0.10, 0.90, 0.30)),
    dict(zone_id="TP_L", name="temporal_L", label_ru="левый висок", parent="temple",
         side="left", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.05, 0.65, 0.22, 0.85)),
    dict(zone_id="TP_R", name="temporal_R", label_ru="правый висок", parent="temple",
         side="right", kind="anatomical_region", priority=70, min_level=2,
         uv_box=(0.78, 0.65, 0.95, 0.85)),

    # --- Морщинные focus-зоны (13) — priority 100 (перекрывают анатомию) ---
    dict(zone_id="FH_C", name="forehead_horizontal_center", label_ru="горизонтальные лобные складки (центр)", parent="forehead",
         side="center", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.30, 0.75, 0.70, 0.95)),
    dict(zone_id="FH_L", name="forehead_horizontal_left", label_ru="горизонтальные лобные складки (лево)", parent="forehead",
         side="left", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.05, 0.75, 0.35, 0.95)),
    dict(zone_id="FH_R", name="forehead_horizontal_right", label_ru="горизонтальные лобные складки (право)", parent="forehead",
         side="right", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.65, 0.75, 0.95, 0.95)),
    dict(zone_id="GL_V", name="glabella_vertical", label_ru="вертикальные межбровные складки", parent="glabella",
         side="center", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.42, 0.60, 0.58, 0.82)),
    dict(zone_id="GL_H", name="glabella_horizontal", label_ru="горизонтальные межбровные складки", parent="glabella",
         side="center", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.38, 0.66, 0.62, 0.78)),
    dict(zone_id="CF_L", name="crow_feet_left", label_ru="левые гусиные лапки", parent="orbit",
         side="left", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.02, 0.40, 0.22, 0.65)),
    dict(zone_id="CF_R", name="crow_feet_right", label_ru="правые гусиные лапки", parent="orbit",
         side="right", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.78, 0.40, 0.98, 0.65)),
    dict(zone_id="NL_L", name="nasolabial_left", label_ru="левая носогубная складка", parent="nasolabial",
         side="left", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.30, 0.28, 0.46, 0.55)),
    dict(zone_id="NL_R", name="nasolabial_right", label_ru="правая носогубная складка", parent="nasolabial",
         side="right", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.54, 0.28, 0.70, 0.55)),
    dict(zone_id="MA_L", name="marionette_left", label_ru="левые линии марионетки", parent="marionette",
         side="left", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.34, 0.08, 0.48, 0.28)),
    dict(zone_id="MA_R", name="marionette_right", label_ru="правые линии марионетки", parent="marionette",
         side="right", kind="wrinkle_focus", priority=100, min_level=2,
         uv_box=(0.52, 0.08, 0.66, 0.28)),
    dict(zone_id="PO_U", name="upper_perioral_skin", label_ru="верхняя околоротовая зона кожи", parent="perioral",
         side="center", kind="perioral_skin", priority=100, min_level=2,
         uv_box=(0.40, 0.26, 0.60, 0.38)),
    dict(zone_id="PO_L", name="lower_perioral_skin", label_ru="нижняя околоротовая зона кожи", parent="perioral",
         side="center", kind="perioral_skin", priority=100, min_level=2,
         uv_box=(0.40, 0.10, 0.60, 0.22)),

    # --- Reference-зоны (2) — priority 30 (шум/цвет/качество) ---
    dict(zone_id="RF_N", name="reference_near_nose", label_ru="референс у носа (шум/цвет)", parent="reference",
         side="center", kind="reference", priority=30, min_level=1,
         uv_box=(0.46, 0.55, 0.54, 0.62)),
    dict(zone_id="RF_C", name="reference_cheek_center", label_ru="референс центр щеки (шум/цвет)", parent="reference",
         side="center", kind="reference", priority=30, min_level=1,
         uv_box=(0.45, 0.45, 0.55, 0.52)),
]

_ZONE_NAME_TO_INDEX = {spec["name"]: i + 1 for i, spec in enumerate(ZONE_SPECS)}


# ⚠️ LEGACY → primary_triangle_zone (T,) int; см. *_final
def build_triangle_zone_map(uv_coords: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Вернуть primary_triangle_zone: (T,) int, 0 = фон, 1..N = индекс зоны.

    Треугольник относится к зоне, если центроид его UV лежит в uv_box зоны.
    Зоны перебираются по убыванию priority (higher_priority_wins), поэтому
    морщинные focus-зоны (100) перекрывают широкие анатомические (70), а те —
    reference (30).
    """
    uv = np.asarray(uv_coords, np.float32)
    tri = np.asarray(triangles, np.int64)
    if uv.ndim != 2 or uv.shape[1] < 2:
        raise ValueError("uv_coords must have shape (N, 2|3)")
    if tri.ndim != 2 or tri.shape[1] != 3:
        raise ValueError("triangles must have shape (T, 3)")
    cen = uv[tri].mean(axis=1)  # (T, 2)
    primary = np.zeros(tri.shape[0], dtype=np.int64)
    order = sorted(range(len(ZONE_SPECS)), key=lambda i: ZONE_SPECS[i]["priority"], reverse=True)
    for i in order:
        spec = ZONE_SPECS[i]
        umin, vmin, umax, vmax = spec["uv_box"]
        mask = (cen[:, 0] >= umin) & (cen[:, 0] <= umax) & (cen[:, 1] >= vmin) & (cen[:, 1] <= vmax)
        primary[mask] = i + 1
    return primary


def _zone_colors(n: int) -> list[tuple[int, int, int]]:
    """Равномерно разнесённые по оттенку цвета (BGR для cv2)."""
    import colorsys
    out: list[tuple[int, int, int]] = []
    for i in range(n):
        h = (i * 0.61803398875) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.62, 0.95)
        out.append((int(b * 255), int(g * 255), int(r * 255)))
    return out


def _tri_px(uv: np.ndarray, tri_verts: np.ndarray, size: int) -> np.ndarray:
    """Вернуть пиксельные координаты треугольника (3,2) int32.

    v=1 (лоб) отображается сверху: y_px = (1-v)*size.
    """
    pts = np.empty((3, 2), np.int32)
    for k, vi in enumerate(tri_verts):
        u, v = uv[vi]
        pts[k, 0] = int(round(u * (size - 1)))
        pts[k, 1] = int(round((1.0 - v) * (size - 1)))
    return pts


# 📤 Отрисовка UV-атласа в PNG (диагностика)
def render_atlas_png(uv_coords: np.ndarray, triangles: np.ndarray, primary: np.ndarray, size: int = 1024) -> np.ndarray:
    """Отрисовать UV-атлас:
      - фон = ЧЁРНЫЙ;
      - развертка 3D-модели = СЕРАЯ СЕТКА (только линии треугольников, без заливки);
      - зоны = цветная РАМКА (контур), без сплошной заливки.

    v=1 (лоб) отображается сверху (y_px = (1-v)*size).
    """
    uv = np.asarray(uv_coords, np.float32)
    tri = np.asarray(triangles, np.int64)
    # Чёрный фон
    img = np.zeros((size, size, 3), dtype=np.uint8)
    # Серая сетка развертки модели (только линии)
    grid_color = (120, 120, 120)
    for ti in range(tri.shape[0]):
        pts = _tri_px(uv, tri[ti], size)
        cv2.polylines(img, [pts], True, grid_color, 1, cv2.LINE_AA)
    # Зоны — рамкой (контур маски зоны)
    colors = _zone_colors(len(ZONE_SPECS))
    for zi in range(1, len(ZONE_SPECS) + 1):
        tids = np.where(primary == zi)[0]
        if tids.size == 0:
            continue
        mask = np.zeros((size, size), np.uint8)
        for ti in tids:
            pts = _tri_px(uv, tri[ti], size)
            cv2.fillPoly(mask, [pts], 255)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(img, contours, -1, colors[zi - 1], 2, cv2.LINE_AA)
    return img


def _pose_weight(pose_bin: str, spec: dict[str, Any]) -> float:
    """Вес применимости зоны для ракурса: 1.0 primary, 0.5 limited, 0.0 exclude."""
    side = spec["side"]
    if pose_bin == "frontal":
        return 1.0
    is_left = "left" in pose_bin
    if side == "center":
        return 0.5 if "profile" in pose_bin else 1.0
    if side == "left":
        if is_left:
            return 0.75 if "profile" in pose_bin else 1.0
        return 0.0
    if side == "right":
        if not is_left:
            return 0.75 if "profile" in pose_bin else 1.0
        return 0.0
    return 0.0


# 🏭 Политика видимости зон по бинам (legacy-расчёт)
def build_pose_policy() -> dict[str, dict[str, float]]:
    policy: dict[str, dict[str, float]] = {}
    for pose in POSE_BINS:
        policy[pose] = {spec["name"]: _pose_weight(pose, spec) for spec in ZONE_SPECS}
    return policy


# 📤 JSON-контракт атласа (legacy)
def build_atlas_json(primary: np.ndarray) -> dict[str, Any]:
    counts = np.bincount(primary, minlength=len(ZONE_SPECS) + 1)
    coverage = {spec["name"]: int(counts[i + 1]) for i, spec in enumerate(ZONE_SPECS)}
    zones = []
    for spec in ZONE_SPECS:
        zones.append({
            "zone_id": spec["zone_id"],
            "name": spec["name"],
            "label_ru": spec["label_ru"],
            "parent": spec["parent"],
            "side": spec["side"],
            "kind": spec["kind"],
            "priority": spec["priority"],
            "priority_rule": PRIORITY_RULE,
            "min_level": spec["min_level"],
            "uv_box": [float(x) for x in spec["uv_box"]],
        })
    return {
        "schema_version": ATLAS_SCHEMA_VERSION,
        "mesh_topology": "bfm-35709",
        "uv_orientation": "u:0=left,1=right; v:0=chin,1=forehead",
        "priority_rule": PRIORITY_RULE,
        "zone_count": len(ZONE_SPECS),
        "background_triangle_count": int(counts[0]),
        "zones": zones,
        "coverage_triangle_counts": coverage,
    }


# 🏭 FACTORY → записать 4 канонических слоя ОДИН РАЗ
def generate_canonical_atlas(atlas_dir: Path, uv_coords: np.ndarray, triangles: np.ndarray, png_size: int = 1024, face_model_path: Path | None = None) -> dict[str, Any]:
    """Построить и записать 4 канонических слоя атласа ОДИН РАЗ.

    Возвращает словарь с primary_triangle_zone и путями (для использования
    project_atlas_to_photo без повторного чтения NPZ).
    """
    atlas_dir = Path(atlas_dir)
    atlas_dir.mkdir(parents=True, exist_ok=True)
    primary = build_triangle_zone_map(uv_coords, triangles)

    (atlas_dir / "skin_zone_atlas_v1.json").write_text(
        json.dumps(build_atlas_json(primary), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    zone_names = np.array([s["name"] for s in ZONE_SPECS], dtype=object)
    zone_ids = np.array([s["zone_id"] for s in ZONE_SPECS], dtype=object)
    zone_priority = np.array([s["priority"] for s in ZONE_SPECS], np.int32)
    zone_kind = np.array([s["kind"] for s in ZONE_SPECS], dtype=object)
    zone_to_triangles = {
        spec["name"]: np.where(primary == (i + 1))[0].astype(np.int64)
        for i, spec in enumerate(ZONE_SPECS)
    }
    np.savez_compressed(
        atlas_dir / "skin_zone_atlas_triangles.npz",
        primary_triangle_zone=primary.astype(np.int64),
        zone_names=zone_names,
        zone_ids=zone_ids,
        zone_priority=zone_priority,
        zone_kind=zone_kind,
        uv_coords=np.asarray(uv_coords, np.float32),
        triangles=np.asarray(triangles, np.int64),
        zone_to_triangles=zone_to_triangles,
    )
    # Развертка 3D-модели для фона PNG (если задан путь к face_model.npy)
    if face_model_path is not None:
        fm = np.load(face_model_path, allow_pickle=True).item()
        model_uv = np.asarray(fm["uv_coords"], np.float32)
        model_tri = np.asarray(fm["tri"], np.int64)
    else:
        model_uv, model_tri = np.asarray(uv_coords, np.float32), np.asarray(triangles, np.int64)
    png = render_atlas_png(model_uv, model_tri, primary, size=png_size)
    if not cv2.imwrite(str(atlas_dir / "skin_zone_atlas_uv.png"), png):
        raise OSError(f"failed to write skin_zone_atlas_uv.png to {atlas_dir}")
    write_pose_policy_csv(build_pose_policy(), atlas_dir)
    return {
        "primary_triangle_zone": primary,
        "zone_names": zone_names,
        "zone_ids": zone_ids,
        "zone_priority": zone_priority,
        "zone_kind": zone_kind,
        "zone_to_triangles": zone_to_triangles,
        "uv_coords": np.asarray(uv_coords, np.float32),
        "triangles": np.asarray(triangles, np.int64),
        "atlas_dir": atlas_dir,
    }


# 📤 Запись pose policy CSV
def write_pose_policy_csv(policy: dict[str, dict[str, float]], out_dir: Path) -> None:
    with open(out_dir / "skin_zone_atlas_pose_policy.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pose_bin"] + [s["name"] for s in ZONE_SPECS])
        for pose, row in policy.items():
            w.writerow([pose] + [row[s["name"]] for s in ZONE_SPECS])


# ✅ Загрузка канонического атласа без пересчёта
def load_canonical_atlas(atlas_dir: Path) -> dict[str, Any]:
    """Загрузить канонический атлас из диска (без пересчёта)."""
    atlas_dir = Path(atlas_dir)
    with np.load(atlas_dir / "skin_zone_atlas_triangles.npz", allow_pickle=False) as z:
        return {
            "primary_triangle_zone": z["primary_triangle_zone"].astype(np.int64),
            "zone_names": z["zone_names"],
            "zone_ids": z["zone_ids"],
            "zone_priority": z["zone_priority"].astype(np.int32),
            "zone_kind": z["zone_kind"],
            "zone_to_triangles": z["zone_to_triangles"].item() if "zone_to_triangles" in z else {},
            "uv_coords": z["uv_coords"].astype(np.float32),
            "triangles": z["triangles"].astype(np.int64),
            "atlas_dir": atlas_dir,
        }


def _boundary_safe_mask(uv_coords: np.ndarray, margin: float = 0.02) -> np.ndarray:
    """Вершины, центроид которых не ближе margin к краю UV [0,1]."""
    uv = np.asarray(uv_coords, np.float32)
    return (uv[:, 0] >= margin) & (uv[:, 0] <= 1 - margin) & (uv[:, 1] >= margin) & (uv[:, 1] <= 1 - margin)


def _uv_to_original(uv: np.ndarray, trans_params: np.ndarray, W: int, H: int) -> np.ndarray:
    """Проецировать UV-координаты (0..1) в пиксели исходного изображения.

    UV (u,v) -> 224-пространство (u*224, (1-v)*224), затем to_original_image.
    """
    pts_224 = np.zeros((uv.shape[0], 2), np.float32)
    pts_224[:, 0] = uv[:, 0] * 224.0
    pts_224[:, 1] = (1.0 - uv[:, 1]) * 224.0
    from .geometry import to_original_image
    return to_original_image(pts_224, trans_params)


# 🎯 Применение атласа к конкретному фото (legacy-путь)
def project_atlas_to_photo(
    atlas: dict[str, Any],
    bgr: np.ndarray,
    uv_coords: np.ndarray,
    triangles: np.ndarray,
    skin_mask_original: np.ndarray | None,
    combined_visible: np.ndarray | None,
    trans_params: np.ndarray,
    pose_bin: str,
    out: Path,
    png_size: int = 1024,
) -> dict[str, str]:
    """Применить канонический атлас к КОНКРЕТНОМУ фото.

    Рабочая зона на фото =
        каноническая зона (primary_triangle_zone)
        ∩ segmentation mask кожи (skin_mask_original)
        ∩ 3D visibility (combined_visible)
        ∩ boundary safe mask (отступ от краёв UV)
        ∩ quality gates (покрытие/видимость)

    Сохраняет в out:
        skin_zone_projection.npz
        skin_zone_quality.json
        skin_zone_overlay.png

    Возвращает словарь имён файлов для записи в info.json files.
    """
    out = Path(out)
    primary = np.asarray(atlas["primary_triangle_zone"], np.int64)
    zone_names = list(atlas["zone_names"])
    zone_to_triangles = atlas["zone_to_triangles"]
    uv = np.asarray(uv_coords, np.float32)
    tri = np.asarray(triangles, np.int64)
    H, W = bgr.shape[:2]

    # --- 1. Каноническая зона на уровне вершин (агрегация triangle->vertex) ---
    vertex_zone = np.zeros(uv.shape[0], dtype=np.int64)
    for ti in range(tri.shape[0]):
        zi = int(primary[ti])
        if zi == 0:
            continue
        for vi in tri[ti]:
            vi = int(vi)
            if vertex_zone[vi] == 0 or ZONE_SPECS[zi - 1]["priority"] >= ZONE_SPECS[vertex_zone[vi] - 1]["priority"]:
                vertex_zone[vi] = zi

    # --- 2. Segmentation mask кожи (исходное изображение) ---
    if skin_mask_original is None:
        skin_mask = np.zeros((H, W), bool)
        skin_coverage = 0.0
    else:
        skin_mask = np.asarray(skin_mask_original, bool)
        skin_coverage = float(np.mean(skin_mask)) if skin_mask.size else 0.0

    # --- 3. 3D visibility (на уровне вершин) ---
    if combined_visible is None:
        vis = np.ones(uv.shape[0], bool)
    else:
        vis = np.asarray(combined_visible, bool).reshape(-1)
        if vis.size != uv.shape[0]:
            vis = np.ones(uv.shape[0], bool)

    # --- 4. Boundary safe mask (вершины внутри отступа от края UV) ---
    safe = _boundary_safe_mask(uv, margin=0.02)

    # --- 5. Проекция вершин зоны в исходное изображение ---
    verts_2d = _uv_to_original(uv, trans_params, W, H)

    # --- 6. Для каждой зоны считаем маски и метрики ---
    zone_id_map = np.zeros(uv.shape[0], dtype=np.int64)
    zone_masks_photo: dict[str, np.ndarray] = {}
    zone_bbox_original: dict[str, list[int]] = {}
    zone_visible_fraction: dict[str, float] = {}
    zone_skin_pixels: dict[str, int] = {}
    zone_quality: dict[str, float] = {}
    zone_status: dict[str, str] = {}
    zone_exclusion_reasons: dict[str, list[str]] = {}

    for name in zone_names:
        tids = np.asarray(zone_to_triangles.get(name, []), np.int64)
        if tids.size == 0:
            zone_status[name] = "empty"
            zone_exclusion_reasons[name] = ["no_triangles_in_atlas"]
            zone_masks_photo[name] = np.zeros((H, W), bool)
            zone_bbox_original[name] = [0, 0, 0, 0]
            zone_visible_fraction[name] = 0.0
            zone_skin_pixels[name] = 0
            zone_quality[name] = 0.0
            continue
        vidx = np.unique(tri[tids].reshape(-1))
        work_vertex = np.zeros(uv.shape[0], bool)
        work_vertex[vidx] = True
        work_vertex &= vis
        work_vertex &= safe
        ys = np.clip(np.round(verts_2d[vidx, 1]).astype(int), 0, H - 1)
        xs = np.clip(np.round(verts_2d[vidx, 0]).astype(int), 0, W - 1)
        photo_mask = np.zeros((H, W), bool)
        photo_mask[ys, xs] = True
        photo_mask &= skin_mask
        skin_pixels = int(np.count_nonzero(photo_mask))
        vis_frac = float(np.mean(vis[vidx])) if vidx.size else 0.0
        reasons: list[str] = []
        if skin_pixels < 50:
            reasons.append("insufficient_skin_pixels")
        if vis_frac < 0.5:
            reasons.append("low_3d_visibility")
        status = "active" if not reasons else "excluded"
        zone_id_map[vidx] = _ZONE_NAME_TO_INDEX[name]
        zone_masks_photo[name] = photo_mask
        if xs.size and ys.size:
            zone_bbox_original[name] = [int(xs.min()), int(ys.min()), int(xs.max() - xs.min()), int(ys.max() - ys.min())]
        else:
            zone_bbox_original[name] = [0, 0, 0, 0]
        zone_visible_fraction[name] = vis_frac
        zone_skin_pixels[name] = skin_pixels
        zone_quality[name] = round(min(1.0, skin_pixels / 2000.0) * vis_frac, 4)
        zone_status[name] = status
        zone_exclusion_reasons[name] = reasons

    # --- 7. Запись NPZ ---
    np.savez_compressed(
        out / "skin_zone_projection.npz",
        zone_id_map=zone_id_map.astype(np.int64),
        zone_names=np.array(zone_names, dtype=object),
        zone_masks_photo=zone_masks_photo,
        zone_bbox_original=np.array([zone_bbox_original[n] for n in zone_names], np.int32),
        zone_visible_fraction=np.array([zone_visible_fraction[n] for n in zone_names], np.float32),
        zone_skin_pixels=np.array([zone_skin_pixels[n] for n in zone_names], np.int64),
        uv_coords=uv.astype(np.float32),
        triangles=tri.astype(np.int64),
        skin_mask_coverage=np.array([skin_coverage], np.float32),
    )

    # --- 8. Запись quality JSON ---
    quality_doc = {
        "schema_version": ATLAS_SCHEMA_VERSION,
        "pose_bin": pose_bin,
        "skin_mask_coverage": skin_coverage,
        "zones": {
            name: {
                "status": zone_status[name],
                "exclusion_reasons": zone_exclusion_reasons[name],
                "visible_fraction": zone_visible_fraction[name],
                "skin_pixels": zone_skin_pixels[name],
                "quality": zone_quality[name],
                "bbox_original": zone_bbox_original[name],
            }
            for name in zone_names
        },
    }
    (out / "skin_zone_quality.json").write_text(
        json.dumps(quality_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # --- 9. Overlay PNG (зоны поверх фото) ---
    overlay = _render_overlay(bgr, zone_masks_photo, zone_names, png_size)
    if not cv2.imwrite(str(out / "skin_zone_overlay.png"), overlay):
        raise OSError(f"failed to write skin_zone_overlay.png to {out}")

    return {
        "skin_zone_projection": "skin_zone_projection.npz",
        "skin_zone_quality": "skin_zone_quality.json",
        "skin_zone_overlay": "skin_zone_overlay.png",
    }


def _render_overlay(bgr: np.ndarray, zone_masks: dict[str, np.ndarray], zone_names: list[str], png_size: int) -> np.ndarray:
    """Наложить зоны (полупрозрачно) поверх уменьшенного фото для проверки."""
    H, W = bgr.shape[:2]
    thumb = cv2.resize(bgr, (png_size, png_size)) if (W, H) != (png_size, png_size) else bgr.copy()
    overlay = thumb.astype(np.float32) * 0.6
    colors = _zone_colors(len(zone_names))
    for i, name in enumerate(zone_names):
        m = zone_masks[name]
        if not np.any(m):
            continue
        m_small = cv2.resize(m.astype(np.uint8), (png_size, png_size)) > 0
        c = np.array(colors[i], np.float32)
        overlay[m_small] = overlay[m_small] * 0.4 + c * 0.6
    return overlay.astype(np.uint8)


# 📤 Имена зон атласа
def zone_names() -> list[str]:
    return [s["name"] for s in ZONE_SPECS]
