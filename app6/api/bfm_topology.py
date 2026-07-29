"""🎯 CRITICAL → Загрузка геометрии BFM (Basel Face Model) без нейросети/torch.

`3ddfa_v3/assets/face_model.tar.gz` содержит подлинные данные деформируемой
модели лица 3DDFA_V3: среднюю форму (`u`), PCA-базисы идентичности (`id`,
80 компонент) и мимики (`exp`, 64 компоненты), точную топологию треугольников
(`tri`, 70 789 треугольников на 35 709 вершинах) и точные индексы вершин для
106/134 ландмарков — те же самые, что использует настоящий Stage 1
(`app6/stage1/reconstruction.py`, `model/recon.py:compute_shape`).

🚨 WARNING: это НЕ neural network inference. Веса `net_recon.pth` (энкодер
фото → alpha_id/alpha_exp) по-прежнему отсутствуют в этом окружении — сама
реконструкция "фото → альфа-параметры" недоступна. Но математика "альфа →
3D-меш" (`face_shape = u + id_basis @ alpha_id + exp_basis @ alpha_exp`)
идентична строке `model/recon.py:184` и не требует torch — только линейная
алгебра numpy. Это позволяет API строить подлинные BFM-мешы (полную
топологию, а не приближённое k-NN облако точек) для демонстрационных
alpha-векторов, использующих ТОЧНО ТУ ЖЕ модель, что и продакшн-пайплайн.

Модуль не встраивает файл `face_model.npy` в git (см. `.gitignore: *.npy`):
он извлекается лениво из уже закоммиченного `face_model.tar.gz` в кэш
`runs/bfm_cache/` при первом обращении и переиспользуется дальше.
"""
from __future__ import annotations

import tarfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

BFM_TOPOLOGY_SCHEMA = "deeputin-api-bfm-topology-v1.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARBALL_PATH = PROJECT_ROOT / "3ddfa_v3" / "assets" / "face_model.tar.gz"
CACHE_DIR = PROJECT_ROOT / "runs" / "bfm_cache"
CACHE_NPY_PATH = CACHE_DIR / "face_model.npy"

_lock = threading.Lock()
_cached_model: "BFMModel | None" = None


@dataclass(frozen=True)
class BFMModel:
    """Неизменяемые геометрические данные BFM, разделяемые между запросами."""

    mean_shape: np.ndarray          # (35709, 3) float32 — средняя форма (identity+expr=0)
    id_basis: np.ndarray            # (35709, 3, 80) float32
    exp_basis: np.ndarray           # (35709, 3, 64) float32
    triangles: np.ndarray           # (70789, 3) int64 — топология (0-indexed)
    ldm106_indices: np.ndarray      # (106,) int64 — индексы вершин для 106 landmarks
    ldm134_indices: np.ndarray      # (134,) int64 — индексы вершин для 134 landmarks
    primary_triangle_zone: np.ndarray  # (70789,) int16 — индекс зоны A01..A20 или -1
    primary_zone_ids: list[str]     # ["A01", ..., "A20"]
    primary_zone_names: list[str]   # ["forehead_left", ...]
    face_support: np.ndarray        # (70789,) bool — треугольник относится к лицу (не фону/шее)

    def compute_shape(self, alpha_id: np.ndarray, alpha_exp: np.ndarray) -> np.ndarray:
        """🔢 NUMERIC → Та же формула, что `model/recon.py:compute_shape` (без torch).

        Raises:
            ValueError: неверная размерность alpha_id/alpha_exp.
        """
        alpha_id = np.asarray(alpha_id, np.float32).reshape(-1)
        alpha_exp = np.asarray(alpha_exp, np.float32).reshape(-1)
        if alpha_id.shape[0] != self.id_basis.shape[2]:
            raise ValueError(f"alpha_id must have {self.id_basis.shape[2]} components, got {alpha_id.shape[0]}")
        if alpha_exp.shape[0] != self.exp_basis.shape[2]:
            raise ValueError(f"alpha_exp must have {self.exp_basis.shape[2]} components, got {alpha_exp.shape[0]}")
        shape = (
            self.mean_shape
            + np.tensordot(self.id_basis, alpha_id, axes=([2], [0]))
            + np.tensordot(self.exp_basis, alpha_exp, axes=([2], [0]))
        )
        return shape.astype(np.float32)


def _extract_face_model_npy() -> Path:
    """🚧 GATE → Извлечь face_model.npy из закоммиченного tar.gz при первом обращении."""
    if CACHE_NPY_PATH.is_file():
        return CACHE_NPY_PATH
    if not TARBALL_PATH.is_file():
        raise FileNotFoundError(
            f"face_model.tar.gz не найден: {TARBALL_PATH}. BFM-геометрия недоступна."
        )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(TARBALL_PATH) as tar:
        member = next((m for m in tar.getmembers() if m.name.endswith("face_model.npy") and not m.name.startswith("._")), None)
        if member is None:
            raise FileNotFoundError(f"face_model.npy не найден внутри {TARBALL_PATH}")
        extracted = tar.extractfile(member)
        if extracted is None:
            raise FileNotFoundError(f"не удалось прочитать face_model.npy внутри {TARBALL_PATH}")
        temp_path = CACHE_NPY_PATH.with_suffix(".npy.partial")
        temp_path.write_bytes(extracted.read())
        temp_path.replace(CACHE_NPY_PATH)
    return CACHE_NPY_PATH


def load_bfm_model() -> BFMModel:
    """🚪 ENTRY POINT (программный) → Загрузить (с кэшированием в памяти) BFM-геометрию.

    Raises:
        FileNotFoundError: если исходный `face_model.tar.gz` отсутствует в репозитории.
    """
    global _cached_model
    with _lock:
        if _cached_model is not None:
            return _cached_model
        npy_path = _extract_face_model_npy()
        raw: dict[str, Any] = np.load(npy_path, allow_pickle=True).item()

        n_vertices = 35709
        mean_shape = np.asarray(raw["u"], np.float32).reshape(n_vertices, 3)
        id_basis = np.asarray(raw["id"], np.float32).reshape(n_vertices, 3, -1)
        exp_basis = np.asarray(raw["exp"], np.float32).reshape(n_vertices, 3, -1)
        triangles = np.asarray(raw["tri"], np.int64)
        ldm106_indices = np.asarray(raw["ldm106"], np.int64).reshape(-1)
        ldm134_indices = np.asarray(raw["ldm134"], np.int64).reshape(-1)
        primary_triangle_zone = np.asarray(raw["primary_triangle_zone"], np.int16)
        primary_zone_ids = [str(x) for x in raw["primary_zone_ids"]]
        primary_zone_names = [str(x) for x in raw["primary_zone_names"]]
        face_support = np.asarray(raw["face_support"], bool)

        if ldm106_indices.shape[0] != 106:
            raise ValueError(f"expected 106 ldm106 indices, got {ldm106_indices.shape[0]}")
        if ldm134_indices.shape[0] != 134:
            raise ValueError(f"expected 134 ldm134 indices, got {ldm134_indices.shape[0]}")
        if triangles.max() >= n_vertices:
            raise ValueError("triangle vertex index out of range")

        _cached_model = BFMModel(
            mean_shape=mean_shape, id_basis=id_basis, exp_basis=exp_basis, triangles=triangles,
            ldm106_indices=ldm106_indices, ldm134_indices=ldm134_indices,
            primary_triangle_zone=primary_triangle_zone, primary_zone_ids=primary_zone_ids,
            primary_zone_names=primary_zone_names, face_support=face_support,
        )
        return _cached_model


def is_bfm_available() -> bool:
    """🔍 QUERY → Проверить доступность BFM-геометрии без выброса исключения."""
    try:
        load_bfm_model()
        return True
    except (FileNotFoundError, ValueError, KeyError):
        return False
