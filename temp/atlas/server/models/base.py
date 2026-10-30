"""Stable boundary for subsequent model adapters.
Coordinates must explicitly declare their system and units. A 2D output must NEVER
be silently treated as a true 3D point set. Future adapters can append independent
NPZ artifacts without invalidating 3DDFA features.
"""

from typing import Protocol, Any
from pathlib import Path
import numpy as np
from PIL import Image


class FeatureExtractor(Protocol):
    def infer(
        self, path: Path, precropped: bool = False
    ) -> tuple[dict[str, np.ndarray], dict[str, Any], Image.Image]: ...
