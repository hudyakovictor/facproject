"""Validated geometry policy for the production longitudinal analysis.

Values are frozen from DCRD + SGT-Chrono + 300-simulation selection.  Pose-bin
boundaries remain unchanged; this module only governs comparisons inside a bin.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Final
from functools import lru_cache
from pathlib import Path
import csv
import numpy as np

from .pose_policy import PROFILE_BINS, profile_sub_bin

ANALYSIS_COORDINATE_SPACE: Final[str] = "raw_object_normalized"
# Пороги разброса позы для сравнения внутри pose-bin.
#
# История: пороги были заморожены на синтетике (yaw 6 / pitch 2 / roll 5), затем
# ослаблены до 15/30/15, чтобы реальные пары не отбраковывались поголовно. Замер
# на калибровочном наборе (943 кадра, 15106 пар) показал, что ослабленные пороги
# пропускают 93.1% пар — гейт фактически инертен. Документированные 6/2/5 дают
# 31.5%. Ни один скалярный порог не годится: измеренный SNR3-предел разный по
# бинам (frontal 12°, right_profile 0°).
#
# Решение: порог по yaw берётся из per-bin таблицы, pitch/roll выводятся из неё
# через измеренную анизотропию чувствительности.
MAX_YAW_GAP_DEG: Final[float] = 6.0          # fallback, если бин неизвестен
#: Замер: d(residual)/d(pitch) / d(residual)/d(yaw) = 0.001010 / 0.000571.
PITCH_TO_YAW_SENSITIVITY: Final[float] = 1.77
ROLL_TO_YAW_SENSITIVITY: Final[float] = 1.37
MAX_PITCH_GAP_DEG: Final[float] = MAX_YAW_GAP_DEG / PITCH_TO_YAW_SENSITIVITY
MAX_ROLL_GAP_DEG: Final[float] = MAX_YAW_GAP_DEG / ROLL_TO_YAW_SENSITIVITY
MIN_ALIGNMENT_QUALITY: Final[float] = 0.5  # справочно (D-003): не гейтит пары
#: Допуск yaw-gap внутри 10° профильного подбина (замена бинового 0.0°).
PROFILE_SUB_BIN_MAX_YAW_GAP_DEG: Final[float] = 2.0
FDR_LEVEL: Final[float] = 0.05

POSE_GATE_FILENAME: Final[str] = "pose_gate_v2.csv"
#: Бины, где SNR3 не достигается ни на одной полосе — сравнение только справочное.
LIMITED_BINS: Final[frozenset[str]] = frozenset({"right_profile"})


def _atlas_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "atlas"


@lru_cache(maxsize=1)
def load_pose_gate(path: str | None = None) -> dict[str, float]:
    """Прочитать per-bin пороги yaw-gap. Fail-closed: файла нет → ошибка."""
    gate_path = Path(path) if path else _atlas_dir() / POSE_GATE_FILENAME
    if not gate_path.is_file():
        raise FileNotFoundError(f"таблица порогов позы не найдена: {gate_path}")
    table: dict[str, float] = {}
    with gate_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            table[str(row["pose_bin"]).strip()] = float(row["max_yaw_gap_deg"])
    if len(table) != 9:
        raise ValueError(f"ожидалось 9 бинов, получено {len(table)}")
    return table

@dataclass(frozen=True)
class PoseGap:
    pitch: float
    yaw: float
    roll: float
    accepted: bool
    reason: str
    pose_bin: str = ""
    yaw_limit: float = float("nan")
    limited: bool = False
    sub_bin: str = ""


def pose_gap(angles_a, angles_b, *, pose_bin: str | None = None) -> PoseGap:
    """Fail-closed axis-specific residual-pose gate for an in-bin pair.

    ``pose_bin`` всегда канонический (ключ BIN_NAME_TO_YAW / pose_gate_v2.csv);
    для профильных бинов имя 10° подбина живёт в ``sub_bin``. ``limited``
    считается во всех ветках (правда и для профилей, F2).
    """
    a=np.asarray(angles_a,dtype=float).reshape(-1)
    b=np.asarray(angles_b,dtype=float).reshape(-1)
    if a.size != 3 or b.size != 3 or not (np.isfinite(a).all() and np.isfinite(b).all()):
        return PoseGap(float("nan"),float("nan"),float("nan"),False,"nonfinite_pose",
                       pose_bin or "", float("nan"), False)
    pitch,yaw,roll=map(float,np.abs(a-b))
    limited = bool(pose_bin in LIMITED_BINS)
    if pose_bin and pose_bin in PROFILE_BINS:
        # Профили: сравнение только внутри одного 10° подбина; внутри подбина
        # действует PROFILE_SUB_BIN_MAX_YAW_GAP_DEG вместо бинового 0.0°.
        sub_a = profile_sub_bin(a[1])
        sub_b = profile_sub_bin(b[1])
        if sub_a is None or sub_b is None:
            return PoseGap(pitch,yaw,roll,False,"profile_yaw_out_of_range",
                           pose_bin, 0.0, limited, "")
        if sub_a != sub_b:
            return PoseGap(pitch,yaw,roll,False,"profile_sub_bin_mismatch",
                           pose_bin, PROFILE_SUB_BIN_MAX_YAW_GAP_DEG, limited, sub_a)
        yaw_limit = PROFILE_SUB_BIN_MAX_YAW_GAP_DEG
        sub_bin = sub_a
    else:
        yaw_limit = float(load_pose_gate().get(pose_bin, MAX_YAW_GAP_DEG)) if pose_bin else MAX_YAW_GAP_DEG
        sub_bin = ""
    pitch_limit = yaw_limit / PITCH_TO_YAW_SENSITIVITY
    roll_limit = yaw_limit / ROLL_TO_YAW_SENSITIVITY
    tail = (pose_bin or "", yaw_limit, limited, sub_bin)
    # yaw_limit == 0 означает: бин не обеспечивает SNR3 ни на одной полосе.
    if yaw_limit <= 0.0:
        return PoseGap(pitch,yaw,roll,False,"bin_below_snr3",*tail)
    if yaw > yaw_limit: return PoseGap(pitch,yaw,roll,False,"yaw_gap",*tail)
    if pitch > pitch_limit: return PoseGap(pitch,yaw,roll,False,"pitch_gap",*tail)
    if roll > roll_limit: return PoseGap(pitch,yaw,roll,False,"roll_gap",*tail)
    return PoseGap(pitch,yaw,roll,True,"",*tail)
