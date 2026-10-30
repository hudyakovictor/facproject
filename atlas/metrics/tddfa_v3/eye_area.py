from server.registry import metric
from metrics.common import eye_area


@metric(
    "mesh_eye_area",
    "Площадь глаз / IOD²",
    model="3ddfa_v3",
    unit="IOD²",
    inputs=("ldm68",),
)
def compute(ctx):
    return eye_area(ctx["ldm68"])
