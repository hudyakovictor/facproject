"""🏭 FACTORY → Детерминированный demo-датасет для API, когда исследовательские данные недоступны.

🚨 WARNING: это не результат анализа фотографий Путина. Это синтетическая,
воспроизводимая коллекция для разработки/демонстрации интерфейса, когда
`app6.api` не сконфигурирован на реальный вывод Stage 1/2
(`DEEPUTIN_STAGE1_ROOT` / `DEEPUTIN_STAGE2_ROOT` не заданы или недоступны).
Все ряды помечаются `source_mode: "demo"` и никогда не должны публиковаться
как evidence — см. `app6/AGENTS.md`.

В отличие от прежней чисто-фронтендовой генерации (`ui/src/data.ts`, где
метрики считались формулами вида ``Math.sin(i * t / 1e15)``), здесь позы и
геометрия — это настоящие 3D-облака точек (106/134 landmark), и все метрики
пары считаются через реальный `app6.stage2.core.compare_landmarks` —
тот же код, что используется в исследовательском Stage 2. Смена сценария
("персона") эмулирует то, что тестирует `app6/test_module/scenarios.py`
(A→A→A, A→B, A→B→A), но подписана как демонстрация метода, а не как находка.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np

from app6.stage2.core import Record, build_coordinate_zone_map, compare_landmarks

DEMO_SCHEMA = "deeputin-api-demo-dataset-v1.0"

POSE_BINS: tuple[str, ...] = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)
POSE_YAW: dict[str, float] = {
    "left_profile": -70.0, "left_deep": -45.0, "left_mid": -32.5, "left_light": -17.5,
    "frontal": 0.0, "right_light": 17.5, "right_mid": 32.5, "right_deep": 45.0, "right_profile": 70.0,
}

#: Демонстрационные "эпохи" с разными синтетическими носителями формы.
#: `carrier` — индекс синтетического облака точек (0,1,2 = разные "лица").
#: Это иллюстрация вопроса "может ли пайплайн отличить A от B", а не
#: утверждение о реальных периодах жизни какого-либо человека.
_ERA_PLAN: list[dict[str, Any]] = [
    {"id": "DEMO_SEGMENT_1", "start": "1999-08-09", "end": "2011-12-31", "count": 140, "carrier": 0},
    {"id": "DEMO_SEGMENT_2", "start": "2012-01-01", "end": "2014-12-31", "count": 60, "carrier": 0},
    {"id": "DEMO_SEGMENT_3", "start": "2015-01-01", "end": "2021-09-08", "count": 130, "carrier": 1},
    {"id": "DEMO_SEGMENT_4", "start": "2021-09-09", "end": "2023-09-30", "count": 70, "carrier": 1},
    {"id": "DEMO_SEGMENT_5", "start": "2023-10-01", "end": "2026-06-04", "count": 120, "carrier": 2},
]


def _seed_from(*parts: Any) -> int:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int(hashlib.blake2b(raw, digest_size=4).hexdigest(), 16)


def _carrier_shape(carrier: int, n_points: int) -> np.ndarray:
    """Базовое облако точек синтетического "лица" — стабильно для carrier."""
    rng = np.random.default_rng(9000 + carrier)
    shape = rng.normal(0.0, 1.0, size=(n_points, 3)).astype(np.float64)
    shape[:, 0] += carrier * 9.0  # разнесение "лиц" в пространстве object-space
    return shape


def _rotate_yaw(points: np.ndarray, yaw_deg: float) -> np.ndarray:
    rad = np.deg2rad(yaw_deg)
    cos_a, sin_a = np.cos(rad), np.sin(rad)
    rot = np.array([[cos_a, 0.0, sin_a], [0.0, 1.0, 0.0], [-sin_a, 0.0, cos_a]])
    return points @ rot.T


def _visibility_for_yaw(n_points: int, yaw_deg: float, seed: int) -> np.ndarray:
    """Меньше видимых точек при более глубоком развороте — как в реальных pose bins."""
    rng = np.random.default_rng(seed)
    visible_fraction = float(np.clip(1.0 - abs(yaw_deg) / 100.0, 0.45, 1.0))
    mask = rng.random(n_points) < visible_fraction
    if mask.sum() < 24:
        mask[: max(24, n_points // 2)] = True
    return mask


@dataclass
class DemoPhoto:
    id: str
    date: str
    pose_bin: str
    era: str
    carrier: int
    record: Record


def build_demo_records(seed_label: str = "deeputin-demo-v1") -> list[DemoPhoto]:
    """🏭 FACTORY → Построить синтетическую хронологию с реальной геометрией.

    Возвращает список `DemoPhoto`, каждый — c настоящим `Record` (106/134
    ландмарки, углы, видимость), готовым к `compare_landmarks`.
    """
    out: list[DemoPhoto] = []
    idx = 0
    for segment in _ERA_PLAN:
        start = date.fromisoformat(segment["start"])
        end = date.fromisoformat(segment["end"])
        span_days = (end - start).days
        rng = np.random.default_rng(_seed_from(seed_label, segment["id"]))
        offsets = sorted(rng.integers(0, max(span_days, 1), size=segment["count"]).tolist())
        base106 = _carrier_shape(segment["carrier"], 106)
        base134 = _carrier_shape(segment["carrier"], 134)
        for offset in offsets:
            photo_date = start + timedelta(days=int(offset))
            pose_bin = POSE_BINS[idx % len(POSE_BINS)]
            yaw = POSE_YAW[pose_bin]
            noise_seed = _seed_from(seed_label, segment["id"], idx)
            noise_rng = np.random.default_rng(noise_seed)
            # Реальный внутрисубъектный шум (реконструкция+мимика+свет) —
            # небольшой гауссов джиттер того же порядка, что в calibration_dataset.
            jitter106 = noise_rng.normal(0.0, 0.02, size=base106.shape)
            jitter134 = noise_rng.normal(0.0, 0.02, size=base134.shape)
            ldm106 = _rotate_yaw(base106 + jitter106, yaw)
            ldm134 = _rotate_yaw(base134 + jitter134, yaw)
            pitch_roll_noise = noise_rng.normal(0.0, 1.5, size=2)
            angles = np.array([pitch_roll_noise[0], yaw, pitch_roll_noise[1]], dtype=np.float32)
            visible106 = _visibility_for_yaw(106, yaw, noise_seed)
            visible134 = _visibility_for_yaw(134, yaw, noise_seed + 1)
            alpha_id = noise_rng.normal(0.0, 0.05, size=80).astype(np.float32) + segment["carrier"] * 0.3
            alpha_exp = np.abs(noise_rng.normal(0.0, 0.08, size=64)).astype(np.float32)
            photo_id = f"DEMO_{idx:05d}"
            record = Record(
                record_id=photo_id,
                dataset_id="demo_subject",
                date=photo_date.isoformat(),
                sequence=idx,
                pose_bin=pose_bin,
                angles=angles,
                ldm106=ldm106.astype(np.float32),
                ldm134=ldm134.astype(np.float32),
                visible106=visible106,
                visible134=visible134,
                alpha_id=alpha_id,
                alpha_exp=alpha_exp,
                record_dir=None,
                source_group=segment["id"],
                source_digest=None,
            )
            out.append(DemoPhoto(
                id=photo_id, date=photo_date.isoformat(), pose_bin=pose_bin,
                era=segment["id"], carrier=segment["carrier"], record=record,
            ))
            idx += 1
    out.sort(key=lambda p: p.date)
    for rank, photo in enumerate(out):
        photo.record.sequence = rank
    return out


def build_demo_zone_maps(photos: list[DemoPhoto]) -> tuple[np.ndarray, np.ndarray]:
    records = [p.record for p in photos]
    zone106, _ = build_coordinate_zone_map(records, 106)
    zone134, _ = build_coordinate_zone_map(records, 134)
    return zone106, zone134


def compare_demo_pair(a: DemoPhoto, b: DemoPhoto, zone106: np.ndarray, zone134: np.ndarray):
    """Тонкая обёртка: реальный `compare_landmarks` на демо-записях."""
    return compare_landmarks(a.record, b.record, zone106, zone134)
