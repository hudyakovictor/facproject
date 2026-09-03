"""🔗 Мост к приватному слою legacy-гипотез (дефект D12).

В `app6/private_hypothesis_seed/` лежат 6223 записи предыдущей реализации, из
которых ретестировано 0. Одна из причин — расхождение словарей ракурсов: шесть
из девяти бинов назывались иначе, поэтому сопоставление по `bucket` не давало
совпадений.

Модуль решает только задачу соответствия имён и учёта различий пространства
выравнивания. Он **не** переносит старые пороги, постериоры и диапазоны:
legacy-числа считались при `reference_use_mesh_alignment=false`, тогда как
текущий пайплайн использует `iteratively_trimmed_kabsch_v1_no_scale`.

🚨 WARNING: legacy-записи — цели перепроверки, а не источник истины. Любой
диапазон должен быть пересчитан на текущей калибровке (см. PRIVATE_HYPOTHESIS_LAYER.md).
"""
from __future__ import annotations

from typing import Any, Final

LEGACY_BRIDGE_SCHEMA: Final[str] = "deeputin-legacy-bridge-v1.0"

#: Соответствие имён ракурсов: legacy → текущее. Проверено по составу датасетов.
LEGACY_TO_CURRENT_BIN: Final[dict[str, str]] = {
    "frontal": "frontal",
    "left_profile": "left_profile",
    "right_profile": "right_profile",
    "left_threequarter_light": "left_light",
    "right_threequarter_light": "right_light",
    "left_threequarter_mid": "left_mid",
    "right_threequarter_mid": "right_mid",
    "left_threequarter_deep": "left_deep",
    "right_threequarter_deep": "right_deep",
}

CURRENT_TO_LEGACY_BIN: Final[dict[str, str]] = {v: k for k, v in LEGACY_TO_CURRENT_BIN.items()}

#: Пространство выравнивания legacy несовместимо с текущим.
LEGACY_ALIGNMENT: Final[str] = "reference_use_mesh_alignment=false"
CURRENT_ALIGNMENT: Final[str] = "iteratively_trimmed_kabsch_v1_no_scale"

#: Поля legacy, которые запрещено использовать как текущую калибровку.
NON_TRANSFERABLE_FIELDS: Final[frozenset[str]] = frozenset({
    "full_posterior", "posterior_raw", "posterior_before_cap", "posterior_after_cap",
    "confidence", "identity_stress_score", "carrier_mass", "anomaly_ratio_max",
})


def normalize_pose_bin(bucket: str) -> str | None:
    """🔄 Привести имя ракурса legacy к текущему словарю.

    Returns:
        Текущее имя бина либо None, если соответствие неизвестно.
    """
    key = str(bucket or "").strip()
    if key in LEGACY_TO_CURRENT_BIN:
        return LEGACY_TO_CURRENT_BIN[key]
    return key if key in CURRENT_TO_LEGACY_BIN else None


def normalize_photo_id(photo_id: str) -> str:
    """🔄 Привести legacy photo_id к каноническому виду `YYYY_MM_DD[_N]`.

    Legacy содержит формы `1999_08_12 (2)` и `1999_08_16(2)`; `parse_photo_name`
    их принимает, но текущие идентификаторы записываются с подчёркиванием.
    """
    from pathlib import Path

    from app6.stage1.naming import parse_photo_name

    raw = str(photo_id or "").strip()
    if not raw:
        return raw
    try:
        return parse_photo_name(Path(f"{raw}.jpg")).canonical_stem
    except Exception:
        return raw


def build_retest_target(legacy_record: dict[str, Any]) -> dict[str, Any]:
    """🏭 FACTORY → Превратить legacy-запись в цель ретеста.

    Числовые поля из `NON_TRANSFERABLE_FIELDS` сохраняются только как
    провенанс с явной пометкой, что они не являются текущей калибровкой.
    """
    payload = legacy_record.get("payload") if "payload" in legacy_record else legacy_record
    if not isinstance(payload, dict):
        payload = {}

    bucket = payload.get("bucket")
    photo_id = payload.get("photo_id")
    historical = {k: payload[k] for k in NON_TRANSFERABLE_FIELDS if k in payload}

    return {
        "schema": LEGACY_BRIDGE_SCHEMA,
        "source": legacy_record.get("source"),
        "legacy_photo_id": photo_id,
        "photo_id": normalize_photo_id(photo_id) if photo_id else None,
        "legacy_bucket": bucket,
        "pose_bin": normalize_pose_bin(bucket) if bucket else None,
        "date": str(payload.get("date_str") or "")[:10] or None,
        "year": payload.get("year"),
        "retest_status": "pending_current_data",
        "historical_values": historical,
        "historical_alignment": LEGACY_ALIGNMENT,
        "current_alignment": CURRENT_ALIGNMENT,
        "range_policy": "исторические значения не переносятся; диапазоны "
                        "пересчитываются на текущей калибровке",
    }


def bridge_coverage(legacy_buckets: list[str]) -> dict[str, Any]:
    """📤 Оценить, какая доля legacy-ракурсов сопоставима с текущими."""
    total = len(legacy_buckets)
    mapped = sum(1 for b in legacy_buckets if normalize_pose_bin(b) is not None)
    unmapped = sorted({b for b in legacy_buckets if normalize_pose_bin(b) is None})
    return {"schema": LEGACY_BRIDGE_SCHEMA, "record_count": total,
            "mapped_count": mapped, "unmapped_count": total - mapped,
            "coverage_fraction": (mapped / total) if total else 0.0,
            "unmapped_examples": unmapped[:10],
            "bin_mapping": dict(LEGACY_TO_CURRENT_BIN)}
