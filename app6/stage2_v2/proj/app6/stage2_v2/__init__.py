"""Stage 2 v2 - rebuilt analysis stage for the 3DDFA_V3 pipeline.

Design rules that the legacy stage2 package violated and this one enforces:

1. One source of truth for every threshold: params.py. No module-level magic
   numbers and no duplicated constants with drifting values.
2. The Stage 1 output contract is frozen and declared in contract.py.
   Stage 2 reads it and never guesses key names.
3. Failures are collected per record, not raised globally, so one bad photo
   cannot abort a run.
4. Every gate decision records the parameter value that produced it, so any
   result can be explained after the fact.
5. The admin panel is generated from the registry, so a newly declared
   parameter appears in the UI immediately.
"""
from __future__ import annotations

from . import contract
from .params import (
    BUILTIN_PROFILES,
    BY_KEY,
    GROUPS,
    PARAMS_SCHEMA,
    SPECS,
    ParamError,
    Params,
    ParamSpec,
    builtin,
    registry_json,
)

__all__ = [
    "contract",
    "Params",
    "ParamSpec",
    "ParamError",
    "SPECS",
    "BY_KEY",
    "GROUPS",
    "PARAMS_SCHEMA",
    "BUILTIN_PROFILES",
    "builtin",
    "registry_json",
]

__version__ = "2.0.0"
