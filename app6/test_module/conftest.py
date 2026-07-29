"""Общие фикстуры тестового контура app6."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Статус-логгер печатает на каждый вызов; в тестах это только шум.
logging.disable(logging.INFO)


@pytest.fixture(scope="session")
def project_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def calibration_root(project_root: Path) -> Path:
    """🚧 GATE → Только источники, из которых load_calibration реально строит записи.

    🚨 WARNING: `calibration_dataset/person_*/frame_*/` (legacy pre-extracted
    landmarks, признаны неактуальными — выровнены неверно) сюда намеренно НЕ
    засчитываются. Единственный допустимый вход — `calibration_dataset/photos/`
    (сырые фото, Stage 1 запускается заново) либо уже готовый
    `main_timeline.csv` от `run_calibration.py`. Без них тест обязан
    пропускаться с понятной причиной, а не падать как ошибка окружения.
    """
    path = project_root / "calibration_dataset"
    has_fresh_extract = (path / "main_timeline.csv").is_file()
    has_raw_photos = (path / "photos").is_dir() and any((path / "photos").rglob("*.jpg"))
    if not (has_fresh_extract or has_raw_photos):
        pytest.skip(
            "калибровочный контур недоступен: нет ни calibration_dataset/photos/ "
            "(сырые фото для Stage 1), ни calibration_dataset/main_timeline.csv "
            "(готовый результат run_calibration.py). Ранее извлечённые "
            "calibration_dataset/person_*/frame_*/ намеренно не используются — "
            "их landmarks признаны невыровненными; см. app6/stage2/loaders.py"
        )
    return path


@pytest.fixture(scope="session")
def calibration_records(calibration_root: Path):
    """Записи калибровки, извлечённые Stage 1 из сырых фото (или их свежий кэш).

    🚨 WARNING: требует весов 3DDFA_V3 (assets/*.pth, assets/*.npy), если ещё
    нет `main_timeline.csv`. Их отсутствие — ожидаемое состояние CI/песочницы,
    поэтому пропускаем тест, а не считаем его упавшим.
    """
    from app6.stage2.loaders import load_calibration
    try:
        return load_calibration(calibration_root)
    except FileNotFoundError as exc:
        pytest.skip(f"калибровка недоступна в этом окружении: {exc}")


@pytest.fixture(scope="session")
def zone_maps(calibration_records):
    from app6.stage2.core import build_coordinate_zone_map
    zone106, _ = build_coordinate_zone_map(calibration_records, 106)
    zone134, _ = build_coordinate_zone_map(calibration_records, 134)
    return zone106, zone134


@pytest.fixture(scope="session")
def records_by_person_pose(calibration_records):
    from collections import defaultdict
    grouped = defaultdict(list)
    for record in calibration_records:
        grouped[(record.dataset_id, record.pose_bin)].append(record)
    return grouped


@pytest.fixture(scope="session")
def synthetic_textures():
    """Синтетические поверхности с известными свойствами микрорельефа."""
    rng = np.random.default_rng(20260729)
    yy, xx = np.mgrid[:160, :160]
    return {
        "skin": rng.normal(128, 18, (160, 160)) + rng.normal(0, 6, (160, 160)),
        "moulded": 128 + 30 * np.sin(xx * 1.4) + 30 * np.sin(yy * 1.4),
        "smooth_gradient": np.clip(128 + 18 * np.sin(xx / 40.0), 0, 255).astype(np.float64),
        "mask": np.ones((160, 160), dtype=bool),
    }
