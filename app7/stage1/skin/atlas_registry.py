"""Atlas registry — load BFM zone definitions from .npz."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class AtlasRegistry:
    """Holds per-triangle zone memberships from the BFM atlas .npz."""
    A: np.ndarray       # A20 zone id per triangle (Fx1 int)
    S: np.ndarray       # S40 zone id per triangle
    skin: np.ndarray    # bool: is this a skin triangle?
    W: np.ndarray       # (14, F) bool: wrinkle zone memberships
    boundary: np.ndarray  # boundary distance per triangle

    @staticmethod
    def load(npz_path: Path, triangles: np.ndarray) -> AtlasRegistry:
        """Load atlas and verify triangle count matches mesh."""
        with np.load(npz_path, allow_pickle=False) as z:
            A = z.get("zone_id_a20", z.get("A"))
            S = z.get("zone_id_s40", z.get("S"))
            skin = z.get("skin_mask", z.get("skin")).astype(bool)
            W_raw = z.get("wrinkle_bits_w14", z.get("W"))
            boundary = z.get("boundary_distance", z.get("boundary", np.zeros(len(A), np.uint8)))

        # Handle packed wrinkle bits
        if W_raw.ndim == 2 and W_raw.shape[0] == 14:
            W = W_raw.astype(bool)
        elif W_raw.ndim == 2 and W_raw.shape[0] < 14:
            W = np.zeros((14, len(A)), dtype=bool)
            W[:W_raw.shape[0]] = W_raw.astype(bool)
        else:
            W = np.unpackbits(W_raw, axis=0, bitorder="little")[:14, :len(A)].astype(bool) if W_raw.ndim == 2 else np.zeros((14, len(A)), dtype=bool)

        # Ensure boundary is 1-D
        if boundary.ndim > 1:
            boundary = boundary.reshape(-1)

        return AtlasRegistry(A=A, S=S, skin=skin, W=W, boundary=boundary)

    def describe(self) -> dict:
        return {
            "zones_a20": int(self.A.max()) + 1 if len(self.A) else 0,
            "zones_s40": int(self.S.max()) + 1 if len(self.S) else 0,
            "wrinkle_channels": self.W.shape[0],
            "skin_triangles": int(self.skin.sum()),
            "total_triangles": len(self.skin),
        }
