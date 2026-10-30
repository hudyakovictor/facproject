from server.registry import metric
from metrics.common import nose_projection


@metric(
    "mesh_nose_projection",
    "Проекция носа / IOD",
    model="3ddfa_v3",
    unit="IOD",
    inputs=("ldm68",),
    poses=("frontal",),
)
def compute(ctx):
    return nose_projection(ctx["ldm68"])
