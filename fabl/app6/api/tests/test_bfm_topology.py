"""🎯 GUARD → BFM-геометрия: понятные ошибки и коррекция вычисления (ER-019).

BFMModel.compute_shape валидирует размерность alpha_id/alpha_exp с понятным
сообщением (ожидаемое vs фактическое число компонентов) и вычисляет форму
mean + id-basis·alpha_id + exp-basis·alpha_exp. Проверяется на полностью
синтетической модели — без загрузки реальных весов.
"""
from __future__ import annotations

import unittest

import numpy as np

from app6.api.bfm_topology import BFMModel


def _tiny_model(n_id: int = 3, n_exp: int = 2) -> BFMModel:
    n_vert = 4
    return BFMModel(
        mean_shape=np.arange(n_vert * 3, dtype=np.float32).reshape(n_vert, 3),
        id_basis=np.random.default_rng(0).normal(0, 1, (n_vert, 3, n_id)).astype(np.float32),
        exp_basis=np.random.default_rng(1).normal(0, 1, (n_vert, 3, n_exp)).astype(np.float32),
        triangles=np.array([[0, 1, 2], [1, 2, 3]], np.int64),
        ldm106_indices=np.arange(0, min(106, n_vert), dtype=np.int64),
        ldm134_indices=np.arange(0, min(134, n_vert), dtype=np.int64),
        primary_triangle_zone=np.array([1, 2], np.int16),
        primary_zone_ids=["A01"],
        primary_zone_names=["forehead"],
        face_support=np.array([True, True]),
    )


class ComputeShapeTests(unittest.TestCase):
    def test_wrong_alpha_id_gives_clear_message(self):
        model = _tiny_model(n_id=3)
        with self.assertRaises(ValueError) as ctx:
            model.compute_shape(np.zeros(5, np.float32), np.zeros(2, np.float32))
        self.assertIn("alpha_id", str(ctx.exception))
        self.assertIn("3", str(ctx.exception))  # ожидаемое число компонентов
        self.assertIn("5", str(ctx.exception))  # фактическое число

    def test_wrong_alpha_exp_gives_clear_message(self):
        model = _tiny_model(n_exp=2)
        with self.assertRaises(ValueError) as ctx:
            model.compute_shape(np.zeros(3, np.float32), np.zeros(9, np.float32))
        self.assertIn("alpha_exp", str(ctx.exception))
        self.assertIn("2", str(ctx.exception))
        self.assertIn("9", str(ctx.exception))

    def test_zero_alpha_returns_mean_shape(self):
        model = _tiny_model()
        out = model.compute_shape(np.zeros(3, np.float32), np.zeros(2, np.float32))
        np.testing.assert_allclose(out, model.mean_shape, atol=1e-6)

    def test_shape_formula_matches_definition(self):
        model = _tiny_model()
        aid = np.ones(3, np.float32)
        aexp = np.ones(2, np.float32)
        out = model.compute_shape(aid, aexp)
        expected = (
            model.mean_shape
            + np.tensordot(model.id_basis, aid, axes=([2], [0]))
            + np.tensordot(model.exp_basis, aexp, axes=([2], [0]))
        )
        np.testing.assert_allclose(out, expected.astype(np.float32), atol=1e-5)
        self.assertEqual(out.dtype, np.float32)


if __name__ == "__main__":
    unittest.main()