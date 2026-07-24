"""🔧 Конфигурация тестового модуля. Все пути — относительно папки work/."""
from __future__ import annotations
from pathlib import Path

TM_DIR = Path(__file__).resolve().parent            # app6/test_module
WORK_ROOT = TM_DIR.parent.parent                      # work/
APP6_DIR = WORK_ROOT / "app6"
CALIB_ROOT = WORK_ROOT / "calibration_dataset"
PHOTOS_ROOT = CALIB_ROOT / "photos"
CALIB_INDEX = WORK_ROOT / "calibration_dataset" / "all_calibration_index.csv"

SCENARIOS_DIR = TM_DIR / "builds"
TESTS_DIR = TM_DIR / "tests"
RUNS_DIR = TM_DIR / "runs"
CACHE_DIR = TM_DIR / "cache"
POOL_INDEX = TM_DIR / "pool_index.csv"

DUMMY_DATE = "2000_01_01"   # дата-заглушка для имён фото в stage1-кэше
MIN_FRAME_GAP = 25          # кадры одного человека — не ближе 25 кадров видео друг к другу

# Статусы пар, считающиеся "красными" (реальная аномалия).
RED_STATUSES = {
    "persistent_geometric_change",
    "same_day_structural_conflict",
    "rapid_change_candidate",
    "persistent_rapid_change_candidate",
    "coherent_jump_candidate",
    "alpha_id_jump_candidate",
}
