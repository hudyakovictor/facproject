from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from morphing.backend.regions import (
    bounds_for,
    normalize_weights,
    region_registry,
    region_statistics,
    split_indices,
    weighted_score,
)
from morphing.backend.reporting import (
    build_pair_report,
    build_timeline_report,
    digest_payload,
    render_report_html,
    report_summary,
    write_report,
)


def sample_mesh(shift: float = 0.0, n: int = 35) -> np.ndarray:
    t = np.linspace(-1, 1, n * 3, dtype=np.float32).reshape(n, 3)
    t[:, 2] += shift
    return t


class RegionRegistryTests(unittest.TestCase):
    def test_regions_partition_the_mesh(self) -> None:
        ranges = bounds_for(100)
        flattened = [index for start, end in ranges.values() for index in range(start, end)]
        self.assertEqual(flattened, list(range(100)))

    def test_registry_carries_vertex_bounds(self) -> None:
        registry = region_registry(35709)
        self.assertEqual(registry["schema"], "facproject-morphing-regions-v1")
        self.assertEqual(len(registry["regions"]), 7)
        self.assertIn("bounds", registry["regions"][0])

    def test_weights_are_normalized(self) -> None:
        weights = normalize_weights({"nose": 3, "mouth_chin": 1})
        self.assertAlmostEqual(sum(weights.values()), 1)
        self.assertGreater(weights["nose"], 0.5)
        defaults = normalize_weights()
        expected = 3.0 / (3.0 + 1.0 + 1.0 - defaults["nose"] - defaults["mouth_chin"] )
        self.assertAlmostEqual(weights["nose"], expected)

    def test_invalid_weights_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite and non-negative"):
            normalize_weights({"nose": -1})
        with self.assertRaisesRegex(ValueError, "positive"):
            normalize_weights({key: 0 for key in normalize_weights()})

    def test_split_indices_reject_unknown_region(self) -> None:
        with self.assertRaisesRegex(KeyError, "unknown"):
            split_indices(100, ["made_up_zone"])

    def test_region_statistics_accept_vectors(self) -> None:
        values = np.ones((70, 3), dtype=np.float32)
        stats = region_statistics(values)
        self.assertEqual(len(stats), 7)
        self.assertAlmostEqual(stats["nose"]["mean"], np.sqrt(3), places=6)

    def test_region_statistics_validate_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "match"):
            region_statistics(np.ones(70), vertex_count=72)

    def test_weighted_score_only_uses_available_regions(self) -> None:
        result = weighted_score({"nose": {"similarity": 80}, "mouth_chin": {"similarity": 20}})
        expected = 80 * (0.22 / 0.52) + 20 * (0.30 / 0.52)
        self.assertAlmostEqual(result, expected)


class ReportTests(unittest.TestCase):
    def test_pair_report_contains_limitations_and_stable_id(self) -> None:
        a, b = sample_mesh(), sample_mesh(0.1)
        first = build_pair_report(a, b, labels=("A", "B"))
        second = build_pair_report(a, b, labels=("A", "B"))
        self.assertEqual(first["report_id"], second["report_id"])
        self.assertEqual(first["schema"], "facproject-morphing-report-v1")
        self.assertEqual(len(first["limitations"]), 3)
        self.assertIn("mesh_a", first["quality"])

    def test_timeline_report_has_age_aware_drift(self) -> None:
        meshes = [sample_mesh(), sample_mesh(0.02), sample_mesh(0.05)]
        result = build_timeline_report(meshes, [2000, 2008, 2025])
        self.assertIn("temporal_drift", result)
        self.assertEqual(result["years"], [2000, 2008, 2025])
        self.assertEqual(len(result["adjacent_similarity"]), 2)

    def test_timeline_report_requires_matching_year_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "match"):
            build_timeline_report([sample_mesh(), sample_mesh(1)], [2000])

    def test_timeline_quality_rows_are_included_and_validated(self) -> None:
        meshes = [sample_mesh(), sample_mesh(0.1)]
        rows = [{"index": 0, "status": "pass"}, {"index": 1, "status": "warn"}]
        report = build_timeline_report(meshes, quality_keyframes=rows)
        self.assertEqual(report["quality_keyframes"], rows)
        with self.assertRaisesRegex(ValueError, "quality_keyframes"):
            build_timeline_report(meshes, quality_keyframes=rows[:1])

    def test_html_escapes_untrusted_title_and_payload(self) -> None:
        report = {"report_id": "test", "kind": "pair", "user_label": "</script><img src=x onerror=alert(1)>"}
        output = render_report_html(report, "<img src=x>")
        self.assertNotIn("<img src=x>", output)
        self.assertNotIn("</script><img", output)
        self.assertIn("&lt;img", output)

    def test_write_json_and_html_atomically(self) -> None:
        report = {"kind": "pair", "report_id": "test", "value": 0.5}
        with tempfile.TemporaryDirectory() as folder:
            json_path = write_report(report, Path(folder) / "report.json")
            html_path = write_report(report, Path(folder) / "report.html", format="html")
            self.assertIn('"value": 0.5', json_path.read_text())
            self.assertIn("Machine-readable payload", html_path.read_text())
            self.assertFalse((Path(folder) / "report.json.tmp").exists())

    def test_write_rejects_unknown_format(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "format"):
                write_report({}, Path(folder) / "report.txt", format="csv")

    def test_summary_does_not_invent_missing_scores(self) -> None:
        summary = report_summary({"report_id": "x", "kind": "pair", "limitations": []})
        self.assertIsNone(summary["morphability_score"])
        self.assertEqual(summary["top_zones"], [])

    def test_canonical_digest_ignores_mapping_order(self) -> None:
        self.assertEqual(digest_payload({"a": 1, "b": 2}), digest_payload({"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
