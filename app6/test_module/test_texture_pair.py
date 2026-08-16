"""🎯 GUARD → Текстурные пары: сводка готовности (ER-158 / ER-161).

texture_pair.summarize_texture_pairs строит таблицу парной готовности к
текстурному анализу. Инвариант ER-161 / AGENTS.md: текстура — visualization-only,
policy явно объявляет «readiness only; no texture identity verdict» и никогда не
превращается в evidence-вердикт.
"""
from __future__ import annotations

import unittest

from app6.stage2.texture_pair import summarize_texture_pairs


def _zone(pair_id="p1", usable=True, zone="forehead", score_a=0.9, score_b=0.85, px=1200):
    return {
        "pair_id": pair_id, "usable_both": usable, "zone": zone,
        "texture_score_a": score_a, "texture_score_b": score_b,
        "texture_pixels_a": px, "texture_pixels_b": px,
    }


class SummarizeTexturePairsTests(unittest.TestCase):
    def test_empty_input_empty_output(self):
        self.assertEqual(summarize_texture_pairs([]), [])

    def test_ready_pair_aggregates(self):
        rows = [
            _zone(pair_id="p1", zone="forehead", score_a=0.9, score_b=0.8, px=1200),
            _zone(pair_id="p1", zone="cheek", score_a=0.7, score_b=0.6, px=900),
        ]
        out = summarize_texture_pairs(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["pair_id"], "p1")
        self.assertEqual(out[0]["texture_pair_status"], "texture_ready")
        self.assertEqual(out[0]["usable_texture_zone_count"], 2)
        self.assertEqual(out[0]["min_usable_texture_score"], 0.6)
        self.assertEqual(out[0]["min_usable_texture_pixels"], 900)

    def test_not_ready_when_no_usable_zones(self):
        rows = [_zone(pair_id="p1", usable=False, zone="forehead")]
        out = summarize_texture_pairs(rows)
        self.assertEqual(out[0]["texture_pair_status"], "texture_not_ready")
        self.assertEqual(out[0]["min_usable_texture_score"], 0.0)
        self.assertEqual(out[0]["usable_texture_zone_count"], 0)

    def test_mixed_ready_and_not(self):
        rows = [
            _zone(pair_id="p1", usable=True, zone="forehead"),
            _zone(pair_id="p2", usable=False, zone="cheek"),
        ]
        out = summarize_texture_pairs(rows)
        by_pair = {r["pair_id"]: r["texture_pair_status"] for r in out}
        self.assertEqual(by_pair, {"p1": "texture_ready", "p2": "texture_not_ready"})

    def test_policy_declares_no_verdict(self):
        out = summarize_texture_pairs([_zone(pair_id="p1", usable=True)])
        self.assertIn("readiness only", out[0]["policy"])
        self.assertIn("no texture identity verdict", out[0]["policy"])


if __name__ == "__main__":
    unittest.main()