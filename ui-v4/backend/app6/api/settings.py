"""⚙️ CONFIG → Персистентные пользовательские настройки UI (`/api/v1/settings`).

Хранит пороги тепловой карты, выбранные метрики и т.д. в одном JSON-файле
на диске (`runs/api_settings.json`, вне git — см. `.gitignore`). Не хранит
ничего специфичного для конкретного результата анализа: это UI-preferences,
а не evidence.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SETTINGS_SCHEMA = "deeputin-api-settings-v1.0"

#: Пороги тепловой карты по умолчанию (доли шкалы 0..1), как описано в ТЗ:
#: 0–25% — только сине-голубой переход; 25–50% — переход в зелёный;
#: 50–75% — зелёный→красный (от яркого до тёмно-красного);
#: 75–100% — тёмно-красный без дальнейшего перехода.
DEFAULT_SETTINGS: dict[str, Any] = {
    "schema": SETTINGS_SCHEMA,
    "heatmap": {
        "stop_blue_cyan": 0.25,
        "stop_cyan_green": 0.50,
        "stop_green_red": 0.75,
        "stop_saturated_red": 1.0,
        "max_residual_reference": 0.12,
    },
    # Пороги классификации смещения ОДНОЙ ключевой точки. Значения по
    # умолчанию — стартовая точка для калибровки, а НЕ установленная норма:
    # допустимый разброс зависит от ракурса и качества съёмки и должен
    # уточняться по калибровочному набору (`app6/AGENTS.md`).
    # Градиент тепловой карты с ПОСЕГМЕНТНОЙ резкостью перехода.
    # `sharpness` задаёт характер перехода ОТ остановки к следующей:
    # 0 — плавно (внутри допустимой изменчивости), 1 — ступенька (на границе
    # аномалии, где важно мгновенно различить «ниже/выше порога»).
    # Прежние `heatmap.stop_*` сохранены для обратной совместимости.
    "gradient": {
        "max_reference": 0.12,
        "stops": [
            {"position": 0.00, "color": "#1d4ed8", "sharpness": 0.00, "label": "норма"},
            {"position": 0.25, "color": "#22d3ee", "sharpness": 0.15, "label": "верх нормы"},
            {"position": 0.50, "color": "#facc15", "sharpness": 0.55, "label": "внимание"},
            {"position": 0.75, "color": "#ef4444", "sharpness": 0.85, "label": "аномалия"},
            {"position": 1.00, "color": "#7f1d1d", "sharpness": 0.00, "label": "предел"},
        ],
    },
    "landmark_shift": {
        # ≤ tolerance — в пределах внутрисубъектной изменчивости
        "tolerance": 0.02,
        # tolerance..suspect — заметное смещение, требует внимания
        "suspect": 0.05,
        # > suspect — аномальное смещение
        "calibrated": False,   # порог подтверждён калибровкой?
    },
    "thresholds": {
        "confidence_min": 0.0,
        "quality_min": 0.0,
        "geometry_zone_delta_limit": 0.018,
        "texture_zone_delta_limit": 0.04,
        "expression_smile": 0.92,
        "expression_jaw_open": 0.28,
    },
    "detail_level": "standard",
    "language": "ru",
}


def _settings_path(project_root: Path) -> Path:
    # Runtime registry is the single mutable settings location. project_root is
    # retained for API compatibility but no longer forces a macOS-only path.
    from .runtime_config import ensure_runtime_write_dirs, load_runtime_paths

    paths = load_runtime_paths()
    ensure_runtime_write_dirs(paths)
    return paths.settings_path


def load_settings(project_root: Path) -> dict[str, Any]:
    path = _settings_path(project_root)
    if not path.is_file():
        return dict(DEFAULT_SETTINGS)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SETTINGS)
    if not isinstance(stored, dict):
        return dict(DEFAULT_SETTINGS)
    # 🔀 Слияние с умолчаниями: файл настроек, сохранённый прежней версией, не
    # содержит новых секций. Без слияния такие ключи приходили бы как None, и
    # интерфейс получал бы "настройка отсутствует" вместо значения по
    # умолчанию — с порогами это означало бы молчаливую потерю классификации.
    merged = dict(DEFAULT_SETTINGS)
    for key, value in stored.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            section = dict(merged[key])
            section.update(value)
            merged[key] = section
        else:
            merged[key] = value
    return merged


def save_settings(project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("settings payload must be an object")
    merged = load_settings(project_root)
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    shift = merged.get("landmark_shift") or {}
    tolerance = float(shift.get("tolerance", 0.02))
    suspect = float(shift.get("suspect", 0.05))
    if not math.isfinite(tolerance) or not math.isfinite(suspect) or tolerance < 0 or suspect <= tolerance:
        raise ValueError("landmark_shift requires finite values with suspect > tolerance >= 0")
    merged["landmark_shift"] = {"tolerance": tolerance, "suspect": suspect, "calibrated": bool(shift.get("calibrated", False))}
    merged["schema"] = SETTINGS_SCHEMA
    path = _settings_path(project_root)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged
