from server.registry import metric
from metrics.common import cosine


@metric(
    "ada_cos_to_centroid",
    "Cosine до центроида",
    model="adaface",
    unit="cosine",
    inputs=("ada_embedding", "ada_centroid"),
)
def compute(ctx):
    return cosine(ctx["ada_embedding"], ctx["ada_centroid"])
