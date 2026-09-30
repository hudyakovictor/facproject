"""Input, reconstruction and mesh quality gates for morphing jobs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class QualityThresholds:
    min_width: int = 160
    min_height: int = 160
    min_blur: float = 20.0
    min_contrast: float = 8.0
    min_brightness: float = 12.0
    max_brightness: float = 245.0
    max_clip_fraction: float = 0.15
    min_face_area_fraction: float = 0.02
    max_face_area_fraction: float = 0.85
    max_center_offset_fraction: float = 0.30
    min_entropy_bits: float = 1.0
    max_nonfinite_fraction: float = 0.0
    max_mesh_extent: float = 10.0

    def __post_init__(self) -> None:
        if self.min_width < 1 or self.min_height < 1:
            raise ValueError("minimum image dimensions must be positive")
        if not 0 <= self.max_clip_fraction <= 1:
            raise ValueError("max_clip_fraction must be between 0 and 1")
        if not 0 <= self.min_face_area_fraction <= self.max_face_area_fraction <= 1:
            raise ValueError("face area fractions must satisfy 0 <= min <= max <= 1")
        if self.max_center_offset_fraction < 0 or self.min_blur < 0 or self.min_entropy_bits < 0:
            raise ValueError("quality thresholds cannot be negative")
        if self.max_nonfinite_fraction < 0 or self.max_mesh_extent <= 0:
            raise ValueError("mesh thresholds must be positive")

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class QualityFinding:
    code: str
    severity: str
    message: str
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
        }
        if self.evidence:
            payload["evidence"] = self.evidence
        return payload


@dataclass
class QualityReport:
    status: str
    score: float
    metrics: dict[str, Any]
    findings: list[QualityFinding]
    thresholds: QualityThresholds

    @property
    def accepted(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "accepted": self.accepted,
            "score": round(float(self.score), 2),
            "metrics": self.metrics,
            "findings": [finding.to_dict() for finding in self.findings],
            "thresholds": self.thresholds.to_dict(),
        }


def _gray(image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    if array.ndim == 2:
        return array.astype(np.float32)
    if array.ndim == 3 and array.shape[2] >= 3:
        # OpenCV BGR coefficients keep this compatible with the backend's
        # decoded images while avoiding an import-time dependency on cv2.
        bgr = array[:, :, :3].astype(np.float32)
        return bgr[:, :, 0] * 0.114 + bgr[:, :, 1] * 0.587 + bgr[:, :, 2] * 0.299
    raise ValueError("image must be HxW or HxWx3")


def _laplacian_variance(gray: np.ndarray) -> float:
    padded = np.pad(gray, 1, mode="edge")
    laplacian = (
        padded[:-2, 1:-1] + padded[2:, 1:-1]
        + padded[1:-1, :-2] + padded[1:-1, 2:]
        - 4.0 * padded[1:-1, 1:-1]
    )
    return float(np.var(laplacian))


def _entropy(gray: np.ndarray, bins: int = 64) -> float:
    # Fixed 8-bit range makes values comparable across input images.
    histogram, _ = np.histogram(np.clip(gray, 0, 255), bins=bins, range=(0, 256))
    probabilities = histogram.astype(np.float64)
    probabilities = probabilities[probabilities > 0] / max(float(histogram.sum()), 1.0)
    return float(-np.sum(probabilities * np.log2(probabilities)))


def _gradient_magnitude(gray: np.ndarray) -> np.ndarray:
    padded = np.pad(gray, 1, mode="edge")
    gx = (padded[1:-1, 2:] - padded[1:-1, :-2]) * 0.5
    gy = (padded[2:, 1:-1] - padded[:-2, 1:-1]) * 0.5
    return np.hypot(gx, gy)


def image_metrics(image: np.ndarray) -> dict[str, float | int]:
    array = np.asarray(image)
    if array.ndim not in (2, 3) or array.shape[0] < 1 or array.shape[1] < 1:
        raise ValueError("image must be non-empty")
    if not np.isfinite(array).all():
        raise ValueError("image pixels must be finite")
    gray = _gray(array)
    if np.max(gray) <= 1.0 and np.min(gray) >= 0.0:
        gray = gray * 255.0
    clipped_low = float(np.mean(gray <= 2.0))
    clipped_high = float(np.mean(gray >= 253.0))
    return {
        "width": int(array.shape[1]),
        "height": int(array.shape[0]),
        "channels": int(1 if array.ndim == 2 else array.shape[2]),
        "blur_laplacian_variance": round(_laplacian_variance(gray), 6),
        "entropy_bits": round(_entropy(gray), 6),
        "edge_fraction": round(float(np.mean(np.abs(_gradient_magnitude(gray)) > 24.0)), 6),
        "contrast_std": round(float(np.std(gray)), 6),
        "brightness_mean": round(float(np.mean(gray)), 6),
        "brightness_median": round(float(np.median(gray)), 6),
        "clipped_low_fraction": round(clipped_low, 6),
        "clipped_high_fraction": round(clipped_high, 6),
        "dynamic_range": round(float(np.percentile(gray, 99) - np.percentile(gray, 1)), 6),
    }


def _quality_score(findings: list[QualityFinding], metrics: Mapping[str, Any]) -> float:
    score = 100.0
    deductions = {"critical": 55.0, "error": 30.0, "warning": 12.0, "info": 2.0}
    for finding in findings:
        score -= deductions.get(finding.severity, 5.0)
    return float(np.clip(score, 0.0, 100.0))


def evaluate_image(
    image: np.ndarray,
    thresholds: QualityThresholds | None = None,
    label: str = "image",
    face_box: tuple[float, float, float, float] | None = None,
) -> QualityReport:
    limits = thresholds or QualityThresholds()
    metrics = image_metrics(image)
    findings: list[QualityFinding] = []
    if metrics["width"] < limits.min_width or metrics["height"] < limits.min_height:
        findings.append(QualityFinding("image_too_small", "error", f"{label}: resolution is too small", f"{metrics['width']}x{metrics['height']}", f">={limits.min_width}x{limits.min_height}"))
    if metrics["blur_laplacian_variance"] < limits.min_blur:
        findings.append(QualityFinding("low_sharpness", "warning", f"{label}: image may be blurred", metrics["blur_laplacian_variance"], limits.min_blur))
    if metrics["contrast_std"] < limits.min_contrast:
        findings.append(QualityFinding("low_contrast", "warning", f"{label}: low local contrast", metrics["contrast_std"], limits.min_contrast))
    if metrics["entropy_bits"] < limits.min_entropy_bits:
        findings.append(QualityFinding("low_information", "warning", f"{label}: image has very low visual information", metrics["entropy_bits"], limits.min_entropy_bits))
    if metrics["brightness_mean"] < limits.min_brightness or metrics["brightness_mean"] > limits.max_brightness:
        findings.append(QualityFinding("bad_exposure", "warning", f"{label}: exposure is outside the recommended range", metrics["brightness_mean"], f"{limits.min_brightness}..{limits.max_brightness}"))
    clip = max(metrics["clipped_low_fraction"], metrics["clipped_high_fraction"])
    if clip > limits.max_clip_fraction:
        findings.append(QualityFinding("clipping", "warning", f"{label}: too many clipped pixels", clip, limits.max_clip_fraction))
    if face_box is not None:
        x, y, width, height = (float(value) for value in face_box)
        image_width, image_height = float(metrics["width"]), float(metrics["height"])
        if not np.isfinite([x, y, width, height]).all() or width <= 0 or height <= 0:
            raise ValueError("face_box must contain finite x, y, width and height")
        area_fraction = width * height / (image_width * image_height)
        center_offset = float(np.hypot((x + width / 2) / image_width - 0.5, (y + height / 2) / image_height - 0.5))
        metrics["face_area_fraction"] = round(area_fraction, 6)
        metrics["face_center_offset_fraction"] = round(center_offset, 6)
        if area_fraction < limits.min_face_area_fraction:
            findings.append(QualityFinding("face_too_small", "warning", f"{label}: detected face occupies a small part of the image", area_fraction, limits.min_face_area_fraction))
        if area_fraction > limits.max_face_area_fraction:
            findings.append(QualityFinding("face_too_large", "warning", f"{label}: detected face may be cropped", area_fraction, limits.max_face_area_fraction))
        if center_offset > limits.max_center_offset_fraction:
            findings.append(QualityFinding("face_off_center", "info", f"{label}: detected face is off-center", center_offset, limits.max_center_offset_fraction))
    status = "fail" if any(item.severity in {"critical", "error"} for item in findings) else "warn" if findings else "pass"
    return QualityReport(status, _quality_score(findings, metrics), metrics, findings, limits)


def mesh_metrics(vertices: np.ndarray, triangles: np.ndarray | None = None) -> dict[str, Any]:
    points = np.asarray(vertices, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) == 0:
        raise ValueError("vertices must have non-empty shape (N, 3)")
    finite_mask = np.isfinite(points).all(axis=1)
    centroid = np.mean(points[finite_mask], axis=0) if np.any(finite_mask) else np.zeros(3)
    centered = points[finite_mask] - centroid
    radii = np.linalg.norm(centered, axis=1) if len(centered) else np.array([np.inf])
    metrics: dict[str, Any] = {
        "vertex_count": int(len(points)),
        "nonfinite_vertices": int(np.sum(~finite_mask)),
        "nonfinite_fraction": round(float(np.mean(~finite_mask)), 8),
        "centroid": [round(float(value), 8) for value in centroid],
        "extent_min": [round(float(value), 8) for value in np.min(points[finite_mask], axis=0)] if np.any(finite_mask) else [None] * 3,
        "extent_max": [round(float(value), 8) for value in np.max(points[finite_mask], axis=0)] if np.any(finite_mask) else [None] * 3,
        "radius_mean": round(float(np.mean(radii)), 8) if np.isfinite(radii).all() else 0.0,
        "radius_max": round(float(np.max(radii)), 8) if np.isfinite(radii).all() else 0.0,
    }
    if triangles is not None:
        faces = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
        valid = (faces >= 0).all(axis=1) & (faces < len(points)).all(axis=1)
        metrics["triangle_count"] = int(len(faces))
        metrics["repeated_index_triangles"] = int(np.sum((faces[:, 0] == faces[:, 1]) | (faces[:, 1] == faces[:, 2]) | (faces[:, 2] == faces[:, 0])))
        if np.any(valid):
            valid_faces = faces[valid]
            directed_edges = np.concatenate((valid_faces[:, [0, 1]], valid_faces[:, [1, 2]], valid_faces[:, [2, 0]]), axis=0)
            undirected_edges = np.sort(directed_edges, axis=1)
            _, edge_use_counts = np.unique(undirected_edges, axis=0, return_counts=True)
            metrics["unique_edge_count"] = int(len(edge_use_counts))
            metrics["boundary_edge_count"] = int(np.sum(edge_use_counts == 1))
            metrics["nonmanifold_edge_count"] = int(np.sum(edge_use_counts > 2))
            metrics["boundary_edge_fraction"] = round(float(np.mean(edge_use_counts == 1)), 8)
        else:
            metrics["unique_edge_count"] = 0
            metrics["boundary_edge_count"] = 0
            metrics["nonmanifold_edge_count"] = 0
            metrics["boundary_edge_fraction"] = 0.0
        metrics["invalid_triangles"] = int(np.sum(~valid))
        geometric_valid = valid.copy()
        if np.any(valid) and np.any(~finite_mask):
            geometric_valid[valid] &= finite_mask[faces[valid]].all(axis=1)
        metrics["nonfinite_triangles"] = int(np.sum(valid & ~geometric_valid))
        if np.any(geometric_valid):
            tri_points = points[faces[geometric_valid]]
            area2 = np.linalg.norm(np.cross(tri_points[:, 1] - tri_points[:, 0], tri_points[:, 2] - tri_points[:, 0]), axis=1)
            metrics["degenerate_triangles"] = int(np.sum(area2 <= 1e-10))
            metrics["triangle_area_median"] = round(float(np.median(area2 / 2.0)), 10)
        else:
            metrics["degenerate_triangles"] = 0
            metrics["triangle_area_median"] = 0.0
    return metrics


def displacement_metrics(vertices_a: np.ndarray, vertices_b: np.ndarray, threshold: float = 0.025) -> dict[str, float]:
    a = np.asarray(vertices_a, dtype=np.float64)
    b = np.asarray(vertices_b, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 2 or a.shape[1] != 3 or len(a) == 0:
        raise ValueError("displacement meshes must have the same shape (N, 3) with at least one vertex")
    if not np.isfinite(a).all() or not np.isfinite(b).all() or not np.isfinite(threshold) or threshold < 0:
        raise ValueError("displacement inputs and threshold must be finite; threshold must be non-negative")
    delta = np.linalg.norm(a - b, axis=1)
    return {
        "mean": round(float(np.mean(delta)), 8),
        "median": round(float(np.median(delta)), 8),
        "p95": round(float(np.percentile(delta, 95)), 8),
        "max": round(float(np.max(delta)), 8),
        "threshold": float(threshold),
        "above_threshold_fraction": round(float(np.mean(delta > threshold)), 8),
        "finite": bool(np.isfinite(delta).all()),
    }


def evaluate_mesh(vertices: np.ndarray, triangles: np.ndarray | None = None, thresholds: QualityThresholds | None = None, label: str = "mesh") -> QualityReport:
    limits = thresholds or QualityThresholds()
    metrics = mesh_metrics(vertices, triangles)
    findings: list[QualityFinding] = []
    if metrics["nonfinite_fraction"] > limits.max_nonfinite_fraction:
        findings.append(QualityFinding("nonfinite_mesh", "critical", f"{label}: mesh contains non-finite vertices", metrics["nonfinite_fraction"], limits.max_nonfinite_fraction))
    if metrics["radius_max"] > limits.max_mesh_extent:
        findings.append(QualityFinding("mesh_extent_outlier", "warning", f"{label}: canonical extent is unusually large", metrics["radius_max"], limits.max_mesh_extent))
    if metrics.get("invalid_triangles", 0):
        findings.append(QualityFinding("invalid_triangles", "error", f"{label}: topology has invalid indices", metrics["invalid_triangles"], 0))
    if metrics.get("degenerate_triangles", 0):
        findings.append(QualityFinding("degenerate_triangles", "warning", f"{label}: topology has degenerate triangles", metrics["degenerate_triangles"], 0))
    if metrics.get("nonmanifold_edge_count", 0):
        findings.append(QualityFinding("nonmanifold_edges", "warning", f"{label}: some edges belong to more than two triangles", metrics["nonmanifold_edge_count"], 0))
    status = "fail" if any(item.severity in {"critical", "error"} for item in findings) else "warn" if findings else "pass"
    return QualityReport(status, _quality_score(findings, metrics), metrics, findings, limits)


def compare_quality(report_a: QualityReport, report_b: QualityReport) -> dict[str, Any]:
    findings = [*report_a.findings, *report_b.findings]
    return {
        "status": "fail" if any(item.severity in {"critical", "error"} for item in findings) else "warn" if findings else "pass",
        "score": round(float((report_a.score + report_b.score) / 2.0), 2),
        "a": report_a.to_dict(),
        "b": report_b.to_dict(),
        "shared_findings": [item.to_dict() for item in findings],
    }


def quality_schema() -> dict[str, Any]:
    return {
        "schema": "facproject-morphing-quality-v1",
        "image_metrics": ["width", "height", "blur_laplacian_variance", "contrast_std", "brightness_mean", "clipped_low_fraction", "clipped_high_fraction"],
        "mesh_metrics": ["vertex_count", "nonfinite_fraction", "radius_mean", "radius_max", "invalid_triangles", "degenerate_triangles", "unique_edge_count", "boundary_edge_count", "nonmanifold_edge_count"],
        "severity": ["info", "warning", "error", "critical"],
        "defaults": QualityThresholds().to_dict(),
    }
