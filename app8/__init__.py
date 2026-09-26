"""🌟 app8: Модернизированный высокоточный Stage 1 с хронологическим выравниванием.

Особенности app8:
- Нулевая файловая избыточность: Единый сжатый binary-контейнер (reconstruction.npz) без 8 лишних CSV.
- Каноническое хронологическое выравнивание позы по 9 POSE_BINS.
- Z-Buffer и Normal Confidence Gating для отсечения самоокклюзии.
- Инвариантный геометрический контроль мимики (улыбка / открытый рот).
- Мгновенный доступ к 134/106 ключевым точкам и 35 709 вершинам через reader API.
"""
from __future__ import annotations

from .config import SCHEMA_VERSION, POSE_BINS, Stage1Config
from .engine import run_stage1
from .reader import (
    App8Record,
    App8PackedBin,
    load_record,
    load_packed_bin,
    get_ldm134,
    get_ldm106,
)
from .reconstruction import reconstruct_image, get_models
from .packer import pack_pose_bins

__version__ = "1.0.0"
__all__ = [
    "SCHEMA_VERSION",
    "POSE_BINS",
    "Stage1Config",
    "run_stage1",
    "App8Record",
    "App8PackedBin",
    "load_record",
    "load_packed_bin",
    "get_ldm134",
    "get_ldm106",
    "reconstruct_image",
    "get_models",
    "pack_pose_bins",
]
