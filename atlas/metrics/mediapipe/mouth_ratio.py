from server.registry import metric
import numpy as np


@metric(
    "mp_mouth_ratio",
    "Раскрытие рта / IOD",
    model="mediapipe",
    unit="IOD",
    inputs=("mp478",),
)
def compute(ctx):
    p = ctx["mp478"]
    return np.linalg.norm(p[13] - p[14]) / max(np.linalg.norm(p[33] - p[263]), 1e-8)
