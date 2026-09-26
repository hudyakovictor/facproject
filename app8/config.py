"""⚙️ Конфигурация Stage 1 (app8): схемы, пороги, классификация поз (POSE_BINS).

Stage 1 извлекает полную 3DMM-геометрию, классифицирует ракурс по 9 каноническим бинам,
рассчитывает выравнивание позы для хронологического сравнения внутри каждого ракурса
и сохраняет компактный бинарный контейнер без избыточных текстовых CSV.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "deeputin-stage1-app8-v1.0"
PHOTO_SCHEMA_VERSION = "deeputin-photo-app8-v1.0"

# 9 канонических угловых бинов (Yaw от -95° до +95°)
# (имя бина, нижняя граница, верхняя граница, канонический yaw для хронологии)
POSE_BINS = (
    ("left_profile",  -95.0, -50.0, -70.0),
    ("left_deep",     -50.0, -40.0, -45.0),
    ("left_mid",      -40.0, -25.0, -32.5),
    ("left_light",    -25.0, -10.0, -17.5),
    ("frontal",       -10.0,  10.0,   0.0),
    ("right_light",    10.0,  25.0,  17.5),
    ("right_mid",      25.0,  40.0,  32.5),
    ("right_deep",     40.0,  50.0,  45.0),
    ("right_profile",  50.0,  95.0,  70.0),
)

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})

# Пороги геометрического контроля мимики (QC)
EXPRESSION_MAGNITUDE_THRESHOLD = 12.0
EXPRESSION_CORNER_LIFT_THRESHOLD = 0.005  # Подъем уголков рта / IOC (улыбка)
EXPRESSION_JAW_OPEN_THRESHOLD = 0.28       # Раскрытие губ / IOC (открытый рот)
CONFIDENCE_THRESHOLD = 0.5                 # Порог надежности видимости вершины


@dataclass(frozen=True)
class Stage1Config:
    project_root: Path
    input_dir: Path
    output_dir: Path
    device: str = "cpu"
    detector: str = "retinaface"
    backbone: str = "resnet50"
    limit: int = 0
    overwrite: bool = False
    continue_on_error: bool = True
    save_mesh: bool = True
    save_original: bool = True
    require_filename_date: bool = False
    group_by_pose: bool = False

    def __post_init__(self) -> None:
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be auto, cpu or cuda")
        if self.detector != "retinaface":
            raise ValueError("only retinaface detector is supported")
        if self.backbone not in {"resnet50", "mbnetv3"}:
            raise ValueError("unsupported reconstruction backbone")
        if int(self.limit) < 0:
            raise ValueError("limit must be non-negative")
