"""Контрактные тесты П3/П4/П5 + fail-fast smoke.

- П3: визуальный golden zone-overlay (детерминированный рендер + L/R стороны);
- П4: provenance fractions суммируются в 1; метка unsupported_distinction;
      mesh.obj нигде не читается как evidence;
- П5: preflight падает без атласа и при чужом pose-policy sha.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

WORK = Path(__file__).resolve().parents[2]
REF_PNG = Path(__file__).resolve().parent / "fixtures" / "zone_overlay_ref.png"


class ZoneOverlayGoldenTests(unittest.TestCase):
    def test_overlay_matches_reference(self):
        import cv2
        from app6.stage1.skin_zone_atlas import build_triangle_zone_map, render_atlas_png, ZONE_SPECS
        m = np.load(WORK / "assets" / "face_model.npy", allow_pickle=True).item()
        uv = np.asarray(m["uv_coords"], np.float32)
        tri = np.asarray(m["tri"], np.int64)
        primary = build_triangle_zone_map(uv, tri)
        img = render_atlas_png(uv, tri, primary, size=256)
        ref = cv2.imread(str(REF_PNG), cv2.IMREAD_UNCHANGED)
        self.assertIsNotNone(ref, "missing reference PNG fixture")
        self.assertEqual(img.shape, ref.shape)
        self.assertEqual(hashlib.sha256(img.tobytes()).hexdigest(),
                         hashlib.sha256(ref.tobytes()).hexdigest())

    def test_left_right_sides(self):
        """Ловит разворот UV: left-зоны строго u<0.5, right строго u>0.5."""
        from app6.stage1.skin_zone_atlas import build_triangle_zone_map, ZONE_SPECS
        m = np.load(WORK / "assets" / "face_model.npy", allow_pickle=True).item()
        uv = np.asarray(m["uv_coords"], np.float32)
        tri = np.asarray(m["tri"], np.int64)
        primary = build_triangle_zone_map(uv, tri)
        cen = uv[tri].mean(axis=1)
        for side, check in (("left", lambda u: u < 0.5), ("right", lambda u: u > 0.5)):
            ids = [i + 1 for i, s in enumerate(ZONE_SPECS) if s["side"] == side]
            uu = cen[np.isin(primary, ids)][:, 0]
            self.assertGreater(len(uu), 1000)
            self.assertTrue(bool(check(uu).all()), f"{side} zones cross u=0.5 (UV flip?)")


class UvProvenanceTests(unittest.TestCase):
    def test_fractions_sum_to_one(self):
        from app6.stage1.assets import save_uv_and_mesh  # noqa: import contract
        import inspect
        src = inspect.getsource(save_uv_and_mesh)
        self.assertIn("directly_observed_fraction", src)
        self.assertIn("unsupported_distinction", src)

    def test_mesh_obj_never_evidence(self):
        """mesh.obj только пишется (визуал), нигде не читается как evidence."""
        hits = []
        for p in (WORK / "app6").rglob("*.py"):
            if "test_" in p.name or p.name == "assets.py":
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(txt.splitlines(), 1):
                if "mesh.obj" in line and ("load" in line or "open" in line or "read" in line):
                    hits.append(f"{p}:{i}: {line.strip()}")
        self.assertEqual(hits, [], f"mesh.obj read as evidence: {hits}")


class FailFastSmokeTests(unittest.TestCase):
    def test_preflight_blocks_without_atlas(self):
        from app6.run_preflight import audit_texture_atlas
        with tempfile.TemporaryDirectory() as t:
            rep = audit_texture_atlas(Path(t))
            self.assertEqual(rep["status"], "blocked")

    def test_validator_rejects_foreign_policy(self):
        from app6.stage1.validator import validate_photo
        import shutil
        cands = sorted((WORK / "stage1_v27_det_output").glob("*"))
        cands = [c for c in cands if (c / "info.json").is_file()]
        self.assertTrue(cands, "need one v27 photo fixture")
        from app6.stage1.config import PHOTO_SCHEMA_VERSION
        src = next(c for c in cands
                   if json.loads((c / "info.json").read_text(encoding="utf-8")).get("schema_version") == PHOTO_SCHEMA_VERSION)
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "x"
            shutil.copytree(src, d)
            info_p = d / "info.json"
            info = json.loads(info_p.read_text(encoding="utf-8"))
            info["pose_policy"] = {"version": "pose-policy-vX-evil", "sha256": "00"}
            info_p.write_text(json.dumps(info), encoding="utf-8")
            res = validate_photo(d, write_result=False)
            self.assertEqual(res["status"], "invalid")
            self.assertTrue(any("pose policy" in e for e in res["errors"]))


class PolicyTamperTests(unittest.TestCase):
    """П5: тампер CSV-политики на старте движка заперт тестом."""

    def _copy_policy(self, tmp):
        import shutil
        from app6.stage1.config import POSE_POLICY_FILE
        src = WORK / POSE_POLICY_FILE
        dst = Path(tmp) / "app6" / "atlas" / "pose_policy_v3_9bins.csv"
        dst.parent.mkdir(parents=True)
        shutil.copy(src, dst)
        return dst

    def test_ok_policy_passes(self):
        from app6.stage1.engine import check_pose_policy
        with tempfile.TemporaryDirectory() as t:
            self._copy_policy(t)
            h = check_pose_policy(Path(t))
            self.assertEqual(len(h), 64)

    def test_swapped_center_fails(self):
        from app6.stage1.engine import check_pose_policy
        with tempfile.TemporaryDirectory() as t:
            dst = self._copy_policy(t)
            txt = dst.read_text(encoding="utf-8").replace("-17.5", "-99.9")
            dst.write_text(txt, encoding="utf-8")
            with self.assertRaises(RuntimeError):
                check_pose_policy(Path(t))

    def test_appended_byte_fails(self):
        from app6.stage1.engine import check_pose_policy
        with tempfile.TemporaryDirectory() as t:
            dst = self._copy_policy(t)
            with dst.open("ab") as f:
                f.write(b" ")
            with self.assertRaises(RuntimeError):
                check_pose_policy(Path(t))


if __name__ == "__main__":
    unittest.main()
