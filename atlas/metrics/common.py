import numpy as np


def polygon_area(p):
    return float(
        abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1)))
        / 2
    )


def iod(lm):
    return max(float(np.linalg.norm(lm[36:42].mean(0) - lm[42:48].mean(0))), 1e-8)


def eye_area(lm):
    return (polygon_area(lm[36:42, :2]) + polygon_area(lm[42:48, :2])) / (
        2 * iod(lm) ** 2
    )


def jaw_ratio(lm):
    return float(
        np.linalg.norm(lm[4] - lm[12]) / max(np.linalg.norm(lm[0] - lm[16]), 1e-8)
    )


def nose_projection(lm):
    if lm.shape[1] < 3:
        return float("nan")
    return float((lm[30, 2] - (lm[27, 2] + lm[33, 2]) / 2) / iod(lm))


def cosine(a, b):
    return float(1 - np.dot(a, b) / (max(np.linalg.norm(a) * np.linalg.norm(b), 1e-12)))
