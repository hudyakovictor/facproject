"""Contract tests for the UI log console ring buffer."""
from __future__ import annotations

import logging
import unittest

from dpo.logging import BufferHandler, LogBuffer


class LogBufferTests(unittest.TestCase):
    def test_seq_is_monotonic_and_since_filters(self) -> None:
        buf = LogBuffer(capacity=10)
        buf.append("info", "a", "first")
        buf.append("warning", "b", "second")
        entries = buf.since(0)
        self.assertEqual([e["seq"] for e in entries], [1, 2])
        self.assertEqual([e["message"] for e in buf.since(1)], ["second"])

    def test_capacity_is_bounded_but_seq_keeps_growing(self) -> None:
        buf = LogBuffer(capacity=3)
        for i in range(10):
            buf.append("info", "loop", f"m{i}")
        entries = buf.since(0)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[-1]["seq"], 10)
        self.assertEqual(buf.last_seq, 10)

    def test_since_respects_limit_and_returns_copies(self) -> None:
        buf = LogBuffer(capacity=10)
        for i in range(5):
            buf.append("info", "x", f"m{i}")
        limited = buf.since(0, limit=2)
        self.assertEqual([e["message"] for e in limited], ["m3", "m4"])
        limited[0]["message"] = "tampered"
        self.assertEqual(buf.since(0, limit=2)[0]["message"], "m3")

    def test_handler_captures_logging_records_with_extra_fields(self) -> None:
        buf = LogBuffer(capacity=10)
        logger = logging.getLogger("dpo.test.console")
        logger.propagate = False
        handler = BufferHandler(buf)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            logger.info("run started", extra={"event": "run_start", "run_id": "r-1"})
        finally:
            logger.removeHandler(handler)
        entry = buf.since(0)[0]
        self.assertEqual(entry["level"], "info")
        self.assertEqual(entry["logger"], "dpo.test.console")
        self.assertEqual(entry["event"], "run_start")
        self.assertEqual(entry["run_id"], "r-1")

    def test_rejects_nonpositive_capacity(self) -> None:
        with self.assertRaises(ValueError):
            LogBuffer(capacity=0)
