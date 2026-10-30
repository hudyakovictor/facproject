from server.registry import metric
from metrics.common import jaw_ratio


@metric(
    "mesh_jaw_ratio",
    "Нижняя челюсть / контур",
    model="3ddfa_v3",
    unit="ratio",
    inputs=("ldm68",),
    poses=("frontal",),
)
def compute(ctx):
    return jaw_ratio(ctx["ldm68"])
