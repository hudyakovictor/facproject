"""DEEPUTIN app6 package.

The root package deliberately has no eager Stage 1 import.  Geometry-only
analysis, report generation and API schema checks must remain importable on a
machine that does not have the optional 3DDFA/OpenCV inference stack installed.
Use ``app6.Stage1Config`` / ``app6.Stage1Engine`` as before; they are loaded
only when explicitly requested.
"""
from __future__ import annotations

from typing import Any

__all__ = ["Stage1Config", "Stage1Engine"]


def __getattr__(name: str) -> Any:
    if name == "Stage1Config":
        from .stage1.config import Stage1Config
        return Stage1Config
    if name == "Stage1Engine":
        from .stage1.engine import Stage1Engine
        return Stage1Engine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
