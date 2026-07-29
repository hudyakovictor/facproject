"""🗂 CATALOG → Нормативное распределение ключей пайплайна по разделам интерфейса.

Модуль решает ровно одну задачу: сопоставить каждому ключу, который пайплайн
уже сохранил на диск, **место в интерфейсе**. До него 289 ключей (162 колонки
`pair_metrics.csv`, 36 ключей `analysis_manifest.json`, 73 листовых ключа
Stage 1 `info.json`, 14 артефактов Stage 2) не покидали диск — см.
`ui/PIPELINE_KEYS_GAP.md` и `ui/KEYS_PLACEMENT_MAP.md`.

Категории (совпадают с `ui/KEYS_PLACEMENT_MAP.md`):

  * ``A`` — статистическая достоверность и корроборация;
  * ``B`` — mesh-канал;
  * ``C`` — качество кадра и применимость пары;
  * ``D`` — точки, дескрипторы, выравнивание;
  * ``E`` — текстура и структура кожи;
  * ``F`` — хронология, темп, лиды;
  * ``G`` — провенанс и воспроизводимость;
  * ``H`` — артефакты Stage 1 (маски, UV, файлы);
  * ``I`` — сводка прогона и ограничения.

🚨 WARNING: модуль НИЧЕГО не вычисляет. Он только классифицирует и приводит
типы. Любое отсутствующее значение остаётся ``None`` — `app6/AGENTS.md`
запрещает подставлять ноль вместо пропуска.

📤 API: categorize_pair_columns(), CATEGORY_TITLES, KEY_GROUPS
"""
from __future__ import annotations

import re
from typing import Any

KEY_CATALOG_SCHEMA = "deeputin-api-key-catalog-v1.0"

#: Человекочитаемые названия категорий (ru/en) — единственный источник
#: подписей для заголовков разделов интерфейса.
CATEGORY_TITLES: dict[str, dict[str, str]] = {
    "A": {"ru": "Статзначимость", "en": "Statistical significance"},
    "B": {"ru": "Меш", "en": "Mesh"},
    "C": {"ru": "Качество и применимость", "en": "Quality and applicability"},
    "D": {"ru": "Точки и дескрипторы", "en": "Points and descriptors"},
    "E": {"ru": "Текстура", "en": "Texture"},
    "F": {"ru": "Хронология", "en": "Chronology"},
    "G": {"ru": "Провенанс", "en": "Provenance"},
    "H": {"ru": "Артефакты кадра", "en": "Frame artifacts"},
    "I": {"ru": "Сводка прогона", "en": "Run summary"},
}

#: Подгруппы внутри категории: ключ → (категория, подгруппа).
#: Порядок проверки важен — более длинные префиксы идут раньше.
_PREFIX_RULES: tuple[tuple[str, str, str], ...] = (
    # --- A: статзначимость -------------------------------------------------
    ("mt_", "A", "multiple_testing"),
    ("cross_bin_", "A", "corroboration"),
    ("primary_", "A", "primary"),
    ("matched_calibration", "A", "primary"),
    ("calibration_limit", "A", "limits"),
    ("pose_leakage", "A", "limits"),
    # --- B: меш ------------------------------------------------------------
    ("mesh_point_to_plane_", "B", "point_to_plane"),
    ("mesh_alignment_", "B", "alignment"),
    ("mesh_anchor_", "B", "alignment"),
    ("mesh_calibrat", "B", "calibration"),
    ("mesh_max_robust_z", "B", "calibration"),
    ("mesh_rmse", "B", "point_to_point"),
    ("mesh_median", "B", "point_to_point"),
    ("mesh_p95", "B", "point_to_point"),
    ("mesh_visible_fraction", "B", "coverage"),
    ("mesh_common_vertex_count", "B", "coverage"),
    ("mesh_fit_vertex_count", "B", "coverage"),
    ("mesh_zone_source", "B", "zones"),
    ("mesh_anatomical_zone_count", "B", "zones"),
    ("mesh_space_", "B", "space"),
    ("mesh_file", "B", "artifact"),
    ("mesh_status", "B", "status"),
    ("mesh_evidence_level", "B", "status"),
    # --- C: качество и применимость ---------------------------------------
    ("quality_zone_", "C", "zone_coverage"),
    ("quality_", "C", "frame_quality"),
    ("expression_", "C", "expression"),
    ("alignment_quality_", "C", "frame_quality"),
    ("forehead_wrinkle_supported", "C", "applicability"),
    # --- D: точки и дескрипторы -------------------------------------------
    ("descriptor_", "D", "descriptors"),
    ("ldm134_", "D", "anchors"),
    ("ldm106_", "D", "anchors"),
    ("anchor106", "D", "anchors"),
    ("anchor134", "D", "anchors"),
    ("alignment106", "D", "alignment"),
    ("alignment134", "D", "alignment"),
    ("rotation1", "D", "residual_transform"),
    ("translation1", "D", "residual_transform"),
    ("pose_distance", "D", "residual_transform"),
    ("significant_point", "D", "point_motion"),
    ("coherent_motion", "D", "point_motion"),
    ("median_point_z", "D", "point_motion"),
    ("p95_point_z", "D", "point_motion"),
    ("point_motion_status", "D", "point_motion"),
    ("common_visible", "D", "coverage"),
    ("coverage1", "D", "coverage"),
    ("motion_file", "D", "artifact"),
    # --- E: текстура -------------------------------------------------------
    ("texture_structure_", "E", "structure"),
    ("texture_image_backend", "E", "provenance"),
    ("texture_image_schema", "E", "provenance"),
    ("texture_image_max_", "E", "channels"),
    ("texture_image_", "E", "status"),
    # --- F: хронология -----------------------------------------------------
    ("chronology_rate_", "F", "rate"),
    ("biological_rate_", "F", "rate"),
    ("biological_reason", "F", "rate"),
    ("time_weighted_", "F", "rate"),
    ("days_delta", "F", "rate"),
    ("alpha_exp_", "F", "identity_vs_expression"),
    ("alpha_id_", "F", "identity_vs_expression"),
    ("identity_only_", "F", "identity_vs_expression"),
    ("lead_", "F", "leads"),
    ("date_status", "F", "date"),
    # --- G: провенанс ------------------------------------------------------
    ("source_", "G", "source"),
    ("pair_", "G", "pair_identity"),
    ("date_a", "G", "pair_identity"),
    ("date_b", "G", "pair_identity"),
)

#: Ключи, которые остаются в «шапке» пары и уже показываются интерфейсом.
_HEADER_KEYS = frozenset({"photo_a", "photo_b", "pose_bin", "status", "evidence_state"})


def category_for(column: str) -> tuple[str, str]:
    """🔍 QUERY → (категория, подгруппа) для колонки `pair_metrics.csv`.

    Неизвестные колонки попадают в ``("I", "other")`` — это осознанный
    fallback: новая колонка Stage 2 окажется видимой в сводке прогона,
    а не исчезнет молча.
    """
    if column in _HEADER_KEYS:
        return ("A", "header")
    for prefix, category, group in _PREFIX_RULES:
        if column.startswith(prefix):
            return (category, group)
    return ("I", "other")


_TRUE = {"true", "1", "yes"}
_FALSE = {"false", "0", "no"}
_MISSING = {"", "nan", "none", "null", "na"}


def coerce(raw: Any) -> Any:
    """🔄 TRANSFORM → Привести CSV-строку к JSON-типу без потери «нет данных».

    Пустая строка, ``nan``, ``none`` → ``None``. Ноль вместо пропуска не
    подставляется никогда.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if text.lower() in _MISSING:
        return None
    low = text.lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    try:
        value = float(text)
    except ValueError:
        return text
    if value != value:  # NaN
        return None
    if value.is_integer() and abs(value) < 1e15 and re.fullmatch(r"-?\d+", text):
        return int(value)
    return value


def categorize_pair_columns(row: dict[str, Any]) -> dict[str, Any]:
    """🏭 FACTORY → Разложить строку `pair_metrics.csv` по категориям A–I.

    Args:
        row: одна строка CSV (как отдаёт `csv.DictReader`).

    Returns:
        ``{"A": {"multiple_testing": {...}, ...}, "B": {...}, ...}`` —
        только непустые категории; значения приведены к JSON-типам,
        отсутствующие остаются ``None``.
    """
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for column, raw in row.items():
        category, group = category_for(column)
        out.setdefault(category, {}).setdefault(group, {})[column] = coerce(raw)
    return out


# --- Stage 1 `info.json` ----------------------------------------------------

#: Корневые ветви `info.json` → категория интерфейса.
_STAGE1_ROOTS: dict[str, tuple[str, str]] = {
    "quality_inputs": ("C", "frame_inputs"),
    "quality_summary": ("C", "frame_summary"),
    "reprojection": ("H", "reprojection"),
    "mask": ("H", "mask"),
    "uv": ("H", "uv"),
    "files": ("H", "files"),
    "camera": ("G", "camera"),
    "normalization": ("G", "normalization"),
    "crop": ("G", "crop"),
    "image": ("G", "image"),
    "pose": ("C", "pose"),
    "landmark_contract": ("D", "contract"),
}

#: Скалярные ключи верхнего уровня `info.json`.
_STAGE1_SCALARS: dict[str, tuple[str, str]] = {
    "photo_id": ("G", "source"),
    "source_filename": ("G", "source"),
    "source_relative_path": ("G", "source"),
    "source_sha256": ("G", "source"),
    "code_hash": ("G", "reproducibility"),
    "config_hash": ("G", "reproducibility"),
    "model_hash": ("G", "reproducibility"),
    "schema_version": ("G", "reproducibility"),
    "extraction_timestamp": ("G", "reproducibility"),
    "date": ("G", "date"),
    "date_year": ("G", "date"),
    "date_month": ("G", "date"),
    "date_day": ("G", "date"),
    "same_date_sequence": ("G", "date"),
}


def categorize_stage1_info(info: dict[str, Any]) -> dict[str, Any]:
    """🏭 FACTORY → Разложить `info.json` одного фото по категориям C/D/G/H.

    Вложенные ветви сохраняются целиком (не уплощаются): интерфейс рендерит
    их как «ключ → значение» рекурсивно, поэтому новая подветвь Stage 1
    появится на экране без изменения кода UI.
    """
    out: dict[str, dict[str, Any]] = {}
    for key, value in info.items():
        if key in _STAGE1_ROOTS:
            category, group = _STAGE1_ROOTS[key]
        elif key in _STAGE1_SCALARS:
            category, group = _STAGE1_SCALARS[key]
        else:
            category, group = ("H", "other")
        bucket = out.setdefault(category, {}).setdefault(group, {})
        if key in _STAGE1_ROOTS and isinstance(value, dict):
            bucket.update(value)
        else:
            bucket[key] = value
    return out


# --- `analysis_manifest.json` (уровень прогона) -----------------------------

_MANIFEST_RULES: dict[str, tuple[str, str]] = {
    "calibration_limited_pair_count": ("A", "coverage"),
    "multiple_testing_pair_count": ("A", "coverage"),
    "pose_leakage_status": ("A", "pose_leakage"),
    "pose_leakage_flagged_metrics": ("A", "pose_leakage"),
    "pose_leakage_limited_pair_count": ("A", "pose_leakage"),
    "calibration_sensitivity_status": ("A", "sensitivity"),
    "mesh_pair_count": ("B", "coverage"),
    "mesh_zone_count": ("B", "coverage"),
    "mesh_calibration_pair_count": ("B", "coverage"),
    "mesh_calibration_status": ("B", "coverage"),
    "quality_zone_pair_count": ("C", "coverage"),
    "point_motion_pair_count": ("D", "coverage"),
    "descriptor_family_count": ("D", "coverage"),
    "texture_pair_count": ("E", "coverage"),
    "texture_zone_metric_count": ("E", "coverage"),
    "alpha_chronology_event_count": ("F", "events"),
    "baseline_return_count": ("F", "events"),
    "change_point_count": ("F", "events"),
    "lead_date_count": ("F", "leads"),
    "lead_metric_count": ("F", "leads"),
    "lead_overlap_pair_count": ("F", "leads"),
    "lead_registry_status": ("F", "leads"),
    "config_hash": ("G", "reproducibility"),
    "schema_version": ("G", "reproducibility"),
    "created_at_utc": ("G", "reproducibility"),
    "elapsed_seconds": ("G", "reproducibility"),
    "stage1_manifest_digest": ("G", "integrity"),
    "artifact_hashes": ("G", "integrity"),
}


def categorize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """🏭 FACTORY → Разложить `analysis_manifest.json` по категориям.

    Всё, для чего нет явного правила (счётчики записей, `limitations`,
    `skipped_pair_counts`, `postprocess_summary`), попадает в категорию ``I``
    — «Сводка прогона», где и должно быть по карте размещения.
    """
    out: dict[str, dict[str, Any]] = {}
    for key, value in manifest.items():
        category, group = _MANIFEST_RULES.get(key, ("I", "summary"))
        out.setdefault(category, {}).setdefault(group, {})[key] = value
    return out


#: Артефакты Stage 2 → раздел интерфейса, который их читает.
#: Значение — (категория, человекочитаемое назначение).
ARTIFACT_PLACEMENT: dict[str, tuple[str, str]] = {
    "multiple_testing": ("A", "Таблица q-value по всем парам"),
    "cross_bin_corroboration": ("A", "Матрица подтверждений по ракурсам"),
    "pose_leakage_diagnostic": ("A", "Диагностика утечки позы"),
    "calibration_sensitivity": ("A", "Устойчивость к составу калибровки"),
    "analysis_validation": ("A", "Валидация схемы прогона"),
    "evidence_packets": ("A", "Пакеты доказательств"),
    "mesh_noise_model": ("B", "Модель шума меша"),
    "zone_map": ("B", "Карта зон меша"),
    "change_points": ("F", "Точки перелома хронологии"),
    "alpha_chronology": ("F", "Хронология alpha-коэффициентов"),
    "chronology_rate_model": ("F", "Модель темпа изменений"),
    "lead_registry": ("F", "Реестр лидов"),
    "baseline_return": ("F", "Возвраты к базовой линии"),
    "cumulative_drift": ("F", "Накопленный дрейф"),
    "pair_details": ("G", "Детали пар для выгрузки"),
    "technical_summary": ("I", "Технический отчёт прогона"),
    "metric_catalog": ("I", "Каталог метрик (источник подписей)"),
    "calibration_noise_model": ("A", "Модель углового шума"),
    "analysis_manifest": ("I", "Манифест прогона"),
}
