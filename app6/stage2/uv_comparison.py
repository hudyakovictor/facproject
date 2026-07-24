"""UV comparison helpers.

Old stage1.skin / stage2.skin package comparison was removed.
Stage1 now writes texture.json authenticity metrics from face_mask.png.
"""
from __future__ import annotations

class RemovedSkinPackageError(RuntimeError):
    pass

def compare_packages(*args, **kwargs):
    raise RemovedSkinPackageError(
        "Old skin package comparison removed. Use stage1 texture.json / skin_authenticity_score."
    )
