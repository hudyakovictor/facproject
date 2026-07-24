"""DEEPUTIN app6 package.

Stage 1 lives in app6.stage1; Stage 2/2B/3 live in their own packages.
Root package re-exports Stage1Config/Stage1Engine for convenience only.
📦 CONVENTIONS v2 → статусы модулей/функций: app6/FUNCTION_STATUS_LOG.md
"""
from .stage1 import Stage1Config, Stage1Engine

__all__ = ["Stage1Config", "Stage1Engine"]
