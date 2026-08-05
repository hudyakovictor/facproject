from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app6.api.analysis_profiles import (
    apply_curation,
    build_profile_photo_statuses,
    clone_profile,
    create_profile,
    diff_profiles,
    export_profile,
    freeze_selection_manifest,
    get_profile,
    import_profile,
    list_profiles,
    rename_profile,
    restore_automatic,
    set_profile_lock,
)
from app6.api.selection_filters import DEFAULT_FILTER_STATE


def _env(tmp: str) -> dict[str, str]:
    storage = str(Path(tmp) / "storage")
    return {
        "DEEPUTIN_STORAGE_ROOT": storage,
        "DEEPUTIN_STAGE1_ROOT": str(Path(storage) / "stage1"),
        "DEEPUTIN_CALIBRATION_ROOT": str(Path(tmp) / "cal"),
    }


def _photos():
    return [
        {"id": "a", "bucket": "frontal", "yaw": 0, "pitch": 0, "roll": 0, "visibility": 0.9, "quality": 0.9},
        {"id": "b", "bucket": "frontal", "yaw": 0, "pitch": 0, "roll": 0, "visibility": 0.2, "quality": 0.2},
        {"id": "c", "bucket": "frontal", "yaw": 0, "pitch": 0, "roll": 0, "visibility": 0.8, "quality": 0.8},
    ]


class IterationFourProfilesTests(unittest.TestCase):
    def test_create_list_rename_clone_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, _env(tmp), clear=False):
                created = create_profile(name="Main", description="d1")
                self.assertTrue(created["id"].startswith("profile_"))
                listed = list_profiles()
                self.assertEqual(listed["count"], 1)
                renamed = rename_profile(created["id"], name="Main v2")
                self.assertEqual(renamed["config"]["name"], "Main v2")
                cloned = clone_profile(created["id"], new_name="Copy")
                self.assertNotEqual(cloned["id"], created["id"])
                locked = set_profile_lock(created["id"], True)
                self.assertTrue(locked["locked"])
                with self.assertRaises(PermissionError):
                    rename_profile(created["id"], name="Nope")

    def test_curation_journal_and_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, _env(tmp), clear=False):
                profile = create_profile(name="Cur")
                pid = profile["id"]
                result = apply_curation(pid, photo_ids=["a", "b"], status="manual_exclusion", reason_code="manual_reviewer", comment="bad")
                self.assertEqual(result["changed_count"], 2)
                loaded = get_profile(pid)
                self.assertEqual(loaded["curation"]["photos"]["a"]["status"], "manual_exclusion")
                self.assertGreaterEqual(len(loaded["journal_tail"]), 2)
                restored = restore_automatic(pid, photo_ids=["a"])
                self.assertEqual(restored["restored_count"], 1)
                loaded2 = get_profile(pid)
                self.assertNotIn("a", loaded2["curation"]["photos"])

    def test_status_resolution_and_freeze_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, _env(tmp), clear=False):
                state = json.loads(json.dumps(DEFAULT_FILTER_STATE))
                state["enabled"]["visibility"] = True
                state["ranges"]["visibility"] = {"min": 0.5, "max": 1.0}
                profile = create_profile(name="Freeze", filter_state=state)
                pid = profile["id"]
                apply_curation(pid, photo_ids=["b"], status="manual_include", reason_code="manual_reviewer")
                apply_curation(pid, photo_ids=["c"], status="diagnostic_only", reason_code="bulk_action")
                resolved = build_profile_photo_statuses(
                    _photos(),
                    filter_state=state,
                    curation=get_profile(pid)["curation"],
                )
                self.assertEqual(resolved["photos"]["b"]["status"], "manual_include")
                self.assertTrue(resolved["photos"]["b"]["included"])
                self.assertEqual(resolved["photos"]["c"]["status"], "diagnostic_only")
                # a is primary (passes filter), no manual
                self.assertEqual(resolved["photos"]["a"]["status"], "primary")
                frozen = freeze_selection_manifest(pid, _photos(), stage1_root="/tmp/stage1")
                manifest = frozen["manifest"]
                self.assertTrue(Path(frozen["path"]).is_file())
                self.assertIn("b", manifest["included_ids"])
                self.assertTrue(manifest["immutable_stage1"])
                # every photo has unambiguous status
                for photo_id in ["a", "b", "c"]:
                    self.assertIn(photo_id, manifest["photo_statuses"])
                    self.assertIn(manifest["photo_statuses"][photo_id]["status"], {
                        "primary", "diagnostic_only", "automatic_exclusion", "manual_exclusion",
                        "manual_include", "manual_review", "invalid",
                    })

    def test_diff_export_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, _env(tmp), clear=False):
                a = create_profile(name="A")
                b = create_profile(name="B")
                apply_curation(a["id"], photo_ids=["x"], status="manual_review")
                apply_curation(b["id"], photo_ids=["x"], status="manual_exclusion")
                diff = diff_profiles(a["id"], b["id"])
                self.assertEqual(diff["status_change_count"], 1)
                exported = export_profile(a["id"])
                imported = import_profile(exported)
                self.assertNotEqual(imported["id"], a["id"])
                self.assertEqual(imported["curation"]["photos"]["x"]["status"], "manual_review")
                listed = list_profiles()
                self.assertEqual(listed["count"], 3)


if __name__ == "__main__":
    unittest.main()
