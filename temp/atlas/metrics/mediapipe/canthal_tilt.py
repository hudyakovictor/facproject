from server.registry import metric
import numpy as np


@metric(
    "mp_canthal_tilt", "Наклон глаз", model="mediapipe", unit="°", inputs=("mp478",)
)
def compute(ctx):
    p = ctx["mp478"]
    v = p[133] - p[33]
    return np.degrees(np.arctan2(v[1], v[0]))
