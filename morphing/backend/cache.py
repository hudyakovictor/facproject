"""🗃️ LRU-кэш 3D-реконструкций по SHA-256 хэшу файла.

Позволяет многократно использовать результат reconstruct_image
для одного и того же фото без повторных вычислений.
"""
from __future__ import annotations
import hashlib
import io
import sys
from pathlib import Path
from typing import Any

try:
    from cachetools import LRUCache
except ImportError:  # Fallback: простой dict с ограничением
    class LRUCache(dict):  # type: ignore
        def __init__(self, maxsize: int = 20):
            super().__init__()
            self._maxsize = maxsize
            self._order: list[str] = []

        def __setitem__(self, key: str, value: Any) -> None:
            if key in self:
                self._order.remove(key)
            elif len(self) >= self._maxsize:
                oldest = self._order.pop(0)
                super().__delitem__(oldest)
            super().__setitem__(key, value)
            self._order.append(key)


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app8.reconstruction import reconstruct_image  # noqa: E402

_recon_cache: LRUCache = LRUCache(maxsize=20)


def cached_reconstruct(file_bytes: bytes, device: str = "cpu") -> Any | None:
    """Реконструирует 3D-лицо из байтов, используя LRU-кэш по SHA-256 хэшу.

    Args:
        file_bytes: Сырые байты изображения (JPEG/PNG/etc.).
        device: Устройство PyTorch ('cpu' или 'cuda').

    Returns:
        dict с результатами reconstruct_image, или None если лицо не найдено.
    """
    key = hashlib.sha256(file_bytes).hexdigest()
    if key not in _recon_cache:
        result = reconstruct_image(io.BytesIO(file_bytes), device=device)
        _recon_cache[key] = result  # Кэшируем даже None
    return _recon_cache[key]


def cache_size() -> int:
    """Возвращает текущее число элементов в кэше."""
    return len(_recon_cache)


def clear_cache() -> None:
    """Очищает кэш реконструкций."""
    _recon_cache.clear()
