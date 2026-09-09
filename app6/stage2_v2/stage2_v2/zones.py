"""Anatomical zone map for landmark indices.

Provenance matters here more than anywhere else in the codebase, because a
zone label is what turns a number into a sentence. "Point 71 moved 1.4 mm" is
inert; "the left nasolabial fold moved 1.4 mm" is a claim about a face. If the
mapping is wrong, the arithmetic stays correct and the sentence becomes false.

So the zone map is *never* invented silently. There are exactly two sources:

  measured   - loaded from a project atlas file that was built from the mesh
               topology. Zone names from this source may be used in prose.
  partition  - a fallback that splits the landmark index range into contiguous
               blocks. It is a bookkeeping device so the pipeline can run
               without the atlas. Its labels are deliberately non-anatomical
               (`block_00`, ...) and `anatomical=False`, and the report layer
               refuses to name zones in prose when this source is active.

The fallback exists so a run does not crash. It does not exist so a report can
quietly attribute a change to a cheekbone it never located.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ZoneMap:
    """A landmark-index to zone-name mapping, with its provenance attached."""

    source: str  # "measured" | "partition"
    scheme: int
    zones: dict[str, list[int]]
    #: True only when zone names denote real anatomy and may appear in prose.
    anatomical: bool
    origin: str = ""

    @property
    def zone_names(self) -> list[str]:
        return sorted(self.zones)

    def covered(self) -> int:
        return len({i for indices in self.zones.values() for i in indices})

    def to_json(self) -> dict:
        return {
            "source": self.source,
            "origin": self.origin,
            "scheme": self.scheme,
            "anatomical": self.anatomical,
            "zone_count": len(self.zones),
            "covered_points": self.covered(),
            "zones": {name: list(idx) for name, idx in sorted(self.zones.items())},
        }


#: Candidate atlas locations, searched in order.
ATLAS_CANDIDATES = (
    "stage2/mesh_zone_indices.json",
    "atlas/landmark_zones.json",
    "atlas/landmark_zones_134.json",
)


def load_measured(project_root: Path, scheme: int = 134) -> ZoneMap | None:
    """Try to load a real, mesh-derived zone map. Returns None if absent."""
    project_root = Path(project_root)
    for relative in ATLAS_CANDIDATES:
        path = project_root / relative
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        raw = payload.get(f"ldm{scheme}") or payload.get("landmarks") or payload
        if not isinstance(raw, dict):
            continue
        zones: dict[str, list[int]] = {}
        for name, indices in raw.items():
            if not isinstance(indices, (list, tuple)):
                continue
            clean = [int(i) for i in indices if isinstance(i, (int, float))]
            clean = [i for i in clean if 0 <= i < scheme]
            if clean:
                zones[str(name)] = sorted(set(clean))
        if zones:
            return ZoneMap(
                source="measured",
                scheme=scheme,
                zones=zones,
                anatomical=True,
                origin=str(path),
            )
    return None


def build_partition(scheme: int = 134, blocks: int = 8) -> ZoneMap:
    """Fallback: contiguous index blocks with deliberately neutral names.

    Named `block_NN` rather than `cheek` or `jaw` precisely so that nobody -
    including the report generator - can mistake this for anatomy.
    """
    blocks = max(1, min(blocks, scheme))
    size = scheme // blocks
    zones: dict[str, list[int]] = {}
    for b in range(blocks):
        start = b * size
        end = scheme if b == blocks - 1 else (b + 1) * size
        zones[f"block_{b:02d}"] = list(range(start, end))
    return ZoneMap(
        source="partition",
        scheme=scheme,
        zones=zones,
        anatomical=False,
        origin=f"contiguous index partition into {blocks} blocks",
    )


def resolve(project_root: Path | None, scheme: int = 134) -> ZoneMap:
    """Load the measured atlas if available, otherwise the neutral partition."""
    if project_root is not None:
        measured = load_measured(project_root, scheme)
        if measured is not None:
            return measured
    return build_partition(scheme)
