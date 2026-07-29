"""🏭 FACTORY → Синтетический архив 7×9×3 для regression-тестов `runner.py`.

Реальный `selected_photos_7x9x3_data.tar.gz` содержит подлинные landmarks и
не хранится в git (см. `app6/test_module/test_scenarios_archive.py`). Тесты
`runner.py`, однако, обязаны проверять поведение раздачи ролей и вызовов
`compare_landmarks`/`detect_irreversible_return` независимо от того, доступен
ли реальный архив в конкретном окружении (см. `app6/AGENTS.md`: сценарии
проверяют поведение системы, а не одно окружение).

Этот генератор строит структуру, побайтово совместимую с контрактом
`archive_adapter.load_archive_records` (без `record.npz`, только CSV +
metadata.json), но с полностью синтетической, воспроизводимой геометрией:
разные "персоны" — далеко разнесённые облака точек, кадры одной персоны —
то же облако с небольшим шумом. Он не подменяет реальный архив в
продуктивных сценарных тестах — используется только для юнит-проверки самого
`runner.py`.
"""
from __future__ import annotations

import csv
import json
import tarfile
from pathlib import Path

import numpy as np

POSE_BINS: tuple[str, ...] = (
    "left_profile", "left_deep", "left_mid", "left_light", "frontal",
    "right_light", "right_mid", "right_deep", "right_profile",
)


def _write_landmarks_csv(path: Path, points: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["landmark_id", "x", "y", "z"])
        for idx, (x, y, z) in enumerate(points):
            writer.writerow([idx, float(x), float(y), float(z)])


def _base_shape(n_points: int, seed: int, separation: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    shape = rng.normal(0.0, 1.0, size=(n_points, 3)).astype(np.float64)
    shape[:, 0] += separation
    return shape


def build_synthetic_archive(
    root: Path,
    *,
    people: tuple[str, ...] = ("person_01", "person_02", "person_03"),
    frames_per_cell: int = 3,
    noise_scale: float = 0.02,
) -> Path:
    """Записать под `root` структуру `person_XX__frame_YYYYYY/` и вернуть путь к tar.gz.

    Каждая персона получает своё отдельное облако точек (сепарация по X),
    каждый (персона, ракурс) — `frames_per_cell` кадров с малым гауссовым
    шумом вокруг этого облака и почти идентичными углами позы (шум ракурса
    не является предметом этого генератора).
    """
    root.mkdir(parents=True, exist_ok=True)
    for person_index, person in enumerate(people):
        separation = person_index * 12.0  # заведомо больше, чем возможный шум одного человека
        base106 = _base_shape(106, seed=1000 + person_index, separation=separation)
        base134 = _base_shape(134, seed=2000 + person_index, separation=separation)
        for pose_index, pose_bin in enumerate(POSE_BINS):
            for frame_index in range(frames_per_cell):
                rng = np.random.default_rng(hash((person, pose_bin, frame_index)) % (2**32))
                ldm106 = base106 + rng.normal(0.0, noise_scale, size=base106.shape)
                ldm134 = base134 + rng.normal(0.0, noise_scale, size=base134.shape)
                record_name = f"{person}__frame_{pose_index:02d}{frame_index:04d}"
                directory = root / record_name
                directory.mkdir(parents=True, exist_ok=True)
                _write_landmarks_csv(directory / "ldm106_raw.csv", ldm106)
                _write_landmarks_csv(directory / "ldm134_raw.csv", ldm134)
                metadata = {
                    "record_id": record_name,
                    "dataset_id": person,
                    "frame_index": pose_index * 1000 + frame_index,
                    "pose_bin": pose_bin,
                    "arrays": {
                        "object_normalization_center": [0.0, 0.0, 0.0],
                        "object_normalization_scale": 1.0,
                        "angle_deg_pitch_yaw_roll": [0.0, float(pose_index * 5), 0.0],
                        "ldm106_visible_original": [True] * 106,
                        "ldm134_visible_original": [True] * 134,
                    },
                }
                (directory / "metadata.json").write_text(
                    json.dumps(metadata, ensure_ascii=False), encoding="utf-8",
                )

    archive_path = root.parent / "synthetic_archive.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        for entry in sorted(root.iterdir()):
            tar.add(entry, arcname=entry.name)
    return archive_path
