"""Тесты боевого набора метрик формы: 30 утверждённых, 9 устойчивых, цвет по личностям.

Здесь нет ни torch, ни MediaPipe, ни фото: проверяются те же данные, что читает прод
(`metric_bands.json`, `approved_metrics`), и чистая арифметика verdict. Реконструкцию и
MP-воркер покрывают прогоны валидации (`app9/validation`), потому что MediaPipe и torch
в одном процессе падают по SIGSEGV — см. docstring `morphing.backend.mp_worker`.
"""
from __future__ import annotations

import itertools
import json
import unittest

import numpy as np

from morphing.backend import approved_metrics as A
from morphing.backend import form_metrics as F
from morphing.backend import metric_registry as R
from morphing.backend.mp_worker import FaceNotFound, MediaPipeUnavailable, roll_corrected, resolve_asset


def bundle(metrics: dict[str, float], yaw: float = 5.0, absent: dict[str, str] | None = None) -> dict:
    """Минимальный «фотобандл» формы, какой возвращает `photo_bundle`."""
    return {"label": "X", "yaw": yaw, "pose_bin": "frontal",
            "mediapipe": {"available": True, "reason": None},
            "expression": {"neutral": True, "flags": []},
            "metrics": dict(metrics), "absent": dict(absent or {})}


def row_of(name: str, a: dict, b: dict) -> dict:
    return next(r for r in F.pair_rows(a, b) if r["name"] == name)


class ApprovedSetTest(unittest.TestCase):
    def test_thirty_approved_and_all_have_definitions(self) -> None:
        self.assertEqual(len(A.APPROVED_NAMES), 30)
        self.assertEqual(len(set(A.APPROVED_NAMES)), 30)
        for name in A.APPROVED_NAMES:
            self.assertTrue(R.describe(name), f"{name} без описания")
            self.assertTrue(R.meta(name)["kind"], f"{name} нет в реестре определений")

    def test_nine_trusted_are_subset_and_all_3ddfa(self) -> None:
        self.assertEqual(len(A.POSE_STABLE), 9)
        self.assertTrue(A.POSE_STABLE <= set(A.APPROVED_NAMES))
        # Устойчивые держатся именно на 3D-сетке: MediaPipe-каркас на угле сыпется.
        self.assertTrue(all(A.framework(n) == "3ddfa" for n in A.POSE_STABLE))

    def test_framework_split_matches_documented_counts(self) -> None:
        self.assertEqual(sum(1 for n in A.APPROVED_NAMES if A.requires_mediapipe(n)), 14)
        self.assertEqual(sum(1 for n in A.APPROVED_NAMES if A.requires_ldm134(n)), 14)


class BandsFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = F.bands()
        self.per_metric = self.payload["metrics"]

    def test_covers_all_approved_with_matching_flags(self) -> None:
        self.assertEqual(set(self.per_metric), set(A.APPROVED_NAMES))
        for name, meta in self.per_metric.items():
            self.assertEqual(meta["trusted"], A.pose_stable(name), name)

    def test_identity_reference_exists_for_every_metric(self) -> None:
        """Цвет ячейки берётся из трёх эталонных медиан: без них красить нечем."""
        idents = self.payload["identities"]
        self.assertEqual(idents, ["put", "vas", "udmurt"])
        for name, meta in self.per_metric.items():
            for regime in ("frontal", "subfrontal"):
                ref = meta[regime]["ref"]
                self.assertEqual(set(ref), set(idents), f"{name}/{regime}")
                for ident, cell in ref.items():
                    self.assertIsNotNone(cell["median"], f"{name}/{regime}/{ident}")
                    self.assertGreaterEqual(cell["n"], 5, f"{name}/{regime}/{ident} мало кадров")
                    self.assertEqual(cell["basis"], "neutral", f"{name}/{regime}/{ident} эталон по мимике")

    def test_every_metric_has_ordered_cuts_in_both_regimes(self) -> None:
        for name, meta in self.per_metric.items():
            self.assertTrue(meta["max_band"], f"{name} без полосы")
            for regime in ("frontal", "subfrontal"):
                reg = meta[regime]
                self.assertGreater(reg["mad_pooled"], 0, f"{name}/{regime} нулевая полоса")
                self.assertGreater(reg["k_same"], 0, f"{name}/{regime} k_same")
                self.assertLess(reg["k_same"], reg["k_differ"], f"{name}/{regime} границы разъехались")
                self.assertGreaterEqual(reg["k_differ"], 2.0, f"{name}/{regime} красный слишком близко")
                self.assertGreaterEqual(reg["n_same_pairs"], 200, f"{name}/{regime} мало пар для перцентиля")
                self.assertLess(reg["signal_cross"], 1.0, f"{name}/{regime} signal_cross вне диапазона")

    def test_trusted_red_is_the_more_informative_one(self) -> None:
        """Выделять 9 рамкой — не украшение: их «расходится» чаще случается у разных лиц."""
        def median(regime: str, trusted: bool) -> float:
            vals = [m[regime]["signal_cross"] for m in self.per_metric.values()
                    if m["trusted"] is trusted and m[regime]["signal_cross"]]
            return float(np.median(vals))

        for regime in ("frontal", "subfrontal"):
            self.assertGreater(median(regime, True), median(regime, False), regime)


class VerdictTest(unittest.TestCase):
    """Согласие двух снимков на реальной калибровке: порог = полоса × перцентиль разностей."""

    def setUp(self) -> None:
        self.name = "midface_profile_convexity_3ddfa"
        reg = F.bands()["metrics"][self.name]["frontal"]
        self.band, self.k_same, self.k_differ = reg["mad_pooled"], reg["k_same"], reg["k_differ"]

    def gap_row(self, gap: float, yaw_b: float = 5.0) -> dict:
        return row_of(self.name, bundle({self.name: 1.0}), bundle({self.name: 1.0 - gap}, yaw=yaw_b))

    def test_three_colors_and_their_boundaries(self) -> None:
        self.assertEqual(self.gap_row(self.band * self.k_same * 0.5)["verdict"], "same")
        self.assertEqual(self.gap_row(self.band * self.k_same)["verdict"], "same")     # ровно на границе
        self.assertEqual(self.gap_row(self.band * (self.k_same + self.k_differ) / 2)["verdict"], "border")
        self.assertEqual(self.gap_row(self.band * self.k_differ * 0.99)["verdict"], "border")
        self.assertEqual(self.gap_row(self.band * self.k_differ * 1.5)["verdict"], "differ")

    def test_diff_signed_diff_and_ratio_in_band_units(self) -> None:
        row = self.gap_row(self.band * 3.0)
        self.assertAlmostEqual(row["diff"], round(self.band * 3.0, 6), places=6)
        self.assertAlmostEqual(row["signed_diff"], round(self.band * 3.0, 6), places=6)
        self.assertAlmostEqual(row["ratio"], 3.0, places=1)
        self.assertEqual(row["verdict_ru"], F.VERDICT_RU[row["verdict"]])

    def test_missing_value_is_unknown_with_reason(self) -> None:
        a = bundle({}, absent={self.name: "нужен MediaPipe, он недоступен: модель не найдена"})
        row = row_of(self.name, a, bundle({self.name: 1.0}))
        self.assertEqual(row["verdict"], "unknown")
        self.assertIn("MediaPipe", row["reason"])

    def test_regime_follows_most_turned_photo(self) -> None:
        self.assertEqual(F._regime(5.0, 12.0), ("frontal", False))
        self.assertEqual(F._regime(-15.0, 3.0), ("frontal", False))
        self.assertEqual(F._regime(18.0, 3.0), ("subfrontal", False))
        self.assertEqual(F._regime(31.0, 3.0), ("subfrontal", True))
        self.assertEqual(F._regime(None, None), ("frontal", False))

    def test_extrapolated_pair_gets_the_softer_cuts(self) -> None:
        meta = F.bands()["metrics"][self.name]
        soft_same = min(meta["frontal"]["k_same"], meta["subfrontal"]["k_same"])
        soft_differ = max(meta["frontal"]["k_differ"], meta["subfrontal"]["k_differ"])
        row = self.gap_row(self.band * 0.5, yaw_b=40.0)
        self.assertTrue(row["extrapolated"])
        self.assertEqual(row["regime"], "subfrontal")
        self.assertEqual(row["k_same"], soft_same)
        self.assertEqual(row["k_differ"], soft_differ)


class AttributionTest(unittest.TestCase):
    """Цвет ячейки = доля близости к двум ближайшим эталонам личности. Чистая геометрия."""

    def setUp(self) -> None:
        per_metric = F.bands()["metrics"]
        # Берём метрику с максимально разнесёнными медианами: делить цвет там есть между кем.
        self.name = max(per_metric, key=lambda n: per_metric[n]["frontal"]["min_gap"] or 0)
        ref = per_metric[self.name]["frontal"]["ref"]
        self.med = {i: float(c["median"]) for i, c in ref.items()}
        self.band = per_metric[self.name]["frontal"]["mad_pooled"]
        ordered = sorted(self.med, key=lambda i: self.med[i])
        # Соседи с наибольшим зазором: в их середине третья медиана гарантированно дальше.
        gaps = [(abs(self.med[b] - self.med[a]), a, b) for a, b in itertools.pairwise(ordered)]
        self.gap, self.left, self.right = max(gaps)
        self.reg = per_metric[self.name]["frontal"]

    def att(self, value: float) -> dict:
        return F._attribution(value, self.reg, self.band, self.reg["k_differ"])

    def test_value_on_median_is_that_person(self) -> None:
        for ident in (self.left, self.right):
            out = self.att(self.med[ident])
            self.assertEqual(out["who"], ident)
            self.assertEqual(out["split"][0], {"ident": ident, "w": 1.0})
            self.assertEqual(out["split"][1]["w"], 0.0)
            self.assertFalse(out["stray"])

    def test_midpoint_between_two_people_is_exactly_half_and_half(self) -> None:
        out = self.att((self.med[self.left] + self.med[self.right]) / 2)
        self.assertEqual({p["ident"] for p in out["split"]}, {self.left, self.right})
        self.assertTrue(all(p["w"] == 0.5 for p in out["split"]), out["split"])

    def test_share_is_distance_ratio_and_weights_sum_to_one(self) -> None:
        # 25% пути от левой медианы: дальняя забирает 0.25, сумма долей всегда 1
        out = self.att(self.med[self.left] + 0.25 * (self.med[self.right] - self.med[self.left]))
        self.assertEqual(out["who"], self.left)
        self.assertAlmostEqual(out["split"][1]["w"], 0.25, places=4)
        self.assertAlmostEqual(sum(p["w"] for p in out["split"]), 1.0, places=4)
        for value in (self.med[self.left], (self.med[self.left] + self.med[self.right]) / 2):
            self.assertAlmostEqual(sum(p["w"] for p in self.att(value)["split"]), 1.0, places=4)

    def test_stray_marks_value_like_none_of_the_three(self) -> None:
        far = max(self.med.values()) + self.band * (self.reg["k_differ"] + 2.0)
        self.assertTrue(self.att(far)["stray"])
        self.assertGreater(self.att(far)["distance"], self.reg["k_differ"])
        self.assertFalse(self.att(self.med[self.left])["stray"])

    def test_no_value_grey_with_reason(self) -> None:
        out = F._attribution(None, self.reg, self.band, self.reg["k_differ"])
        self.assertIsNone(out["who"])
        self.assertEqual(out["split"], [])

    def test_row_marks_when_photos_point_to_different_people(self) -> None:
        a = bundle({self.name: self.med[self.left]})
        b = bundle({self.name: self.med[self.right]})
        row = row_of(self.name, a, b)
        self.assertEqual(row["a"]["who"], self.left)
        self.assertEqual(row["b"]["who"], self.right)
        self.assertTrue(row["other_people"])
        self.assertEqual(row["a"]["regime"], "frontal")

    def test_row_uses_the_photos_own_regime(self) -> None:
        # B повёрнут на 20°: его ячейка судится по подфронтовым медианам, а пара — по нему
        b = bundle({self.name: self.med[self.left]}, yaw=20.0)
        row = row_of(self.name, bundle({self.name: self.med[self.left]}), b)
        self.assertEqual(row["b"]["regime"], "subfrontal")
        self.assertEqual(row["a"]["regime"], "frontal")
        self.assertEqual(row["regime"], "subfrontal")
        self.assertNotEqual(row["b"]["medians"], row["a"]["medians"])

    def test_dominance_mix_counts_half_cells_for_both(self) -> None:
        rows = [row_of(self.name, bundle({self.name: self.med[self.left]}),
                       bundle({self.name: (self.med[self.left] + self.med[self.right]) / 2}))]
        dom = F._dominance(rows, F.bands()["identities"])
        self.assertEqual(dom["a"]["mix"][self.left], 1.0)
        self.assertAlmostEqual(dom["b"]["mix"][self.left], 0.5, places=3)
        self.assertAlmostEqual(dom["b"]["mix"][self.right], 0.5, places=3)
        self.assertEqual(dom["b"]["attributed"], 1)
        self.assertEqual(dom["b"]["count"][self.left] + dom["b"]["count"][self.right], 1)
        self.assertIn(dom["b"]["lead"], (self.left, self.right))

    def test_dominance_of_unattributed_rows_is_empty(self) -> None:
        dom = F._dominance([], F.bands()["identities"])
        for side in ("a", "b"):
            self.assertIsNone(dom[side]["lead"])
            self.assertEqual(dom[side]["mix"], {})


class ReportShapeTest(unittest.TestCase):
    def test_identical_photos_agree_on_every_metric(self) -> None:
        values = {n: 1.0 for n in A.APPROVED_NAMES}
        rows = F.pair_rows(bundle(values), bundle(values, yaw=7.0))
        self.assertEqual(len(rows), 30)
        self.assertEqual(sum(r["trusted"] for r in rows), 9)
        self.assertEqual(F._count(rows)["same"], 30)
        self.assertEqual(F._count(rows, trusted=True)["total"], 9)
        self.assertEqual(F._count(rows, trusted=False)["total"], 21)
        # одинаковое значение не может смотреть на разных людей
        self.assertFalse(any(r["other_people"] for r in rows))

    def test_trusted_flag_and_grouping_survive(self) -> None:
        rows = F.pair_rows(bundle({}), bundle({}))
        self.assertEqual({r["group"] for r in rows}, {A.group(n) for n in A.APPROVED_NAMES})
        self.assertTrue(all(r["verdict"] == "unknown" for r in rows))

    def test_bands_missing_raises_when_file_absent(self) -> None:
        saved = F.BANDS_PATH
        try:
            F.BANDS_PATH = saved.parent / "no_such_bands.json"
            F.bands.cache_clear()
            with self.assertRaises(F.BandsMissing):
                F.bands()
        finally:
            F.BANDS_PATH = saved
            F.bands.cache_clear()


class RollCanonTest(unittest.TestCase):
    """Roll-канон MediaPipe: линия глаз горизонтальна, начало — середина глаз, z цел."""

    def setUp(self) -> None:
        rng = np.random.default_rng(7)
        pts = rng.normal(scale=40.0, size=(478, 3)).astype(np.float32)
        pts[33], pts[133] = [10.0, 30.0, 1.0], [20.0, 34.0, 2.0]
        pts[362], pts[263] = [90.0, 60.0, 3.0], [100.0, 64.0, 4.0]
        self.pts = pts
        self.out = roll_corrected(pts)

    def test_eye_line_is_horizontal_and_centered(self) -> None:
        eye_l = (self.out[33] + self.out[133]) / 2
        eye_r = (self.out[362] + self.out[263]) / 2
        self.assertAlmostEqual(float(eye_l[1]), float(eye_r[1]), places=3)
        self.assertAlmostEqual(float((eye_l[1] + eye_r[1]) / 2), 0.0, places=3)
        self.assertAlmostEqual(float((eye_l[0] + eye_r[0]) / 2), 0.0, places=3)

    def test_depth_and_dtype_untouched(self) -> None:
        self.assertTrue(np.allclose(self.out[:, 2], self.pts[:, 2]))
        self.assertEqual(self.out.dtype, self.pts.dtype)


class WorkerContractTest(unittest.TestCase):
    def test_asset_resolution_returns_path_or_none(self) -> None:
        asset = resolve_asset()
        self.assertTrue(asset is None or asset.is_file())

    def test_no_face_is_a_distinct_error_from_dead_worker(self) -> None:
        # «Лица нет» — 400 для сервера, «воркер сломан» — 503: подмена потеряла бы смысл.
        self.assertTrue(issubclass(FaceNotFound, MediaPipeUnavailable))

    def test_bands_file_is_valid_json_with_schema(self) -> None:
        payload = json.loads(F.BANDS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "morphing-metric-bands-v3")
        self.assertTrue(payload["caveats"])
        self.assertIn("k_differ", payload["meaning"])
        self.assertIn("signal_cross", payload["meaning"])
        self.assertIn("ref", payload["meaning"])   # эталонные медианы — основа цвета
        self.assertEqual(payload["identities"], ["put", "vas", "udmurt"])


if __name__ == "__main__":
    unittest.main()
