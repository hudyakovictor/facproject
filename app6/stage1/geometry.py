"""
🎯 CRITICAL → Геометрия поз: canonical alignment и chronology alignment.

КЛЮЧЕВОЙ КОНТРАКТ (патч 01): фото в одном pose bin
приводятся к ИДЕНТИЧНОЙ позе (0, canonical_yaw, 0) полной коррекцией
pitch+yaw+roll через full_pose_correction_matrix (R_corr = R_target @ R_actual^T).
Это исключает шумы наклона головы при хронологическом сравнении.
🔗 DEPENDS ON: config.POSE_BINS (9 бинов yaw), используется reconstruction.py/engine.py.
💡 NOTE: row_rotation_matrix — конвенция row-vector (Rz@Ry@Rx)^T; координаты согласованы с 3DDFA_V3.
⚠️ nearest_canonical_yaw (#17) — soft assignment, в пайплайн пока не интегрирована.
"""
from __future__ import annotations

import numpy as np

from .config import POSE_BINS
from .status_logger import log_status, log_blocker, log_warning


def classify_pose(yaw: float) -> tuple[str, float]:
    log_status("classify_pose", "complete")
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
    for name, lo, hi, canonical in POSE_BINS:
        if lo <= float(yaw) < hi:
            return name, canonical
    return "out_of_supported_range", float(np.clip(yaw, -70.0, 70.0))
def nearest_canonical_yaw(yaw: float) -> tuple[str, float]:
    log_status("nearest_canonical_yaw", "in_progress", "Not integrated into main pipeline yet")
    """📊 METRIC → Ближайший canonical yaw (soft assignment).

    В отличие от classify_pose, использует ближайший canonical,
    а не центр бина. Устраняет резкие скачки на границах бинов.

    Пример: yaw=-12° → canonical=-17.5° (left_light), не 0° (frontal).

    ⚠️ IN PROGRESS:
    - Пока не используется в основном пайплайне
    - Нужно интегрировать в compute_chronology_alignment
    """
    log_status("nearest_canonical_yaw", "in_progress",
               "Not integrated into main pipeline yet")
    best_name = "frontal"
    best_canonical = 0.0
    best_dist = float("inf")
    for name, lo, hi, canonical in POSE_BINS:
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
    log_status("full_pose_correction_matrix", "complete")
    """Compute rotation matrix that transforms mesh from actual_pose to target_pose.

    This is the KEY function for chronology alignment. It ensures that all photos
    within the same pose bin have identical pose (0, canonical_yaw, 0), eliminating
    pitch/roll noise from the comparison.

    The correction is: R_corr = R_target @ R_actual^T
    Where R_actual is the rotation that produced the actual pose, and R_target
    is the rotation for the desired canonical pose.

    Args:
        actual_pose_deg: [pitch, yaw, roll] in degrees from 3DDFA
        target_pose_deg: [pitch, yaw, roll] in degrees for canonical pose

    Returns:
        3x3 rotation matrix (row-vector convention, float32)
    """
    log_status("full_pose_correction_matrix", "complete")
    actual = np.asarray(actual_pose_deg, np.float64)
    target = np.asarray(target_pose_deg, np.float64)

    # R_actual: rotation matrix that produced the actual pose
    R_actual = row_rotation_matrix(float(actual[0]), float(actual[1]), float(actual[2])).T
    # R_target: rotation matrix for the target canonical pose
    R_target = row_rotation_matrix(float(target[0]), float(target[1]), float(target[2])).T

    # Correction: undo actual rotation, then apply target rotation
    R_corr = (R_target @ R_actual.T).T.astype(np.float32)

    return R_corr


def normalize_mesh(mesh: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    log_status("normalize_mesh", "complete")
    """Normalize mesh to canonical scale and center.

    Uses RMS scale over the entire mesh. For chronology, this is applied
    BEFORE pose correction so that scale is consistent across all photos.
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
    log_status("normalize_mesh_landmark_anchored", "complete")
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
    log_status("normalize_mesh_landmark_anchored", "complete")
    mesh = np.asarray(mesh, np.float32)
    center = mesh.mean(axis=0)
    centered = mesh - center

    if landmark_indices is not None:
        idx1, idx2 = anchor_pair
        p1 = mesh[landmark_indices[idx1]]
        p2 = mesh[landmark_indices[idx2]]
    else:
        p1 = mesh[anchor_pair[0]]
        p2 = mesh[anchor_pair[1]]

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
    log_status("compute_chronology_alignment", "complete")
    """Full alignment pipeline for chronology comparison.

    This is the main entry point for producing aligned vertices suitable
    for chronological comparison within a pose bin.

    Steps:
    1. Normalize mesh (center + scale)
    2. Compute full pose correction matrix (corrects pitch, yaw, AND roll)
    3. Apply correction to get chronology-aligned vertices

    Args:
        vertices: (N, 3) vertex array (identity-only recommended)
        actual_pose_deg: [pitch, yaw, roll] from 3DDFA
        canonical_yaw: target yaw for the pose bin
        normalization: "rms" for full-mesh RMS, "landmark" for eye-distance anchored

    Returns:
        dict with:
            - vertices_aligned: (N, 3) aligned vertices
            - correction_matrix: (3, 3) applied rotation
            - center: (3,) applied translation
            - scale: float applied scale
            - target_pose: [0, canonical_yaw, 0]
            - actual_pose: original [pitch, yaw, roll]
    """
    log_status("compute_chronology_alignment", "complete")
    actual = np.asarray(actual_pose_deg, np.float64)
    target = np.array([0.0, float(canonical_yaw), 0.0], np.float64)

    # Step 1: Normalize
    if normalization == "landmark":
        normalized, center, scale = normalize_mesh_landmark_anchored(vertices)
    else:
        normalized, center, scale = normalize_mesh(vertices)

    # Step 2: Compute full pose correction
    R_corr = full_pose_correction_matrix(actual, target)

    # Step 3: Apply correction
    aligned = (normalized @ R_corr).astype(np.float32)

    return {
        "vertices_aligned": aligned,
        "correction_matrix": R_corr,
        "center": center,
        "scale": scale,
        "target_pose": target.astype(np.float32),
        "actual_pose": actual.astype(np.float32),
    }


def to_original_image(points_224: np.ndarray, trans_params: np.ndarray) -> np.ndarray:
    log_status("to_original_image", "in_progress", "No bounds check on output coordinates")
    """🎯 CRITICAL → Map 3DDFA image-plane coordinates to original top-left image coordinates.
    🔗 DEPENDS ON: engine._one() — вызывается для проекции ландмарков на оригинал
    💡 NOTE: Инвертирует Y (223 - y) т.к. 3DDFA использует bottom-left origin
    ⚠️ IN PROGRESS: Нет проверки что результат в пределах изображения
    """
    log_status("to_original_image", "in_progress",
               "No bounds check on output coordinates")
    q = np.asarray(points_224, np.float32).copy()
    q[:, 1] = 223.0 - q[:, 1]
    w0, h0, scale, cx, cy = map(float, np.asarray(trans_params).reshape(-1)[:5])
    w = max(int(w0 * scale), 1); h = max(int(h0 * scale), 1)
    left = int(w / 2 - 112 + (cx - w0 / 2) * scale)
    up = int(h / 2 - 112 + (h0 / 2 - cy) * scale)
    q[:, 0] = (q[:, 0] + left) / w * w0
    q[:, 1] = (q[:, 1] + up) / h * h0
    return q.astype(np.float32)


def reprojection_stats(projected: np.ndarray, expected: np.ndarray) -> dict[str, float]:
    log_status("reprojection_stats", "complete")
    a = np.asarray(projected, np.float64); b = np.asarray(expected, np.float64)
    if a.shape != b.shape:
        raise ValueError(f"reprojection shape mismatch: {a.shape} vs {b.shape}")
    dist = np.linalg.norm(a - b, axis=1)
    return {
        "rmse": float(np.sqrt(np.mean(dist * dist))),
        "p95": float(np.percentile(dist, 95)),
        "max": float(np.max(dist)),
    }


def pack_mask(mask: np.ndarray) -> np.ndarray:
    log_status("pack_mask", "complete")
    return np.packbits(np.asarray(mask, dtype=np.uint8), bitorder="little")


def unpack_mask(packed: np.ndarray, count: int) -> np.ndarray:
    log_status("unpack_mask", "complete")
    return np.unpackbits(np.asarray(packed, dtype=np.uint8), bitorder="little")[:count].astype(np.uint8)
