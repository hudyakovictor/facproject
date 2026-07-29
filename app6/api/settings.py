"""⚙️ CONFIG → Персистентные пользовательские настройки UI (`/api/v1/settings`).

Хранит пороги тепловой карты, выбранные метрики и т.д. в одном JSON-файле
на диске (`runs/api_settings.json`, вне git — см. `.gitignore`). Не хранит
ничего специфичного для конкретного результата анализа: это UI-preferences,
а не evidence.
"""
from __future__ import annotations

import json
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
    path = project_root / "runs" / "api_settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_settings(project_root: Path) -> dict[str, Any]:
    path = _settings_path(project_root)
    if not path.is_file():
        return dict(DEFAULT_SETTINGS)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_SETTINGS)


def save_settings(project_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    merged = {**DEFAULT_SETTINGS, **payload, "schema": SETTINGS_SCHEMA}
    path = _settings_path(project_root)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged
