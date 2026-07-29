"""Регрессия D2/D3: атлас mesh-зон должен быть пригоден к измерению."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ATLAS_PATH = Path(__file__).resolve().parents[1] / "stage2" / "mesh_zone_indices.json"

#: Порог dense_mesh_pair: зона с меньшим числом точек не измеряется.
MIN_VERTICES_PER_ZONE = 4
BFM_VERTEX_COUNT = 35709


@pytest.fixture(scope="module")
def atlas() -> dict[str, list[int]]:
    return json.loads(ATLAS_PATH.read_text(encoding="utf-8"))


def test_every_zone_can_be_measured(atlas) -> None:
    """Ранее 11 зон из 23 имели <4 вершин: chin=1, temporal=2, jaw_angle=3."""
    degenerate = {name: len(idx) for name, idx in atlas.items()
                  if len(idx) < MIN_VERTICES_PER_ZONE}
    assert not degenerate, f"зоны непригодны для измерения: {degenerate}"


def test_zones_do_not_overlap(atlas) -> None:
    """nose_wing_L/R были полными подмножествами nose_bridge_tip (двойной учёт)."""
    names = sorted(atlas)
    overlaps = {}
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            shared = set(atlas[first]) & set(atlas[second])
            if shared:
                overlaps[f"{first}~{second}"] = len(shared)
    assert not overlaps, f"зоны пересекаются: {overlaps}"


def test_indices_inside_bfm_topology(atlas) -> None:
    for name, indices in atlas.items():
        assert indices, f"зона {name} пуста"
        assert min(indices) >= 0, f"отрицательный индекс в {name}"
        assert max(indices) < BFM_VERTEX_COUNT, f"индекс вне BFM в {name}"


def test_bone_zones_present(atlas) -> None:
    """Костные структуры — основа метода, они обязаны присутствовать."""
    required = {"orbit_L", "orbit_R", "nose_bridge_tip", "chin",
                "cheekbone_L", "cheekbone_R", "forehead",
                "temporal_L", "temporal_R", "jaw_angle_L", "jaw_angle_R"}
    assert required <= set(atlas), f"отсутствуют зоны: {sorted(required - set(atlas))}"


def test_atlas_matches_priority_zones(atlas) -> None:
    from app6.stage2.mesh_dense import PRIORITY_ZONES
    assert set(PRIORITY_ZONES) == set(atlas)
