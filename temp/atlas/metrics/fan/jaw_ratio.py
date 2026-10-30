from server.registry import metric
from metrics.common import jaw_ratio


@metric(
    "fan_jaw_ratio",
    "Нижняя челюсть / контур",
    model="fan",
    unit="ratio",
    inputs=("fan68",),
)
def compute(ctx):
    return jaw_ratio(ctx["fan68"])
