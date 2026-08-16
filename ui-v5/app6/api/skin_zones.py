"""🚪 API-слой → Per-zone кожа/качество из УЖЕ СОХРАНЁННЫХ артефактов Stage 1.

Модуль ничего не вычисляет заново: он читает то, что Stage 1 положил на диск
рядом с фотографией, и приводит к одному контракту для интерфейса.

Источники (см. `info.json → files`):
  * `skin_zone_quality.json` — статус зоны (`active` / исключена), причины
    исключения, `visible_fraction`, число кожных пикселей, bbox;
  * `quality.json` — `per_zone_quality` (laplacian_var, tenengrad_mean,
    highlight/shadow fraction, texture_score_0_1, quality_class) и
    `global_texture_quality` / `mask_quality`;
  * `wrinkle_zones.json` — зоны морщин, когда соответствующий модуль включён.

🚨 WARNING: новый анализ кожи здесь НЕ выполняется (требование заказчика:
"не надо делать дополнительные анализы кожи, тех что уже сохраняется
в texture.json/csv достаточно"). Если Stage 1 не сохранил канал — поле
возвращается как `null`, а зона получает статус `no_data`. Ноль вместо
пропуска не подставляется: `app6/AGENTS.md` прямо запрещает заменять
отсутствующие данные числом ради красивой картинки.

📤 API: load_skin_zone_report(), SKIN_ZONES_SCHEMA
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SKIN_ZONES_SCHEMA = "deeputin-api-skin-zones-v1.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# This is the versioned 40-zone v4 atlas used by the current 3DDFA pipeline.
# Keep the API catalogue tied to the same source instead of an obsolete
# `app6/atlas` location, which is not part of this checkout.
ATLAS_PATH = PROJECT_ROOT / "3ddfa_v3" / "atlas" / "skin_zone_atlas.json"

#: Статусы зоны в отчёте. `no_data` — Stage 1 не сохранил канал для этой зоны;
#: это НЕ то же самое, что "зона в норме".
ZONE_STATUSES = ("active", "excluded", "no_data")

_atlas_cache: dict[str, Any] | None = None


def _load_atlas() -> dict[str, Any]:
    """🔍 QUERY → Атлас зон кожи (единственный источник имён/групп/исключений)."""
    global _atlas_cache
    if _atlas_cache is None:
        _atlas_cache = json.loads(ATLAS_PATH.read_text(encoding="utf-8"))
    return _atlas_cache


def zone_catalog() -> list[dict[str, Any]]:
    """📤 Плоский каталог зон атласа для легенды интерфейса.

    Веса зон намеренно НЕ выдумываются: атлас (`skin_zone_atlas.json`) их не
    содержит, а придумывать их в API означало бы подменить нормативную схему
    (`app6/AGENTS.md`: "Вес зоны задаётся атласом и не должен произвольно
    меняться в коде"). Отдаётся то, что в атласе реально есть.
    """
    atlas = _load_atlas()
    excluded_by_segmentation = set(atlas.get("segmentation_excluded_zones") or [])
    return [
        {
            "zone_id": zone["zone_id"],
            "name": zone["name"],
            "label_ru": zone.get("label_ru") or zone["name"],
            "group": zone.get("group"),
            "side": zone.get("side"),
            "seed_uv": zone.get("seed_uv"),
            "scale_uv": zone.get("scale_uv"),
            # Зона, которую сегментация исключает всегда (веки, губы):
            # мягкие ткани, сильно зависящие от мимики.
            "excluded_by_segmentation": bool(
                zone.get("excluded_by_segmentation") or zone["name"] in excluded_by_segmentation
            ),
        }
        for zone in atlas.get("zones", [])
    ]


def _read_json(path: Path) -> dict[str, Any] | None:
    """🔍 QUERY → Прочитать JSON-артефакт Stage 1, если он есть и валиден."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _float_or_none(value: Any) -> float | None:
    """Привести к float, сохраняя `None` для отсутствующих значений."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None  # NaN → None


def load_skin_zone_report(photo_dir: Path) -> dict[str, Any]:
    """🏭 FACTORY → Собрать per-zone отчёт кожи из артефактов одного фото.

    Args:
        photo_dir: каталог Stage 1 для конкретного `photo_id`.

    Returns:
        Отчёт с ключами `zones`, `global_texture_quality`, `mask_quality`,
        `available_sources`. Поля, которых нет на диске, равны `None`, а не
        нулю или выдуманному значению.
    """
    photo_dir = Path(photo_dir)
    skin = _read_json(photo_dir / "skin_zone_quality.json") or {}
    quality = _read_json(photo_dir / "quality.json") or {}
    wrinkles = _read_json(photo_dir / "wrinkle_zones.json") or {}

    skin_zones: dict[str, Any] = skin.get("zones") or {}
    per_zone_quality: dict[str, Any] = quality.get("per_zone_quality") or {}
    wrinkle_zones: dict[str, Any] = wrinkles.get("zones") or {}

    catalog = {entry["name"]: entry for entry in zone_catalog()}
    # Имена зон в quality.json (`forehead_L`) и в атласе (`forehead_left`)
    # различаются исторически — сопоставляем по обоим написаниям, не теряя
    # данные и не выдумывая соответствий там, где их нет.
    quality_aliases = {
        name.replace("_L", "_left").replace("_R", "_right"): payload
        for name, payload in per_zone_quality.items()
    }

    zones: list[dict[str, Any]] = []
    observed_names = set(skin_zones) | set(catalog) | set(quality_aliases)
    for name in sorted(observed_names):
        entry = catalog.get(name, {})
        skin_entry = skin_zones.get(name) or {}
        quality_entry = per_zone_quality.get(name) or quality_aliases.get(name) or {}

        raw_status = str(skin_entry.get("status") or "").lower()
        if raw_status == "active":
            status = "active"
        elif raw_status:
            status = "excluded"
        elif quality_entry:
            status = "active"
        else:
            status = "no_data"

        exclusion_reasons = list(skin_entry.get("exclusion_reasons") or [])
        if entry.get("excluded_by_segmentation") and "segmentation_excluded" not in exclusion_reasons:
            exclusion_reasons.append("segmentation_excluded")

        zones.append({
            "zone_id": entry.get("zone_id"),
            "name": name,
            "label_ru": entry.get("label_ru") or name,
            "group": entry.get("group"),
            "side": entry.get("side"),
            "status": status,
            "exclusion_reasons": exclusion_reasons,
            # --- из skin_zone_quality.json ---
            "visible_fraction": _float_or_none(skin_entry.get("visible_fraction")),
            "skin_pixels": skin_entry.get("skin_pixels"),
            "quality": _float_or_none(skin_entry.get("quality")),
            "bbox_original": skin_entry.get("bbox_original"),
            # --- из quality.json → per_zone_quality ---
            "texture_score": _float_or_none(quality_entry.get("texture_score_0_1")),
            "texture_usable": quality_entry.get("texture_usable"),
            "quality_class": quality_entry.get("quality_class"),
            "laplacian_var": _float_or_none(quality_entry.get("laplacian_var")),
            "tenengrad_mean": _float_or_none(quality_entry.get("tenengrad_mean")),
            "highlight_fraction": _float_or_none(quality_entry.get("highlight_fraction")),
            "shadow_fraction": _float_or_none(quality_entry.get("shadow_fraction")),
            "skin_fraction": _float_or_none(quality_entry.get("skin_fraction")),
            "texture_pixels": quality_entry.get("texture_pixels"),
            "roi_source": quality_entry.get("roi_source"),
            # --- из wrinkle_zones.json (если модуль включён) ---
            "wrinkle": wrinkle_zones.get(name),
        })

    return {
        "schema": SKIN_ZONES_SCHEMA,
        "not_a_verdict": True,
        "pose_bin": skin.get("pose_bin") or (quality.get("pose") or {}).get("pose_bin"),
        "skin_mask_coverage": _float_or_none(skin.get("skin_mask_coverage")),
        "global_texture_quality": quality.get("global_texture_quality"),
        "mask_quality": quality.get("mask_quality"),
        "zone_count": len(zones),
        "active_zone_count": sum(1 for z in zones if z["status"] == "active"),
        "excluded_zone_count": sum(1 for z in zones if z["status"] == "excluded"),
        "no_data_zone_count": sum(1 for z in zones if z["status"] == "no_data"),
        "zones": zones,
        # Честный перечень того, что реально нашлось на диске: интерфейс
        # обязан показать пользователю, из чего построен отчёт.
        "available_sources": {
            "skin_zone_quality": bool(skin_zones),
            "per_zone_quality": bool(per_zone_quality),
            "wrinkle_zones": bool(wrinkle_zones),
            "wrinkle_note": wrinkles.get("note"),
        },
    }
