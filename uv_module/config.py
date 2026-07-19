from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

MAX_UV_SIZE = 1000

@dataclass(frozen=True)
class UVExtractionConfig:
    uv_size: int = 1000
    super_sample: int = 2
    interpolation: str = "lanczos4"
    zbuffer_size: int = 1024
    depth_tolerance: float = 0.015
    angle_soft_lo: float = 0.05
    angle_soft_hi: float = 0.45
    observed_threshold: float = 0.55
    observed_erode_px: int = 1
    skin_mask_threshold: float = 0.5
    footprint_target_px: float = 0.8
    cache_dir: str | None = None
    # Legacy Stage-1 arguments kept only so the old call site can be replaced
    # without keeping the old UV package. They do not change UV Core behavior.
    enable_delighting: bool = False
    force_all_triangles_visible: bool = False
    device: str = "cpu"

    def __post_init__(self):
        if not 64 <= int(self.uv_size) <= MAX_UV_SIZE:
            raise ValueError(f"uv_size must be in 64..{MAX_UV_SIZE}")
        if not 1 <= int(self.super_sample) <= 4:
            raise ValueError("super_sample must be in 1..4")
        if self.interpolation not in {"linear", "cubic", "lanczos4"}:
            raise ValueError("unsupported interpolation")

    @property
    def grid_size(self) -> int:
        return int(self.uv_size) * int(self.super_sample)

    def resolved_cache_dir(self) -> Path:
        return Path(self.cache_dir) if self.cache_dir else Path.home() / ".cache" / "forensic_uv_v4"

@dataclass(frozen=True)
class MorphCompletionConfig:
    enabled: bool = True
    method: str = "uv_mirror"  # uv_mirror | disabled
    color_match: bool = False
    small_hole_max_area: int = 1200
    inpaint_radius: float = 3.0
    real_feather_px: int = 8
    hidden_feather_px: int = 18
    background: str = "black"  # black | median

    def __post_init__(self):
        if self.method not in {"uv_mirror", "disabled"}:
            raise ValueError("method must be uv_mirror or disabled")
        if self.background not in {"black", "median"}:
            raise ValueError("background must be black or median")
        if int(self.real_feather_px) < 0 or int(self.hidden_feather_px) < 0:
            raise ValueError("feather widths must be non-negative")
