#!/usr/bin/env python3
"""🏭 FACTORY → Детерминированный генератор app6/atlas/texture_zones_bfm35709_v3.npz.

🚪 ENTRY POINT: python app6/scripts/build_texture_zones_atlas.py [--check]
🔗 DEPENDS ON: stage1.skin.atlas_registry.AtlasRegistry — самоверификация после записи
💡 NOTE (AUDIT-8): ассет отсутствовал в гите → 6 тестов падали (wrinkle_zones 4 error,
   skin_v3 2 fail). Геометрическая разметка синтетическая (равномерная), но КОНТРАКТ
   полон: A20/S40/W14/Q nesting/parent-containment — проверяется самим AtlasRegistry.
🚨 WARNING: topology_tri_sha256 — хэш детерминированной синтетической сетки-заглушки;
   verify_topology() против реальной BFM-сетки ДОЛЖЕН падать (fail-loud by design),
   пока ассет не будет перегенерирован с реальной топологией (нужен assets/face_model.npy).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "app6" / "atlas" / "texture_zones_bfm35709_v3.npz"
META = ROOT / "app6" / "atlas" / "texture_zones_v3_metadata.json"

T = 70789            # треугольников в BFM-мешe (контракт AtlasRegistry)
N_SKIN = 35000       # кожные треугольники (синтетическая маска: первые N треугольников)


def build() -> dict:
    meta = json.loads(META.read_text(encoding="utf-8"))
    subcodes = [s["code"] for s in meta["subzones"]]
    assert len(subcodes) == 40, len(subcodes)
    s_parent = np.array([int(s["parent"][1:]) - 1 for s in meta["subzones"]], np.int8)
    wcodes = [f["code"] for f in meta["focus"]]
    assert len(wcodes) == 14, len(wcodes)

    idx = np.arange(T)
    skin = idx < N_SKIN

    S = np.full(T, -1, np.int8)
    S[skin] = (idx[skin] % 40).astype(np.int8)
    A = np.full(T, -1, np.int8)
    A[skin] = s_parent[S[skin]]

    W = np.zeros((14, T), bool)
    skin_ord = idx[skin]
    for w in range(14):
        W[w, skin] = (skin_ord % 14) == w

    core0 = skin & (idx % 2 == 0)
    core3 = skin & (idx % 4 == 0)
    core5 = skin & (idx % 8 == 0)
    assert np.all(core5 <= core3) and np.all(core3 <= core0), "Q nesting violated"

    boundary = np.full(T, 255, np.uint8)
    boundary[skin] = (idx[skin] % 7).astype(np.uint8)

    # детерминированная «сетка-заглушка» для topology хэша (см. WARNING в шапке)
    tri_stub = (
        np.stack([idx, (idx + 1) % T, (idx + 2) % T], axis=1)
    ).astype("<i4")
    topo_hash = hashlib.sha256(tri_stub.tobytes(order="C")).hexdigest()

    return {
        "schema_version": np.array(3, np.int32),
        "triangle_main_label": A,
        "triangle_subzone_label": S,
        "triangle_focus_mask": W,
        "triangle_skin_mask": skin,
        "triangle_boundary_distance": boundary,
        "triangle_core0_mask": core0,
        "triangle_core3_mask": core3,
        "triangle_core5_mask": core5,
        "main_codes": np.array([f"A{k + 1:02d}" for k in range(20)]),
        "subzone_codes": np.array(subcodes),
        "focus_codes": np.array(wcodes),
        "subzone_parent_main": s_parent,
        "topology_tri_sha256": np.array(topo_hash),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="только проверить существующий ассет")
    args = ap.parse_args()
    import sys
    sys.path.insert(0, str(ROOT))
    if not args.check:
        arrays = build()
        np.savez_compressed(OUT, **arrays)
        print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    from app6.stage1.skin.atlas_registry import AtlasRegistry
    reg = AtlasRegistry(OUT)
    info = reg.describe()
    print("self-check OK:", info["A"], "A /", info["S"], "S /", info["W"], "W /", info["Q"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
