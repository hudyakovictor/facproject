from __future__ import annotations

import unittest

from dpo.guide import build_guide_status


def health(*, app6=True, storage=True, main=True, calibration=True):
    return {
        "app6": {"available": app6},
        "storage": {"ready": storage, "heavy_root": "/Volumes/SDCARD/uidata", "reasons": [] if storage else ["disk missing"]},
        "datasets": {
            "main": {"available": main, "file_count": 10, "reasons": [] if main else ["main missing"]},
            "calibration": {"available": calibration, "file_count": 7, "reasons": [] if calibration else ["calibration missing"]},
        },
    }


class GuidedWorkflowTests(unittest.TestCase):
    def test_first_failed_gate_is_current_and_later_steps_are_locked(self):
        result = build_guide_status(health(storage=False), [])
        self.assertEqual(result["current_step_id"], "storage")
        states = {x["id"]: x["status"] for x in result["steps"]}
        self.assertEqual(states["system"], "complete")
        self.assertEqual(states["storage"], "current")
        self.assertEqual(states["main-dataset"], "locked")

    def test_successful_runs_unlock_foundation_in_order(self):
        runs = [
            {"id": "ui-1", "runner_id": "ui-backend-regression", "status": "succeeded", "finished_at": "2026-01-01"},
            {"id": "app6-1", "runner_id": "app6-regression", "status": "succeeded", "finished_at": "2026-01-02"},
        ]
        result = build_guide_status(health(), runs)
        self.assertTrue(result["foundation_complete"])
        self.assertEqual(result["current_step_id"], "photo-index")
        self.assertEqual(result["steps"][6]["action"], "development")

    def test_latest_failed_run_does_not_reuse_old_success(self):
        runs = [
            {"id": "old", "runner_id": "ui-backend-regression", "status": "succeeded", "finished_at": "2026-01-01"},
            {"id": "new", "runner_id": "ui-backend-regression", "status": "failed", "finished_at": "2026-01-02"},
        ]
        result = build_guide_status(health(), runs)
        self.assertEqual(result["current_step_id"], "backend-tests")

    def test_photo_index_capability_advances_to_timeline_gate(self):
        runs = [
            {"id": "ui", "runner_id": "ui-backend-regression", "status": "succeeded", "finished_at": "2026-01-01"},
            {"id": "app", "runner_id": "app6-regression", "status": "succeeded", "finished_at": "2026-01-02"},
        ]
        result = build_guide_status(health(), runs, {"photo_index_count": 1700})
        self.assertEqual(result["current_step_id"], "timeline")
        self.assertEqual(result["steps"][6]["status"], "complete")
        self.assertIn("1700", result["steps"][6]["evidence"])

    def test_analysis_stays_locked_until_real_product_gates_exist(self):
        result = build_guide_status(health(), [])
        self.assertFalse(result["analysis_unlocked"])
        self.assertEqual(result["steps"][-1]["status"], "locked")

    def test_empty_health_fails_closed(self):
        result = build_guide_status({}, [])
        self.assertEqual(result["current_step_id"], "system")
        self.assertEqual(result["completed"], 0)
