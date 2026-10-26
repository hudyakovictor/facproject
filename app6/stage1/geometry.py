"""
🎯 CRITICAL → Геометрия поз: canonical alignment и chronology alignment.

КЛЮЧЕВОЙ КОНТРАКТ (патч 03): хронология хранит identity-сетку в объектном каноне 3DMM —
ни полной коррекции позы, ни доворота к каноническому yaw бина она не получает.
История: патч 01 убрал двойной поворот (полная коррекция pitch+yaw+roll применялась к
vertices_identity, у которых поза уже снята базисом 3DDFA, и доворачивала кадр на -yaw
сверх нормы), патч 02 оставил только поворот к canonical_yaw бина, патч 03 убрал и его:
внутри бина это общая изометрия (расстояния не меняет), а между бинами и против
фронтального эталона добавляет искусственную разницу. canonical_yaw остаётся метаданным
для проверки согласованности бинов. Шум наклона головы внутри бина не убирается и
измеряется в app9/validation.
🔗 DEPENDS ON: config.POSE_BINS (9 бинов yaw), используется reconstruction.py/engine.py.
💡 NOTE: row_rotation_matrix — конвенция row-vector (Rz@Ry@Rx)^T; координаты согласованы с 3DDFA_V3.
⚠️ nearest_canonical_yaw (#17) — soft assignment, в пайплайн пока не интегрирована.
"""
from __future__ import annotations

import numpy as np

from .config import POSE_BINS
from .status_logger import log_status


def classify_pose(yaw: float) -> tuple[str, float]:
    """📊 METRIC → Классификация позы по yaw углу.

    9 бинов от left_profile (-70°) до right_profile (+70°).
    Каждый бин имеет canonical_yaw (центр бина).

    ⚠️ IN PROGRESS:
    - Жёсткие границы бинов: фото на границе получают чрезмерную коррекцию
    - Нет soft assignment (ближайший canonical вместо центра бина)
    - При yaw=-9.9° (frontal, canonical=0°) vs yaw=-10.1° (left_light, canonical=-17.5°)
      разница коррекции 7.4° для соседних фото!

    💡 NOTE:
    - frontal: -10°..10° → canonical 0°
    - left_light: -25°..-10° → canonical -17.5°
    - left_mid: -40°..-25° → canonical -32.5°
    - left_deep: -50°..-40° → canonical -45°
    - left_profile: -95°..-50° → canonical -70°
    """
    log_status("classify_pose", "complete")
    if not np.isfinite(float(yaw)):
        raise ValueError("yaw must be finite")
    for name, lo, hi, canonical in POSE_BINS:
        if lo <= float(yaw) < hi:
            return name, canonical
    return "out_of_supported_range", float(np.clip(yaw, -70.0, 70.0))
def nearest_canonical_yaw(yaw: float) -> tuple[str, float]:
    """📊 METRIC → Ближайший canonical yaw (soft assignment).

    В отличие от classify_pose, использует ближайший canonical,
    а не центр бина. Устраняет резкие скачки на границах бинов.

    Пример: yaw=-12° → canonical=-17.5° (left_light), не 0° (frontal).

    ⚠️ IN PROGRESS:
    - Пока не используется в основном пайплайне
    - Нужно интегрировать в compute_chronology_alignment

    📌 РЕШЕНИЕ (2026-07-22, аудит P0-2): оригиналы калибровочного датасета
    сохранены у владельца проекта; после интеграции soft assignment весь
    калибровочный датасет будет пересчитан заново тем же пайплайном.
    """
    if not np.isfinite(float(yaw)):
        raise ValueError("yaw must be finite")
    log_status("nearest_canonical_yaw", "need_testing", "Alternative assignment policy")
    best_name = "frontal"
    best_canonical = 0.0
    best_dist = float("inf")
    for name, _lo, _hi, canonical in POSE_BINS:  # границы (_lo/_hi) не нужны: выбор по близости к canonical
        dist = abs(float(yaw) - canonical)
        if dist < best_dist:
            best_dist = dist
            best_name = name
            best_canonical = canonical
    return best_name, best_canonical


def row_rotation_matrix(pitch_deg: float, yaw_deg: float, roll_deg: float) -> np.ndarray:
    """Euler rotation: Rz @ Ry @ Rx, transposed for row-vector convention."""
    log_status("row_rotation_matrix", "complete")
    p, y, r = np.radians([pitch_deg, yaw_deg, roll_deg])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]], np.float32)
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]], np.float32)
    rz = np.array([[np.cos(r), -np.sin(r), 0], [np.sin(r), np.cos(r), 0], [0, 0, 1]], np.float32)
    return (rz @ ry @ rx).T.astype(np.float32)


def full_pose_correction_matrix(actual_pose_deg: list[float] | np.ndarray,
                                 target_pose_deg: list[float] | np.ndarray) -> np.ndarray:
    """Compute rotation matrix that transforms mesh from actual_pose to target_pose.

    This is the KEY function for chronology alignment. It ensures that all photos
    within the same pose bin have identical pose (0, canonical_yaw, 0), eliminating
    pitch/roll noise from the comparison.

    The correction is: R_corr = R_target @ R_actual^T
    Where R_actual is the rotation that produced the actual pose, and R_target
    is the rotation for the desired canonical pose.

    IMPORTANT — applicability: this matrix only removes a pose that is actually
    present in the mesh (i.e. vertices_camera in the model basis, or a mesh the
    basis rotated by R_actual). Feeding `vertices_identity_only` into it is the
    double-rotation bug: the basis builds that mesh with zero pose, so
    subtracting the measured pose again over-rotates the frame by -yaw
    (app9/validation: ratio to the noise floor 4.87 instead of 2.15 frontal).
    In camera space an extra step is needed too, because to_camera does
    z = camera_distance - z, i.e. a reflection Fz = diag(1,1,-1): the correction
    must be applied as cam @ Fz @ R_corr (5.83 vs 2.19 otherwise).

    Args:
        actual_pose_deg: [pitch, yaw, roll] in degrees from 3DDFA
        target_pose_deg: [pitch, yaw, roll] in degrees for canonical pose

    Returns:
        3x3 rotation matrix (row-vector convention, float32)
    """
    log_status("full_pose_correction_matrix", "complete")
    actual = np.asarray(actual_pose_deg, np.float64).reshape(-1)
    target = np.asarray(target_pose_deg, np.float64).reshape(-1)
    if actual.shape != (3,) or target.shape != (3,):
        raise ValueError("actual_pose_deg and target_pose_deg must contain exactly 3 values")
    if not (np.isfinite(actual).all() and np.isfinite(target).all()):
        raise ValueError("pose values must be finite")

    # R_actual: rotation matrix that produced the actual pose
    R_actual = row_rotation_matrix(float(actual[0]), float(actual[1]), float(actual[2])).T
    # R_target: rotation matrix for the target canonical pose
    R_target = row_rotation_matrix(float(target[0]), float(target[1]), float(target[2])).T

    # Correction: undo actual rotation, then apply target rotation
    R_corr = (R_target @ R_actual.T).T.astype(np.float32)

    return R_corr


def normalize_mesh(mesh: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Normalize mesh to canonical scale and center.

    Uses RMS scale over the entire mesh. For chronology this is the ONLY
    transform applied: с патча 03 поворота после нормализации нет (identity-сетка
    уже без позы), поэтому scale/center и есть вся юстировка.
    """
    log_status("normalize_mesh", "complete")
    mesh = np.asarray(mesh, np.float32)
    center = mesh.mean(axis=0)
    centered = mesh - center
    scale = float(np.sqrt(np.mean(np.sum(centered * centered, axis=1))))
    if not np.isfinite(scale) or scale < 1e-8:
        raise ValueError("invalid full-mesh RMS scale")
    return (centered / scale).astype(np.float32), center.astype(np.float32), scale


def normalize_mesh_landmark_anchored(mesh: np.ndarray,
                                       landmark_indices: np.ndarray | None = None,
                                       anchor_pair: tuple[int, int] = (38, 43)) -> tuple[np.ndarray, np.ndarray, float]:
    """Normalize mesh using inter-landmark distance as scale reference.

    This is an alternative to RMS normalization that preserves more individual
    shape information. Uses the distance between two anatomical landmarks
    (default: eye centers) as the scale reference.

    Args:
        mesh: (N, 3) vertex array
        landmark_indices: indices of landmarks in mesh (if None, uses anchor_pair directly)
        anchor_pair: (idx1, idx2) pair of vertex indices for scale reference

    Returns:
        (normalized_mesh, center, scale)
    """
    log_status("normalize_mesh_landmark_anchored", "need_testing", "Indirect coverage only (AUDIT-6)")
    mesh = np.asarray(mesh, np.float32)
    if mesh.ndim != 2 or mesh.shape[1] != 3 or mesh.shape[0] < 2:
        raise ValueError("mesh must have shape (N,3) with N >= 2")
    if not np.isfinite(mesh).all():
        raise ValueError("mesh contains NaN/Inf")
    center = mesh.mean(axis=0)
    centered = mesh - center

    if landmark_indices is not None:
        idx1, idx2 = anchor_pair
        landmark_indices = np.asarray(landmark_indices, np.int64).reshape(-1)
        if min(anchor_pair) < 0 or max(anchor_pair) >= landmark_indices.size:
            raise IndexError("anchor_pair is outside landmark_indices")
        vertex_ids = landmark_indices[list(anchor_pair)]
        if np.any(vertex_ids < 0) or np.any(vertex_ids >= mesh.shape[0]):
            raise IndexError("landmark anchor vertex index is outside mesh")
        p1, p2 = mesh[vertex_ids]
    else:
        if min(anchor_pair) < 0 or max(anchor_pair) >= mesh.shape[0]:
            raise IndexError("anchor_pair is outside mesh")
        p1, p2 = mesh[list(anchor_pair)]

    scale = float(np.linalg.norm(p1 - p2))
    if not np.isfinite(scale) or scale < 1e-8:
        # Fallback to RMS scale
        scale = float(np.sqrt(np.mean(np.sum(centered * centered, axis=1))))
    if not np.isfinite(scale) or scale < 1e-8:
        raise ValueError("invalid landmark-anchored scale")

    return (centered / scale).astype(np.float32), center.astype(np.float32), scale


def compute_chronology_alignment(vertices: np.ndarray,
                                   actual_pose_deg: list[float] | np.ndarray,
                                   canonical_yaw: float,
                                   normalization: str = "rms") -> dict[str, np.ndarray]:
    """Full alignment pipeline for chronology comparison.

    This is the main entry point for producing aligned vertices suitable
    for chronological comparison within a pose bin.

    Steps:
    1. Normalize mesh (center + scale)
    2. NO rotation — the identity-only mesh is already pose-free

    Why there is no rotation (патч 03, после 01 и 02):
    - полный R_corr(actual -> target) на этом входе был двойным поворотом: базис 3DDFA
      строит `vertices_identity` с нулевыми параметрами позы, поэтому вычитать
      измеренные pitch/yaw/roll второй раз значит довернуть кадр на -yaw сверх нормы
      (app9/validation: ratio к шумовому полу 4.87 против 2.15, фронтал);
    - доворот даже на общий канонический yaw бина (патч 02) тоже убран: внутри бина это
      общая изометрия, то есть расстояния между кадрами она не меняет и проверить её
      нельзя, а при сравнении РАЗНЫХ бинов и против фронтального эталона она добавляет
      искусственную разницу ровно на canonical_yaw и портит ось зеркальной
      симметризации. `morphing/backend/aligner.py` описывает тот же вывод для своего
      конвейера — теперь прод и валидация согласованы.

    Args:
        vertices: (N, 3) vertex array (identity-only recommended)
        actual_pose_deg: [pitch, yaw, roll] from 3DDFA — сохраняется только как диагностика
        canonical_yaw: канонический yaw бина; НЕ применяется, возвращается как метаданные
            (потребители: проверка согласованности бинов и отчёты)
        normalization: "rms" for full-mesh RMS, "landmark" for eye-distance anchored

    Returns:
        dict with:
            - vertices_aligned: (N, 3) aligned vertices (normalized, без поворота)
            - correction_matrix: (3, 3) единичная матрица — поворот не выполняется
            - center: (3,) applied translation
            - scale: float applied scale
            - target_pose: [0, 0, 0] — реальная поза сохранённой сетки (identity-only)
            - bin_canonical_yaw: [canonical_yaw] — метаданные бина, не применено
            - actual_pose: original [pitch, yaw, roll]
    """
    log_status("compute_chronology_alignment", "complete")
    actual = np.asarray(actual_pose_deg, np.float64)
    target = np.zeros(3, np.float64)

    # Step 1: Normalize
    if normalization == "landmark":
        normalized, center, scale = normalize_mesh_landmark_anchored(vertices)
    elif normalization == "rms":
        normalized, center, scale = normalize_mesh(vertices)
    else:
        raise ValueError("normalization must be 'rms' or 'landmark'")

    # Step 2: поворота нет — см. docstring. Сетка остаётся в объектном каноне 3DMM.
    R_corr = np.eye(3, dtype=np.float32)
    aligned = normalized.astype(np.float32)

    return {
        "vertices_aligned": aligned,
        "correction_matrix": R_corr,
        "center": center,
        "scale": scale,
        "target_pose": target.astype(np.float32),
        "bin_canonical_yaw": np.asarray([float(canonical_yaw)], np.float32),
        "actual_pose": actual.astype(np.float32),
    }


def to_original_image(points_224: np.ndarray, trans_params: np.ndarray) -> np.ndarray:
    """🎯 CRITICAL → Map 3DDFA image-plane coordinates to original top-left image coordinates.
    🔗 DEPENDS ON: engine._one() — вызывается для проекции ландмарков на оригинал
    💡 NOTE: Инвертирует Y (223 - y) т.к. 3DDFA использует bottom-left origin
    Координаты за границами не обрезаются: для mesh это валидная диагностика.
    Функция проверяет форму, конечность и геометрию transform, чтобы ошибочный
    transform не превращался в тихие Inf/NaN.
    """
    log_status("to_original_image", "complete")
    q = np.asarray(points_224, np.float32).copy()
    if q.ndim != 2 or q.shape[1] < 2:
        raise ValueError("points_224 must have shape (N,2+) ")
    if not np.isfinite(q[:, :2]).all():
        raise ValueError("points_224 contains NaN/Inf")
    trans = np.asarray(trans_params, np.float64).reshape(-1)
    if trans.size < 5 or not np.isfinite(trans[:5]).all():
        raise ValueError("trans_params must contain five finite values")
    q[:, 1] = 223.0 - q[:, 1]
    w0, h0, scale, cx, cy = map(float, trans[:5])
    if w0 <= 0 or h0 <= 0 or scale <= 0:
        raise ValueError("trans_params width, height and scale must be positive")
    w = max(int(w0 * scale), 1); h = max(int(h0 * scale), 1)
    left = int(w / 2 - 112 + (cx - w0 / 2) * scale)
    up = int(h / 2 - 112 + (h0 / 2 - cy) * scale)
    q[:, 0] = (q[:, 0] + left) / w * w0
    q[:, 1] = (q[:, 1] + up) / h * h0
    return q.astype(np.float32)


def reprojection_stats(projected: np.ndarray, expected: np.ndarray) -> dict[str, float]:
    log_status("reprojection_stats", "complete")
    a = np.asarray(projected, np.float64); b = np.asarray(expected, np.float64)
    if a.shape != b.shape or a.ndim != 2 or a.shape[0] == 0:
        raise ValueError(f"reprojection shape mismatch: {a.shape} vs {b.shape}")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("reprojection arrays contain NaN/Inf")
    dist = np.linalg.norm(a - b, axis=1)
    return {
        "rmse": float(np.sqrt(np.mean(dist * dist))),
        "p95": float(np.percentile(dist, 95)),
        "max": float(np.max(dist)),
    }


def pack_mask(mask: np.ndarray) -> np.ndarray:
    log_status("pack_mask", "complete")
    arr = np.asarray(mask)
    if arr.ndim != 1:
        raise ValueError("mask must be one-dimensional")
    return np.packbits(arr.astype(np.uint8), bitorder="little")


def unpack_mask(packed: np.ndarray, count: int) -> np.ndarray:
    log_status("unpack_mask", "complete")
    if int(count) < 0:
        raise ValueError("count must be non-negative")
    arr = np.asarray(packed, dtype=np.uint8)
    if arr.ndim != 1 or arr.size * 8 < int(count):
        raise ValueError("packed mask is too short for count")
    return np.unpackbits(arr, bitorder="little")[:int(count)].astype(np.uint8)
