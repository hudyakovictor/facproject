from server.registry import metric
from metrics.common import cosine


@metric(
    "ada_pair_cos",
    "Cosine к предыдущему",
    model="adaface",
    unit="cosine",
    inputs=("ada_embedding", "ada_previous"),
)
def compute(ctx):
    return cosine(ctx["ada_embedding"], ctx["ada_previous"])
