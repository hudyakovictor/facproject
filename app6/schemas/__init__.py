"""JSON-схемы контрактов app6.

P3.17 (DEV_FIX_TZ): пакет получил `__init__.py`, чтобы схемы можно было
адресовать через `importlib.resources` и чтобы каталог не выглядел как
случайная папка с данными вне пакета.
"""
from __future__ import annotations

from pathlib import Path

SCHEMAS_DIR = Path(__file__).resolve().parent


def schema_path(name: str) -> Path:
    """🔍 QUERY → Путь к файлу схемы по имени (`confounders_v1.json` и т.п.)."""
    candidate = SCHEMAS_DIR / name
    if not candidate.is_file():
        available = sorted(p.name for p in SCHEMAS_DIR.glob("*.json"))
        raise FileNotFoundError(f"схема {name!r} не найдена; доступны: {available}")
    return candidate
