"""🚪 CONTRACT → Ручные QA-решения (append-only журнал).

append_review: обязательные поля и допустимые decision валидируются (fail-closed);
валидное решение append-only пишется в JSONL журнал с версионированной схемой.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from app6.api.review import append_review


class AppendReviewTests(unittest.TestCase):
    def test_missing_required_field_raises(self):
        with self.assertRaises(ValueError):
            append_review(Path("."), {"photo_id": "x", "reviewer": "me"})  # нет decision

    def test_invalid_decision_raises(self):
        with self.assertRaises(ValueError):
            append_review(Path("."), {"photo_id": "x", "decision": "maybe", "reviewer": "me"})

    def test_valid_review_appended_to_jsonl(self):
        with TemporaryDirectory() as td, mock.patch.dict(
            "os.environ", {"DEEPUTIN_STATE_ROOT": td}, clear=False
        ):
            row = append_review(Path("."), {"photo_id": "p1", "decision": "approve", "reviewer": "alpha"})
            self.assertEqual(row["schema"], "deeputin-manual-qa-v1")
            self.assertIn("created_at", row)
            journal = (Path(td) / "manual_qa.jsonl").read_text(encoding="utf-8")
            records = [json.loads(line) for line in journal.strip().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["decision"], "approve")
            self.assertEqual(records[0]["photo_id"], "p1")

    def test_append_only_preserves_prior_entries(self):
        with TemporaryDirectory() as td, mock.patch.dict(
            "os.environ", {"DEEPUTIN_STATE_ROOT": td}, clear=False
        ):
            append_review(Path("."), {"photo_id": "a", "decision": "approve", "reviewer": "r"})
            append_review(Path("."), {"photo_id": "b", "decision": "reject", "reviewer": "r"})
            lines = (Path(td) / "manual_qa.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()