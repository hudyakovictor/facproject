"""Copy into metrics/tddfa_v3/mesh_height.py, then click «Обновить».
A real geometric example, not a medical metric. No frontend changes required.
"""
from server.registry import metric
import numpy as np

@metric('mesh_height_example', 'Высота реконструкции', model='3ddfa_v3', unit='IOD₀', inputs=('vertices',))
def compute(ctx):
    return np.ptp(ctx['vertices'][:, 1])
