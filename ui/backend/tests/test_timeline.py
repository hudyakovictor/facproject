from __future__ import annotations

import unittest

from dpo.timeline import build_timeline, timeline_state_at


def _ev(seq: int, ts: str, type: str, **payload) -> dict:
    return {"schema": "dpo-run-event-v1", "seq": seq, "ts": ts, "type": type, "payload": payload}


class TimelineFromUnittestOutputTests(unittest.TestCase):
    def test_matched_unittest_lines_become_sequential_test_spans(self) -> None:
        events = [
            _ev(1, "2026-01-01T00:00:00Z", "started", runner_id="app6-regression"),
            _ev(2, "2026-01-01T00:00:01Z", "log", text="test_a (test_stage1_geometry_contracts.T.test_a) ... ok"),
            _ev(3, "2026-01-01T00:00:03Z", "log", text="test_b (test_stage1_geometry_contracts.T.test_b) ... FAIL"),
            _ev(4, "2026-01-01T00:00:04Z", "finished", status="failed", exit_code=1),
        ]
        timeline = build_timeline(events, run_created_at="2026-01-01T00:00:00Z")
        track_ids = {t["id"] for t in timeline["tracks"]}
        self.assertEqual(track_ids, {"run", "tests"})

        test_spans = [s for s in timeline["spans"] if s["track_id"] == "tests"]
        self.assertEqual([s["label"] for s in test_spans], ["test_a", "test_b"])
        self.assertEqual([s["status"] for s in test_spans], ["succeeded", "failed"])
        self.assertEqual(test_spans[0]["stage_guess"], "stage1")

        # Start of span N is estimated as the end of span N-1 (sequential
        # execution assumption), never a fabricated measured duration.
        self.assertTrue(test_spans[0]["start_is_estimated"])
        self.assertEqual(test_spans[0]["start_ts"], "2026-01-01T00:00:00Z")
        self.assertEqual(test_spans[0]["end_ts"], "2026-01-01T00:00:01Z")
        self.assertEqual(test_spans[1]["start_ts"], "2026-01-01T00:00:01Z")
        self.assertEqual(test_spans[1]["end_ts"], "2026-01-01T00:00:03Z")

    def test_stage1_photo_progress_lines_become_photo_spans(self) -> None:
        events = [
            _ev(1, "2026-01-01T00:00:00Z", "started", runner_id="fresh-5"),
            _ev(2, "2026-01-01T00:00:02Z", "log", text="[1/3] IMG_0001.jpg"),
            _ev(3, "2026-01-01T00:00:05Z", "log", text="[2/3] IMG_0002.jpg"),
            _ev(4, "2026-01-01T00:00:07Z", "log", text="[3/3] IMG_0003.jpg"),
            _ev(5, "2026-01-01T00:00:08Z", "finished", status="succeeded", exit_code=0),
        ]
        timeline = build_timeline(events, run_created_at="2026-01-01T00:00:00Z")
        photo_spans = [s for s in timeline["spans"] if s["track_id"] == "photos"]
        self.assertEqual([s["label"] for s in photo_spans], ["IMG_0001.jpg", "IMG_0002.jpg", "IMG_0003.jpg"])
        self.assertEqual(photo_spans[0]["stage_guess"], "stage1")

    def test_unrecognized_lines_are_kept_not_dropped(self) -> None:
        events = [
            _ev(1, "2026-01-01T00:00:00Z", "started", runner_id="x"),
            _ev(2, "2026-01-01T00:00:01Z", "log", text="some totally unstructured line"),
        ]
        timeline = build_timeline(events, run_created_at="2026-01-01T00:00:00Z")
        log_spans = [s for s in timeline["spans"] if s["track_id"] == "log"]
        self.assertEqual(len(log_spans), 1)
        self.assertEqual(log_spans[0]["raw_line"], "some totally unstructured line")
        self.assertEqual(log_spans[0]["status"], "unknown")

    def test_timeline_state_at_splits_completed_and_pending_by_seq(self) -> None:
        events = [
            _ev(1, "2026-01-01T00:00:00Z", "started", runner_id="x"),
            _ev(2, "2026-01-01T00:00:01Z", "log", text="test_a (m.T.test_a) ... ok"),
            _ev(3, "2026-01-01T00:00:02Z", "log", text="test_b (m.T.test_b) ... ok"),
            _ev(4, "2026-01-01T00:00:03Z", "log", text="test_c (m.T.test_c) ... ok"),
        ]
        timeline = build_timeline(events, run_created_at="2026-01-01T00:00:00Z")
        state = timeline_state_at(timeline, at_seq=3)
        self.assertEqual(state["active"], [])
        self.assertEqual({s["seq"] for s in state["completed"]}, {1, 2, 3})
        self.assertEqual({s["seq"] for s in state["pending"]}, {4})

    def test_skipped_and_error_statuses_are_mapped_honestly(self) -> None:
        events = [
            _ev(1, "2026-01-01T00:00:00Z", "started", runner_id="x"),
            _ev(2, "2026-01-01T00:00:01Z", "log", text="test_a (m.T.test_a) ... skipped 'reason'"),
            _ev(3, "2026-01-01T00:00:02Z", "log", text="test_b (m.T.test_b) ... ERROR"),
        ]
        timeline = build_timeline(events, run_created_at="2026-01-01T00:00:00Z")
        test_spans = [s for s in timeline["spans"] if s["track_id"] == "tests"]
        self.assertEqual(test_spans[0]["status"], "skipped")
        self.assertEqual(test_spans[1]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
