import unittest
import numpy as np
from uv_module import HDUVConfig, HDUVTextureGenerator


class TestUVModule(unittest.TestCase):
    def setUp(self):
        yy, xx = np.mgrid[:96, :96]
        self.image = np.dstack(((xx*2)%256, (yy*2)%256, ((xx+yy)*2)%256)).astype(np.uint8)
        self.recon = {
            "vertices_2d": np.array([[12, 12], [82, 12], [82, 82], [12, 82]], np.float32),
            "vertices_3d": np.zeros((4, 3), np.float32),
            "triangles": np.array([[0, 1, 2], [0, 2, 3]], np.int64),
            "uv_coords": np.array([[.15, .15], [.85, .15], [.85, .85], [.15, .85]], np.float32),
            "normals_3d": np.tile(np.array([[0, 0, 1]], np.float32), (4, 1)),
            "alpha_sh": np.zeros(27, np.float32),
        }

    def test_two_products_and_provenance(self):
        a, s, observed, conf, aux = HDUVTextureGenerator(HDUVConfig(uv_size=256)).generate(self.image, self.recon)
        self.assertEqual(a.shape, (256, 256, 3)); self.assertEqual(s.shape, a.shape)
        self.assertTrue(np.all(a[~observed] == 0))
        self.assertTrue(np.all(conf[~observed] == 0))
        self.assertFalse(np.any(aux["uv_synthetic_mask"] & observed))
        self.assertTrue(np.array_equal(a[observed], s[observed]))

    def test_resolution_guard(self):
        with self.assertRaises(ValueError):
            HDUVConfig(uv_size=1001)

if __name__ == "__main__":
    unittest.main()
