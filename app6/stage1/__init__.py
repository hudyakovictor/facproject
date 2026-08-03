"""DEEPUTIN Stage 1 extraction package.

Keep metadata/provenance utilities importable without OpenCV/Torch; the heavy
inference engine is loaded only when ``Stage1Engine`` is requested.
"""
from __future__ import annotations
from typing import Any

from .config import Stage1Config

__all__ = ["Stage1Config", "Stage1Engine"]


def __getattr__(name: str) -> Any:
    if name == "Stage1Engine":
        from .engine import Stage1Engine
        return Stage1Engine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
