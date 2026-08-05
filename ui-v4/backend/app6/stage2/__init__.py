"""Stage 2: calibration-aware chronological analysis.

The orchestration engine has optional image/texture dependencies.  Keep core
geometry, policy and report modules independently importable for calibration
and contract checks.
"""
from __future__ import annotations
from typing import Any

__all__ = ["Stage2Config", "Stage2Engine"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .engine import Stage2Config, Stage2Engine
        return {"Stage2Config": Stage2Config, "Stage2Engine": Stage2Engine}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
