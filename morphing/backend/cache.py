"""LRU-кэш для результатов 3D-реконструкции.

Позволяет избежать повторной реконструкции одного и того же фото
при последовательных вызовах /api/morph-pair, /api/forensic-score,
/api/export-gif и других эндпоинтов.

Размер кэша: 20 последних реконструкций (~400 MB VRAM при cpu-режиме).
"""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path
from typing import Any

from cachetools import LRUCache

# Корень проекта
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app8.reconstruction import reconstruct_image

# 20 лиц × ~20 MB на реконструкцию = до 400 MB RAM
_recon_cache: LRUCache = LRUCache(maxsize=20)


def file_sha256(file_bytes: bytes) -> str:
    """SHA-256 хэш байтов файла — ключ кэша."""
    return hashlib.sha256(file_bytes).hexdigest()


def cached_reconstruct(file_bytes: bytes, device: str = "cpu") -> dict[str, Any] | None:
    """Реконструкция с кэшированием по SHA-256 хэшу входного файла.

    Args:
        file_bytes: Байты изображения (JPEG/PNG).
        device: Устройство для вычислений ('cpu' или 'cuda').

    Returns:
        Словарь с результатами реконструкции или None если лицо не найдено.
        Повторный вызов с теми же байтами вернёт кэшированный результат мгновенно.
    """
    key = file_sha256(file_bytes)

    if key not in _recon_cache:
        result = reconstruct_image(io.BytesIO(file_bytes), device=device)
        if result is not None:
            _recon_cache[key] = result
        return result

    return _recon_cache[key]


def cache_info() -> dict[str, int]:
    """Статистика кэша для /api/health."""
    return {
        "cached_reconstructions": len(_recon_cache),
        "max_size": _recon_cache.maxsize,
    }


def cache_clear() -> None:
    """Очистка кэша (например, при нехватке памяти)."""
    _recon_cache.clear()
