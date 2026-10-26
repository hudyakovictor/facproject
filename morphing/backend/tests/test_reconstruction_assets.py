from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app8 import reconstruction


ASSETS = (
    "face_model.npy",
    "net_recon.pth",
    "retinaface_resnet50_2020-07-20_old_torch.pth",
    "large_base_net.pth",
    "similarity_Lm3D_all.mat",
)


class ReconstructionAssetTests(unittest.TestCase):
    def test_complete_local_assets_need_no_network_or_directories(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assets = root / "assets"
            assets.mkdir()
            for name in ASSETS:
                (assets / name).write_bytes(b"local weights")
            with patch.object(reconstruction, "TDDFA", root), patch("urllib.request.urlopen") as download, patch.object(Path, "mkdir") as mkdir:
                reconstruction.ensure_assets()
            download.assert_not_called()
            mkdir.assert_not_called()

    def test_only_missing_asset_is_downloaded(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assets = root / "assets"
            assets.mkdir()
            for name in ASSETS[:-1]:
                (assets / name).write_bytes(b"local weights")
            cache = root / "cache"

            def local_path(value):
                return cache if value == "/tmp/assets" else Path(value)

            with patch.object(reconstruction, "TDDFA", root), patch.object(reconstruction, "Path", side_effect=local_path), patch("urllib.request.urlopen", return_value=io.BytesIO(b"downloaded weights")) as download:
                reconstruction.ensure_assets()
            self.assertEqual(download.call_count, 1)
            self.assertEqual((assets / ASSETS[-1]).read_bytes(), b"downloaded weights")
            self.assertEqual((assets / ASSETS[0]).read_bytes(), b"local weights")

    def test_detector_exit_is_a_missing_face_not_process_exit(self) -> None:
        with patch.object(reconstruction, "get_models", return_value=(None, lambda image: (_ for _ in ()).throw(SystemExit()), None)), patch("app8.imaging.decode_oriented_bgr") as decode:
            import numpy as np

            decode.return_value = np.zeros((224, 224, 3), dtype=np.uint8)
            self.assertIsNone(reconstruction.reconstruct_image("unused.jpg"))

    def test_uncropped_detector_fallback_is_rejected(self) -> None:
        with patch.object(reconstruction, "get_models", return_value=(None, lambda image: (None, object()), None)), patch("app8.imaging.decode_oriented_bgr") as decode:
            import numpy as np

            decode.return_value = np.zeros((224, 224, 3), dtype=np.uint8)
            self.assertIsNone(reconstruction.reconstruct_image("unused.jpg"))


if __name__ == "__main__":
    unittest.main()
