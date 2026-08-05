from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tools.rebuild_landmark_utility import (
    BINS,
    build,
    build_visibility_prior,
    load_nested_calibration,
)


class A11ArtifactTests(unittest.TestCase):
    @staticmethod
    def _rows():
        rng = np.random.default_rng(20260803)
        rows = []
        for bi, bin_name in enumerate(BINS):
            for frame in range(6):
                points = rng.normal(
                    loc=float(bi) * 0.01,
                    scale=0.001,
                    size=(134, 3),
                ).astype(np.float64)
                visible = np.ones(134, dtype=bool)
                # Детерминированное частичное закрытие нескольких точек.
                visible[(frame + bi) % 17::37] = False
                rows.append({
                    "bin": bin_name,
                    "points": points,
                    "visible": visible,
                    "subject": f"person_{frame % 3}",
                    "directory": f"{bin_name}/frame_{frame:03d}",
                })
        return rows

    @staticmethod
    def _loader(row):
        return row["points"], row["visible"]

    def test_build_is_deterministic(self):
        rows = self._rows()
        first, report_first = build(rows, self._loader)
        second, report_second = build(rows, self._loader)

        np.testing.assert_array_equal(
            np.nan_to_num(first, nan=-1.0),
            np.nan_to_num(second, nan=-1.0),
        )
        self.assertEqual(report_first["sha256"], report_second["sha256"])

    def test_prior_is_deterministic(self):
        rows = self._rows()
        first = build_visibility_prior(rows, self._loader)
        second = build_visibility_prior(rows, self._loader)
        np.testing.assert_array_equal(first, second)

    def test_shapes_and_bin_coverage(self):
        rows = self._rows()
        utility, report = build(rows, self._loader)
        prior = build_visibility_prior(rows, self._loader)

        self.assertEqual(utility.shape, (9, 134))
        self.assertEqual(prior.shape, (9, 134))
        self.assertTrue(np.isfinite(utility).any(axis=1).all())
        self.assertTrue(np.isfinite(prior).all())
        self.assertEqual(
            report["bin_counts"],
            {bin_name: 6 for bin_name in BINS},
        )

    def test_order_does_not_change_result(self):
        rows = self._rows()
        direct, _ = build(rows, self._loader)
        reversed_result, _ = build(list(reversed(rows)), self._loader)

        # np.var не должна зависеть от порядка кадров за пределами машинного
        # epsilon; сравниваем с жёстким численным допуском.
        np.testing.assert_allclose(
            direct,
            reversed_result,
            rtol=1e-12,
            atol=1e-14,
            equal_nan=True,
        )

    def test_nested_loader_does_not_require_temporal_axis(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = (
                Path(tmp)
                / "person_01"
                / "frame_000001"
            )
            directory.mkdir(parents=True)
            (directory / "info.json").write_text(
                json.dumps({
                    "date": "2001-01-01",
                    "pose": {"pose_bin": "frontal"},
                }),
                encoding="utf-8",
            )
            with (directory / "ldm134_raw.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                handle.write(
                    "landmark_id,x,y,z,visible,vertex_index\n"
                )
                for landmark_id in range(134):
                    handle.write(
                        f"{landmark_id},"
                        f"{landmark_id * 0.001},0,0,1,{landmark_id}\n"
                    )

            rows = load_nested_calibration(Path(tmp))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["bin"], "frontal")
            self.assertEqual(rows[0]["subject"], "person_01")
            self.assertNotIn("date", rows[0])
            self.assertNotIn("era", rows[0])
            self.assertNotIn("temporal_axis", rows[0])


if __name__ == "__main__":
    unittest.main()
