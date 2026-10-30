"""Independent source contours and diagnostic, non-causal correction controls."""
from __future__ import annotations

import cv2
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree

MP_UP = ((33, 246, 161, 160, 159, 158, 157, 173, 133), (263, 466, 388, 387, 386, 385, 384, 398, 362))
MP_LO = ((33, 7, 163, 144, 145, 153, 154, 155, 133), (263, 249, 390, 373, 374, 380, 381, 382, 362))
MP_LIP_UP = (61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291)
MP_LIP_LO = (61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291)
MP_LOWER_FACE = (234, 93, 132, 58, 172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 361, 323, 454)


def independent_landmarks(image: np.ndarray, client=None) -> dict:
    from morphing.backend.mp_worker import LandmarkerClient
    owned = client is None
    client = client or LandmarkerClient()
    ok, data = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("cannot encode oriented source for independent contour extraction")
    try:
        result = client.detect(data.tobytes())
        points = np.asarray(result["points_raw"], dtype=float)[:, :2]
        return {"points": points, "blendshapes": result["blendshapes"], "method": "MediaPipe478_original_pixels",
                "manual_validation_status": "not_manually_validated", "image_size": result["image_size"]}
    finally:
        if owned:
            client.close()


def interpolate_curve(points: np.ndarray, count: int = 25) -> np.ndarray:
    distances = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    if distances[-1] < 1e-6:
        return np.repeat(points[:1], count, axis=0)
    distances /= distances[-1]
    unique, indices = np.unique(distances, return_index=True)
    return np.column_stack([np.interp(np.linspace(0, 1, count), unique, points[indices, axis]) for axis in range(2)])


def curve_metrics(model: np.ndarray, observed: np.ndarray, face_scale: float, normal: np.ndarray) -> tuple[dict, np.ndarray, np.ndarray]:
    predicted, target = interpolate_curve(model), interpolate_curve(observed)
    delta = predicted - target
    error = np.linalg.norm(delta, axis=1)
    signed = delta @ normal
    return {"signed_mean_px": float(signed.mean()), "signed_median_px": float(np.median(signed)),
            "median_error_px": float(np.median(error)), "p95_error_px": float(np.quantile(error, 0.95)),
            "median_error_normalized": float(np.median(error) / face_scale),
            "p95_error_normalized": float(np.quantile(error, 0.95) / face_scale)}, predicted, target


def loop_area(upper, lower):
    points = np.concatenate((upper, lower[::-1]))
    return float(abs(np.sum(points[:, 0] * np.roll(points[:, 1], -1) - points[:, 1] * np.roll(points[:, 0], -1))) / 2)


def correction_controls(model_points: np.ndarray, observed_points: np.ndarray, face_scale: float) -> dict:
    affine, _ = cv2.estimateAffinePartial2D(model_points.astype(np.float32), observed_points.astype(np.float32), method=cv2.LMEDS)
    if affine is None:
        return {"status": "insufficient_data"}
    camera_like = np.column_stack((model_points, np.ones(len(model_points)))) @ affine.T
    residual = observed_points - camera_like
    unique, indices = np.unique(np.round(camera_like, 4), axis=0, return_index=True)
    if len(unique) < 4 or np.linalg.matrix_rank(np.column_stack((unique, np.ones(len(unique))))) < 3:
        return {"status": "insufficient_data", "camera_like_matrix": affine.tolist()}
    interpolator = RBFInterpolator(camera_like[indices], residual[indices], kernel="thin_plate_spline",
                                  smoothing=(0.002 * face_scale) ** 2, degree=1)
    limit = 0.03 * face_scale
    unbounded = interpolator(camera_like)
    magnitude = np.linalg.norm(unbounded, axis=1)

    def bounded_field(points):
        values = interpolator(points)
        values *= np.minimum(1, limit / np.maximum(np.linalg.norm(values, axis=1), 1e-8))[:, None]
        return values

    correction = bounded_field(camera_like)
    epsilon = max(0.5, 0.001 * face_scale)
    dx = (bounded_field(camera_like + [epsilon, 0]) - bounded_field(camera_like - [epsilon, 0])) / (2 * epsilon)
    dy = (bounded_field(camera_like + [0, epsilon]) - bounded_field(camera_like - [0, epsilon])) / (2 * epsilon)
    jacobian = np.stack((dx, dy), axis=2) + np.eye(2)
    determinant = np.linalg.det(jacobian)
    _, neighbours = cKDTree(camera_like).query(camera_like, k=min(4, len(camera_like)))
    smoothness = np.linalg.norm(correction[:, None] - correction[neighbours], axis=2)
    return {"status": "diagnostic_only", "camera_control": "2D_similarity_proxy_not_a_physical_camera_recalibration",
            "camera_like_matrix": affine.tolist(), "original_median_error_px": float(np.median(np.linalg.norm(model_points - observed_points, axis=1))),
            "camera_like_median_error_px": float(np.median(np.linalg.norm(residual, axis=1))),
            "local_median_error_px": float(np.median(np.linalg.norm(camera_like + correction - observed_points, axis=1))),
            "local_correction_median_px": float(np.median(magnitude)), "local_correction_p95_px": float(np.quantile(magnitude, 0.95)),
            "applied_correction_p95_px": float(np.quantile(np.linalg.norm(correction, axis=1), 0.95)),
            "cap_px": limit, "fraction_at_cap": float(np.mean(magnitude > limit)),
            "smoothness_mean_px": float(smoothness.mean()), "area_change_median": float(np.median(determinant)),
            "area_change_p95_abs": float(np.quantile(np.abs(determinant - 1), 0.95)),
            "correction_points": camera_like.tolist(), "correction_vectors": correction.tolist(),
            "meaning": "Required fit correction, not a cause or material diagnosis; original projection is not modified."}


def validate_contours(recon: dict, independent: dict, visibility_buffers: dict | None = None) -> dict:
    points = independent["points"]
    projected = recon["vertices_2d"]
    dense = projected[recon["ldm134_indices"]]
    sparse = projected[recon["ldm106_indices"]]
    scale = float(np.linalg.norm(points[33] - points[263]))
    if scale < 5:
        raise ValueError("independent facial normalization span unavailable")
    results, models, targets = {}, [], []
    for side, (upper, lower, start) in enumerate(zip(MP_UP, MP_LO, (0, 22), strict=True)):
        model_upper, model_lower = dense[start + 11:start + 22], dense[start:start + 11]
        observed_upper, observed_lower = points[list(upper)], points[list(lower)]
        axis = observed_upper[-1] - observed_upper[0]
        axis /= np.linalg.norm(axis)
        normal = np.array([-axis[1], axis[0]])
        if (observed_lower.mean(axis=0) - observed_upper.mean(axis=0)) @ normal < 0:
            normal *= -1
        up, predicted_up, target_up = curve_metrics(model_upper, observed_upper, scale, normal)
        lo, predicted_lo, target_lo = curve_metrics(model_lower, observed_lower, scale, normal)
        model_ends = (model_upper[[0, -1]] + model_lower[[0, -1]]) / 2
        observed_ends = observed_upper[[0, -1]]
        models.extend((predicted_up, predicted_lo))
        targets.extend((target_up, target_lo))
        model_width, observed_width = np.linalg.norm(np.diff(model_ends, axis=0)), np.linalg.norm(np.diff(observed_ends, axis=0))
        results[f"eye_{side}"] = {"upper": up, "lower": lo, "corner_errors_px": np.linalg.norm(model_ends - observed_ends, axis=1).tolist(),
                                  "width_difference_px": float(model_width - observed_width),
                                  "height_difference_px": float(np.linalg.norm(predicted_up - predicted_lo, axis=1).mean() - np.linalg.norm(target_up - target_lo, axis=1).mean()),
                                  "aperture_area_difference_px2": loop_area(model_upper, model_lower) - loop_area(observed_upper, observed_lower),
                                  "tilt_difference_deg": float((np.degrees(np.arctan2(*(model_ends[1] - model_ends[0])[::-1]) - np.arctan2(*axis[::-1])) + 180) % 360 - 180)}
    for name, model, observed in (("upper_lip", sparse[np.arange(84, 91)], points[list(MP_LIP_UP)]),
                                  ("lower_lip", sparse[[84, 95, 94, 93, 92, 91, 90]], points[list(MP_LIP_LO)])):
        metrics, predicted, target = curve_metrics(model, observed, scale, np.array([0, 1]))
        results[name] = metrics
        models.append(predicted)
        targets.append(target)
    results["nasal_alae"] = {"point_errors_px": np.linalg.norm(sparse[[58, 62]] - points[[98, 327]], axis=1).tolist(),
                              "note": "Correspondence is a sparse proxy, not a manually validated alar contour."}
    if visibility_buffers is not None:
        mask = (visibility_buffers["triangle_id"] >= 0).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if contours:
            contour = (max(contours, key=cv2.contourArea).reshape(-1, 2) / visibility_buffers["scale"]).astype(np.float32)
            observed = points[list(MP_LOWER_FACE)]
            signed = np.array([-cv2.pointPolygonTest(contour, tuple(point.astype(float)), True) for point in observed])
            results["lower_silhouette"] = {"signed_observation_to_projection_px": signed.tolist(),
                                           "median_abs_error_px": float(np.median(np.abs(signed))),
                                           "p95_abs_error_px": float(np.quantile(np.abs(signed), 0.95)),
                                           "projected_background_capture_candidate_fraction": float(np.mean(signed < -0.02 * scale)),
                                           "meaning": "negative means observed border lies inside the larger projected mask; external contour still requires manual validation"}
    results["correction_control"] = correction_controls(np.concatenate(models), np.concatenate(targets), scale)
    results["model_contour_points"] = np.concatenate(models).tolist()
    results["observed_contour_points"] = np.concatenate(targets).tolist()
    results.update({"normalization": "observed outer-canthal pixel span", "normalization_pixels": scale,
                    "observed_face_bbox": [float(points[:, 0].min()), float(points[:, 1].min()), float(points[:, 0].max()), float(points[:, 1].max())],
                    "method": independent["method"], "manual_validation_status": independent["manual_validation_status"],
                    "material_or_cause_inference": False})
    return results


def check_manual_contours(manual, independent):
    points = independent["points"]
    curves = {"eye_0_upper": MP_UP[0], "eye_0_lower": MP_LO[0], "eye_1_upper": MP_UP[1], "eye_1_lower": MP_LO[1],
              "upper_lip": MP_LIP_UP, "lower_lip": MP_LIP_LO, "lower_face": MP_LOWER_FACE}
    span = float(np.linalg.norm(points[33] - points[263]))
    errors = {}
    for name, coordinates in manual.items():
        if name not in curves:
            continue
        target = np.asarray(coordinates, dtype=float)
        if target.ndim != 2 or target.shape[1] != 2 or len(target) < 3 or not np.isfinite(target).all():
            raise ValueError("manual source contour must contain finite pixel coordinates")
        prediction = interpolate_curve(points[list(curves[name])], 50)
        target = interpolate_curve(target, 50)
        direct = np.linalg.norm(prediction - target, axis=1)
        reverse = np.linalg.norm(prediction - target[::-1], axis=1)
        distances = direct if direct.mean() <= reverse.mean() else reverse
        errors[name] = {"median_px": float(np.median(distances)), "p95_px": float(np.quantile(distances, 0.95)),
                        "p95_normalized": float(np.quantile(distances, 0.95) / span)}
    passed = len(errors) >= 2 and all(row["p95_normalized"] <= 0.02 for row in errors.values())
    return {"status": "manually_checked" if errors else "insufficient_data", "curves": errors, "passed_preset_tolerance": passed,
            "normalization": "observed outer-canthal span", "preset_p95_tolerance": 0.02}
