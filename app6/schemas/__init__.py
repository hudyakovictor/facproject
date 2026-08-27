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
    basename = Path(name).name
    if basename != name or not basename.endswith(".json"):
        raise FileNotFoundError(f"схема {name!r} не найдена; доступны только JSON в каталоге схем")
    candidate = (SCHEMAS_DIR / basename).resolve()
    try:
        candidate.relative_to(SCHEMAS_DIR)
    except ValueError as exc:
        raise FileNotFoundError(f"схема {name!r} вне каталога схем") from exc
    if not candidate.is_file():
        available = sorted(p.name for p in SCHEMAS_DIR.glob("*.json"))
        raise FileNotFoundError(f"схема {name!r} не найдена; доступны: {available}")
    return candidate
