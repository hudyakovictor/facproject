from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageOps

from app6.archive_adapter import (
    ArchiveRecord, group_by_person_pose, load_archive_records,
    safe_extract_archive, with_synthetic_dates,
)
from app6.stage1.input_provenance import _parse_exif_date, build_date_provenance, decode_oriented
from app6.stage1.provenance_ledger import hamming_distance, load_provenance_sidecar, perceptual_dhash
from app6.stage2.date_provenance import _delta_days, parse_filename_date, resolve_date
from app6.stage2.same_day_gate import _robust_scale, check_same_day_conflict, same_day_summary
from app6.stage2.temporal_axis import temporal_status


OUTPUT_ROOT = Path(os.environ.get(
    "PKG001_OUTPUT_ROOT", "/Volumes/SDCARD/storage/function-verification-runs/PKG-001"
))


def workspace():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="fixture-", dir=OUTPUT_ROOT)


def rec(record_id: str, person: str = "p1", pose: str = "frontal") -> ArchiveRecord:
    return ArchiveRecord(person, record_id, pose, Path("/") / person / record_id)


class ArchiveStrictEvidence(unittest.TestCase):
    def test_group_oracle_boundaries_handoff_and_repeat(self):
        rows = [rec("10"), rec("2"), rec("1", "p2"), rec("1", pose="left_profile")]
        expected = {("p1", "frontal"): ["10", "2"], ("p2", "frontal"): ["1"],
                    ("p1", "left_profile"): ["1"]}
        for _ in range(2):
            got = group_by_person_pose(list(reversed(rows)))
            self.assertEqual({k: [x.record_id for x in v] for k, v in got.items()}, expected)
        self.assertEqual(group_by_person_pose([]), {})
        self.assertEqual(sum(map(len, got.values())), len(rows))

    def test_archive_load_schema_skip_invalid_and_synthetic_handoff(self):
        with workspace() as td:
            root = Path(td)
            entries = [
                ("person_02/frame_000002", {"photo_id": "b", "pose": {"pose_bin": "frontal"}}),
                ("person_01/frame_000001", {"photo_id": "a", "chronology": {"pose_bin": "left_profile"}}),
                ("person_01/frame_badpose", {"photo_id": "x", "pose": {"pose_bin": "unknown"}}),
            ]
            for rel, payload in entries:
                p = root / rel; p.mkdir(parents=True); (p / "info.json").write_text(json.dumps(payload))
            bad = root / "person_03/frame_bad"; bad.mkdir(parents=True); (bad / "info.json").write_text("{")
            (root / "person_04/frame_missing").mkdir(parents=True)
            got = load_archive_records(root)
            self.assertEqual([(x.dataset_id, x.record_id, x.pose_bin) for x in got],
                             [("person_01", "a", "left_profile"), ("person_02", "b", "frontal")])
            self.assertEqual(load_archive_records(None), [])
            self.assertEqual(load_archive_records(root / "missing"), [])
            dated = with_synthetic_dates(got, date(2020, 2, 28))
            self.assertEqual([x.date for x in dated], ["2020-02-28", "2020-02-29"])
            self.assertEqual([x.date for x in with_synthetic_dates(got, date(2020, 2, 28))],
                             [x.date for x in dated])
            self.assertIsNone(got[0].date)
            self.assertEqual(group_by_person_pose(dated)[("person_01", "left_profile")][0].date,
                             "2020-02-28")

    def test_safe_extract_positive_nested_and_traversal_link_fail_closed(self):
        with workspace() as td:
            root = Path(td)
            good = root / "good.tar"
            payload = json.dumps({"photo_id": "a", "pose": {"pose_bin": "frontal"}}).encode()
            with tarfile.open(good, "w") as tf:
                info = tarfile.TarInfo("bundle/person_01/frame_1/info.json"); info.size = len(payload)
                tf.addfile(info, io.BytesIO(payload))
            out = safe_extract_archive(good, root / "out")
            self.assertEqual(out.name, "bundle")
            self.assertEqual(load_archive_records(out)[0].record_id, "a")
            for name, link in (("../escape", None), ("sym", "../escape")):
                evil = root / (name.replace("/", "_") + ".tar")
                with tarfile.open(evil, "w") as tf:
                    info = tarfile.TarInfo(name)
                    if link is not None: info.type = tarfile.SYMTYPE; info.linkname = link
                    else: info.size = 1
                    tf.addfile(info, None if link else io.BytesIO(b"x"))
                with self.assertRaises(ValueError): safe_extract_archive(evil, root / (evil.stem + "-out"))
            self.assertFalse((root / "escape").exists())


class InputProvenanceStrictEvidence(unittest.TestCase):
    def test_exif_parser_leap_boundaries_null_and_repeat(self):
        cases = {"2020:02:29 23:59:59": date(2020, 2, 29), "2019-12-31": date(2019, 12, 31),
                 "2019:02:29": None, "": None, None: None, "garbage": None}
        for value, expected in cases.items():
            self.assertEqual(_parse_exif_date(value), expected)
            self.assertEqual(_parse_exif_date(value), expected)

    def test_build_date_provenance_conflict_null_schema_and_invalid_fail_closed(self):
        meta = {"exif_camera_processing": {"DateTimeOriginal": "2020:01:02 12:00:00"}}
        got = build_date_provenance("2020-01-01", meta, {"claimed_date": "2020-01-03"})
        self.assertEqual(got["authority"], "filename")
        self.assertEqual(got["conflict_sources"], ["exif", "source_claim"])
        self.assertTrue(got["requires_manual_review"])
        self.assertIsInstance(got["delta_days"], int)
        self.assertEqual(got, build_date_provenance("2020-01-01", meta, {"claimed_date": "2020-01-03"}))
        far = build_date_provenance("2020-01-01", {"exif_camera_processing": {"DateTimeOriginal": "2021:01:02"}})
        self.assertIsNone(far["exif_date"])
        with self.assertRaises(ValueError): build_date_provenance("2020-02-30", {})
        with self.assertRaises(ValueError): build_date_provenance("2020-01-01", {}, {"claimed_date": "bad"})

    def test_decode_orientation_modes_corrupt_empty_and_repeat(self):
        with workspace() as td:
            root = Path(td)
            # Asymmetric 3x2 image; EXIF orientation 6 produces 2x3.
            im = Image.new("RGB", (3, 2)); im.putdata([(255,0,0),(0,255,0),(0,0,255),(1,2,3),(4,5,6),(7,8,9)])
            ex = Image.Exif(); ex[274] = 6; ex[36867] = "2020:02:29 12:00:00"
            path = root / "oriented.jpg"; im.save(path, exif=ex, quality=100, subsampling=0)
            a, ma = decode_oriented(path); b, mb = decode_oriented(path)
            oracle = np.asarray(ImageOps.exif_transpose(Image.open(path)).convert("RGB"))[:, :, ::-1]
            np.testing.assert_array_equal(a, oracle)
            np.testing.assert_array_equal(a, b); self.assertEqual(ma, mb)
            self.assertEqual(a.shape, (3, 2, 3)); self.assertEqual(a.dtype, np.uint8)
            self.assertEqual(ma["oriented_size"], [2, 3]); self.assertTrue(ma["orientation_applied"])
            for mode in ("L", "CMYK"):
                p = root / f"{mode}.jpg"; Image.new(mode, (4, 3)).save(p)
                arr, meta = decode_oriented(p); self.assertEqual(arr.shape, (3, 4, 3)); self.assertEqual(meta["encoded_mode"], mode)
            for name, raw in (("empty.jpg", b""), ("truncated.jpg", path.read_bytes()[:30])):
                p = root / name; p.write_bytes(raw)
                with self.assertRaises(Exception): decode_oriented(p)


class DuplicateAndSidecarStrictEvidence(unittest.TestCase):
    def test_dhash_manual_oracle_byte_vs_perceptual_and_repeat(self):
        with workspace() as td:
            root = Path(td); a = root / "a.png"; b = root / "b.jpg"
            im = Image.new("RGB", (64, 64)); im.putdata([(x*4, y*4, (x+y)*2) for y in range(64) for x in range(64)])
            im.save(a); im.save(b, quality=80)
            ha = perceptual_dhash(a); hb = perceptual_dhash(b)
            gray = np.asarray(Image.open(a).convert("L").resize((9,8), Image.Resampling.LANCZOS), dtype=np.int16)
            manual = f"{sum(int(v)<<i for i,v in enumerate((gray[:,1:]>gray[:,:-1]).reshape(-1).tolist())):016x}"
            self.assertEqual(ha, manual); self.assertEqual(ha, perceptual_dhash(a))
            self.assertNotEqual(hashlib.sha256(a.read_bytes()).hexdigest(), hashlib.sha256(b.read_bytes()).hexdigest())
            self.assertLessEqual(hamming_distance(ha, hb), 4)
            self.assertEqual(hamming_distance("0"*16, "f"*16), 64)
            self.assertEqual(hamming_distance(ha, hb), hamming_distance(hb, ha))
            with self.assertRaises((ValueError, TypeError)): hamming_distance("nothex", ha)
            empty = root / "empty"; empty.write_bytes(b"")
            with self.assertRaises(Exception): perceptual_dhash(empty)

    def test_sidecar_candidates_digest_schema_null_symlink_and_repeat(self):
        with workspace() as td:
            root = Path(td); image = root / "x.jpg"; Image.new("RGB", (2,2)).save(image)
            self.assertEqual(load_provenance_sidecar(image), {"status":"not_provided","sidecar_path":None,"sidecar_digest":None})
            side = image.with_suffix(image.suffix + ".provenance.json")
            raw = b'{"source_url":"https://example.test/x","collector":"me","claimed_date":"2020-02-29"}'
            side.write_bytes(raw); got = load_provenance_sidecar(image)
            self.assertEqual(got["sidecar_digest"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(got, load_provenance_sidecar(image))
            self.assertEqual(got["sidecar_path"], side.name)
            for payload in ([], {"unknown":1}, {"source_url":"file:///tmp/x"},
                            {"source_url":"https://x", "claimed_date":"2019-02-29"},
                            {"source_url":"https://x", "collector":""}):
                side.write_text(json.dumps(payload))
                with self.assertRaises(ValueError): load_provenance_sidecar(image)
            target = root / "outside.json"; target.write_text('{"source_url":"https://example.test/out"}')
            side.unlink(); side.symlink_to(target)
            # Symlink provenance is not accepted as an in-tree chain-of-custody artifact.
            with self.assertRaises(ValueError): load_provenance_sidecar(image)


class DateAndTemporalStrictEvidence(unittest.TestCase):
    def test_filename_variants_ambiguity_invalid_and_delta_boundaries(self):
        for name in ("2020_02_29.jpg", "2020-02-29(4).JPG", "IMG_20200229_0001.jpg"):
            self.assertEqual(parse_filename_date(name), ("2020-02-29", "day"))
        self.assertEqual(parse_filename_date("2020_02.jpg"), ("2020-02-01", "month"))
        self.assertEqual(parse_filename_date("x2020y"), ("2020-01-01", "year"))
        self.assertEqual(parse_filename_date("2019_02_29.jpg"), (None, "none"))
        self.assertEqual(parse_filename_date("2020_01_01__2021_01_01.jpg"), (None, "ambiguous"))
        self.assertEqual(_delta_days("2020-02-28", "2020-03-01"), 2)
        self.assertEqual(_delta_days(None, "2020-01-01"), None)
        self.assertEqual(_delta_days("bad", "2020-01-01"), None)

    def test_resolve_date_conflicts_invalid_fail_closed_and_repeat(self):
        got = resolve_date(filename="2020_02_29(2).jpg", exif_date="2020-03-04", claimed_date="2020-02-29")
        self.assertEqual(got["date_source"], "exif")
        self.assertEqual(got["date_provenance_status"], "conflict")
        self.assertEqual(got["date_delta_days"], 4)
        self.assertEqual(got, resolve_date(filename="2020_02_29(2).jpg", exif_date="2020-03-04", claimed_date="2020-02-29"))
        missing = resolve_date(filename="2019_02_29.jpg", exif_date="invalid")
        self.assertIsNone(missing["date"]); self.assertEqual(missing["date_provenance_status"], "missing")
        cal = resolve_date(filename="2020_01_01.jpg", dataset_role="calibration")
        self.assertIsNone(cal["date"]); self.assertEqual(cal["date_provenance_status"], "not_applicable")

    def test_robust_scale_oracle_properties_and_nonfinite_fail_closed(self):
        values = np.array([1., 2., 3., 4., 100.])
        median, sigma = _robust_scale(values)
        self.assertEqual(median, 3.0); self.assertAlmostEqual(sigma, 1.4826)
        m2, s2 = _robust_scale(values + 10); self.assertEqual(m2, 13.0); self.assertAlmostEqual(s2, sigma)
        _, s3 = _robust_scale(values * 2); self.assertAlmostEqual(s3, sigma * 2)
        with self.assertRaises(ValueError): _robust_scale(np.array([]))
        with self.assertRaises(ValueError): _robust_scale(np.array([1., np.nan]))

    def test_same_day_gate_summary_schema_filtering_order_and_repeat(self):
        rows = []
        for i, value in enumerate([1., 1.1, .9, 1.05, .95, 20.]):
            rows.append({"pair_id": str(i), "date_a":"2020-01-01T01:00:00", "date_b":"2020-01-01T23:00:00",
                         "photo_a":f"a{i}", "photo_b":f"b{i}", "pose_bin":"frontal", "ldm134_rmse":value})
        rows += [{"pair_id":"x","date_a":"2020-01-01","date_b":"2020-01-02","ldm134_rmse":999},
                 {"pair_id":"nan","date_a":"2020-01-01","date_b":"2020-01-01","ldm134_rmse":float("nan")},
                 {"pair_id":"null","date_a":None,"date_b":None,"ldm134_rmse":999}]
        hits = check_same_day_conflict(rows)
        self.assertEqual([h["pair_id"] for h in hits], ["5"])
        self.assertEqual(hits, check_same_day_conflict(rows))
        self.assertTrue(np.isfinite(hits[0]["robust_z"])); self.assertTrue(hits[0]["not_a_verdict"])
        summary = same_day_summary(rows, hits)
        self.assertEqual(summary["same_day_pair_count"], 7)
        self.assertEqual(summary["conflict_dates"], ["2020-01-01"])
        self.assertEqual(summary["schema"], hits[0]["schema"])
        with self.assertRaises(ValueError): check_same_day_conflict(rows, 0)
        with self.assertRaises(ValueError): check_same_day_conflict(rows, baseline_quantile=1)

    def test_temporal_status_null_calibration_mixed_and_repeat(self):
        def r(d, role="evidence", precision="day"):
            return SimpleNamespace(date=d, dataset_role=role, date_precision=precision,
                                   has_temporal_axis=lambda: d is not None)
        good = [r("2020-01-01"), r("2020-01-02"), r("2020-01-03", precision="month")]
        got = temporal_status(good)
        self.assertEqual(got, temporal_status(good)); self.assertTrue(got["applicable"])
        self.assertEqual(got["distinct_dates"], 3); self.assertEqual(got["confidence"], "limited_coarse_dates")
        cal = temporal_status([r(None, "calibration") for _ in range(3)])
        self.assertFalse(cal["applicable"]); self.assertEqual(cal["reason"], "calibration_dataset")
        insufficient = temporal_status([r("2020-01-01"), r(None), r("2020-01-01")])
        self.assertFalse(insufficient["applicable"]); self.assertEqual(insufficient["dated_count"], 2)
        self.assertFalse(temporal_status([])["applicable"])


if __name__ == "__main__":
    unittest.main()
