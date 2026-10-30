from server.registry import metric
import numpy as np


@metric(
    "ada_norm_quality",
    "Норма эмбеддинга",
    model="adaface",
    unit="norm",
    inputs=("ada_embedding",),
)
def compute(ctx):
    return np.linalg.norm(ctx["ada_embedding"])
