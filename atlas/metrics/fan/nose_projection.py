from server.registry import metric
from metrics.common import nose_projection


@metric(
    "fan_nose_projection",
    "Проекция носа / IOD",
    model="fan",
    unit="IOD",
    inputs=("fan68",),
)
def compute(ctx):
    return nose_projection(ctx["fan68"])
