"""⚙️ Конфигурация Stage 1: пороги, семантические политики, POSE_BINS (9 бинов).
🎯 CRITICAL → canonical yaw-значения [0, ±17.5, ±32.5, ±45] согласованы с
  geometry.classify_pose() и golden-тестами — менять только синхронно!
📤 public_dict()/extraction_payload() — сериализация конфига в info.json.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "deeputin-stage1-v2.4-chronology-alignment"
PHOTO_SCHEMA_VERSION = "deeputin-photo-v2.4-chronology-alignment"
VALIDATION_SCHEMA_VERSION = "deeputin-validation-v2.4-chronology-alignment"
SEMANTIC_POLICY = "3ddfa-semantic-skin-plus-nose-v1"
POSE_BINS = (
    ("left_profile", -95.0, -50.0, -70.0),
    ("left_deep", -50.0, -40.0, -45.0),
    ("left_mid", -40.0, -25.0, -32.5),
    ("left_light", -25.0, -10.0, -17.5),
    ("frontal", -10.0, 10.0, 0.0),
    ("right_light", 10.0, 25.0, 17.5),
    ("right_mid", 25.0, 40.0, 32.5),
    ("right_deep", 40.0, 50.0, 45.0),
    ("right_profile", 50.0, 95.000001, 70.0),
)
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})

# ─────────────────────────────────────────────────────────────────────────────
# ДЕТЕКЦИЯ ВЫРАЖЕНИЙ ЛИЦА — только через геометрию ландмарок 3DDFA
# ─────────────────────────────────────────────────────────────────────────────
# В проекте используется ЕДИНЫЙ подход к определению мимики — через форму
# ключевых точек (106-точечная схема 3DDFA_V3), а не через alpha_exp (BFM).
#
# ПОЧЕМУ НЕ alpha_exp:
#   L2-норма alpha_exp (BFM expression coefficients) НЕ ИСПОЛЬЗУЕТСЯ для
#   детекции улыбки/открытого рта, потому что:
#   - Не имеет физического смысла (непонятно какой порог чему соответствует)
#   - Сильно зависит от качества реконструкции 3DDFA
#   - Не разделяет спокойные лица и улыбки на калибровочном наборе
#   (значение EXPRESSION_MAGNITUDE_THRESHOLD=12.0 сохранено только для
#   обратной совместимости в stage2/engine.py, но не используется в QC)
#
# КАК РАБОТАЕТ ГЕОМЕТРИЧЕСКАЯ ДЕТЕКЦИЯ:
#   1. Улыбка — измеряем подъём уголков рта относительно центра рта
#      (corner_lift_ioc). При улыбке уголки поднимаются, давая ПОЛОЖИТЕЛЬНОЕ
#      значение. Метрика НЕ ЗАВИСИТ от ширины рта человека — только от формы.
#   2. Открытый рот — измеряем расстояние между верхней и нижней губой
#      (jaw_open_ratio). Не зависит от размера рта.
#   3. Обе метрики нормализованы по межзрачковому расстоянию (инвариантны
#      к масштабу лица на фото).
#
# КАЛИБРОВКА:
#   Пороги подобраны на наборе smiletest (13 фото: 9 спокойных + 4 выразительных)
#   и дают 100% separation — ни одного ложного срабатывания.
#   См. audit: calibration_dataset/test_calibration_landmarks.py
# ─────────────────────────────────────────────────────────────────────────────

#: Не используется для QC. Сохранён для обратной совместимости (stage2/engine.py).
EXPRESSION_MAGNITUDE_THRESHOLD = 12.0

#: ── ПОРОГ УЛЫБКИ (подъём уголков рта) ──
#: corner_lift_ioc = (avg_y(уголки_рта) - avg_y(центр_рта)) / interocular
#: Положительное = уголки подняты = улыбка. Порог 0.005 с запасом.
#: Все calm ≤ -0.0106, все smile ≥ +0.0166 (на smiletest).
EXPRESSION_CORNER_LIFT_THRESHOLD = 0.005

#: ── ПОРОГ ОТКРЫТОГО РТА (раскрытие челюсти) ──
#: jaw_open_ratio = ||upper_lip - lower_lip|| / interocular
#: Все calm ≤ 0.1711, open_mouth = 0.3955 (на smiletest).
EXPRESSION_JAW_OPEN_THRESHOLD = 0.28


@dataclass(frozen=True)
class Stage1Config:
    project_root: Path
    input_dir: Path
    output_dir: Path
    device: str = "auto"
    detector: str = "retinaface"
    backbone: str = "resnet50"
    uv_size: int = 1000
    limit: int = 0
    overwrite: bool = False
    continue_on_error: bool = True
    save_original: bool = True
    save_mesh: bool = True
    require_filename_date: bool = True
    sampling_mode: str = "full"
    per_year: int = 5

    def __post_init__(self) -> None:
        if self.device not in {"auto", "cpu", "cuda"}:
            raise ValueError("device must be auto, cpu or cuda")
        if self.detector != "retinaface":
            raise ValueError("only retinaface detector is supported")
        if self.backbone not in {"resnet50", "mbnetv3"}:
            raise ValueError("unsupported reconstruction backbone")
        if not 64 <= int(self.uv_size) <= 1000:
            raise ValueError("uv_size must be in 64..1000")
        if int(self.limit) < 0:
            raise ValueError("limit must be non-negative")
        if self.sampling_mode not in {"full", "limited", "per_year"}:
            raise ValueError("sampling_mode must be full, limited or per_year")
        if int(self.per_year) < 1:
            raise ValueError("per_year must be >= 1")
        input_path = Path(self.input_dir).resolve()
        output_path = Path(self.output_dir).resolve()
        if input_path == output_path or input_path in output_path.parents:
            raise ValueError("output_dir must not equal or be inside input_dir")

    # 📤 Только настройки, влияющие на научный результат (идут в info.json)
    def extraction_payload(self) -> dict[str, Any]:
        """Only settings that can change scientific output."""
        return {
            "schema_version": SCHEMA_VERSION,
            "detector": self.detector,
            "backbone": self.backbone,
            "uv_size": int(self.uv_size),
            "semantic_policy": SEMANTIC_POLICY,
            "pose_bins": POSE_BINS,
            "save_mesh": bool(self.save_mesh),
            "require_filename_date": bool(self.require_filename_date),
            "sampling_mode": self.sampling_mode,
            "per_year": int(self.per_year),
        }

    # 📤 Публичный dict конфига для сериализации
    def public_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: str(v) if isinstance(v, Path) else v for k, v in d.items()}
