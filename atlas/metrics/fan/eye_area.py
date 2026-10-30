from server.registry import metric
from metrics.common import eye_area


@metric(
    "fan_eye_area", "Площадь глаз / IOD²", model="fan", unit="IOD²", inputs=("fan68",)
)
def compute(ctx):
    return eye_area(ctx["fan68"])
