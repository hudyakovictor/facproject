"""Photo-space projection used by the canonical UV atlas.

The regression these tests pin: 3DDFA applies pose as ``shape @ rot`` where
``rot`` is already transposed by ``compute_rotation``. Multiplying by the
untransposed ``Rz @ Ry @ Rx`` shifts every projected landmark by up to a
hundred pixels and smears the atlas.
"""

import numpy as np
import pytest

from server.config import ASSETS
from server.models.tddfa import basis_arrays, pose_rotation, project_to_photo
from server import storage


def axis_rotations(angles):
    x, y, z = angles
    rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    return rz @ ry @ rx


def test_pose_rotation_is_the_transpose_upstream_returns():
    rng = np.random.default_rng(7)
    angles = rng.uniform(-1.2, 1.2, 3)
    points = rng.normal(size=(16, 3))
    rot = axis_rotations(angles)
    # Upstream multiplies column points by Rz @ Ry @ Rx; row vectors therefore
    # need the transposed product.
    assert np.allclose(points @ pose_rotation(angles), (rot @ points.T).T)


def test_positive_yaw_turns_the_face_to_the_right():
    forward = np.array([1.0, 0.0, 0.0]) @ pose_rotation(np.array([0, np.pi / 2, 0]))
    assert np.allclose(forward, [0, 0, -1], atol=1e-9)


def stub_basis(points):
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    n = len(pts)
    return {
        "u": pts.reshape(-1, 1),
        "id": np.zeros((n * 3, 80)),
        "exp": np.zeros((n * 3, 64)),
    }


def alpha_at(translation):
    a = np.zeros(257)
    a[254:257] = translation
    return a


def test_yunet_crop_window_is_undone_in_source_pixels():
    basis = stub_basis(np.zeros((4, 3)))
    # crop = [left, top, scale] of a 1000x800 photo resized by 0.5.
    alignment = {"mode": "yunet_pos5", "crop": [100, 50, 0.5]}
    uv = project_to_photo(basis, alpha_at([0, 0, 0]), 1000, 800, alignment)
    # Zero translation projects to the principal point (112, 112) of the
    # aligned frame, i.e. source pixel (212, 162) after undoing the crop.
    expected = [424 / 999, 1 - 322 / 799]
    assert np.allclose(uv, expected, atol=1e-6)


def test_manual_precropped_maps_the_224_frame_onto_the_whole_photo():
    basis = stub_basis(np.zeros(3))
    uv = project_to_photo(
        basis, alpha_at([0, 0, 0]), 448, 224, {"mode": "manual_precropped"}
    )
    assert np.allclose(uv, [[224 / 447, 1 - 111 / 223]] * 3, atol=1e-6)


def test_alignment_without_crop_geometry_is_an_error():
    basis = stub_basis(np.zeros(3))
    with pytest.raises(ValueError):
        project_to_photo(basis, alpha_at([0, 0, 0]), 800, 800, {"mode": "yunet_pos5"})
    with pytest.raises(ValueError):
        project_to_photo(
            basis, alpha_at([0, 0, 0]), 800, 800, {"crop": [0, 0, 0]}
        )


def test_short_alpha_and_tiny_photo_are_rejected():
    basis = stub_basis(np.zeros(3))
    with pytest.raises(ValueError):
        project_to_photo(basis, np.zeros(128), 800, 800, {"crop": [0, 0, 1]})
    with pytest.raises(ValueError):
        project_to_photo(basis, alpha_at([0, 0, 0]), 1, 800, {"crop": [0, 0, 1]})


def test_pose_changes_the_projection():
    basis = stub_basis(np.array([[0.05, 0.0, 0.5]]))
    center = project_to_photo(basis, alpha_at([0, 0, 0]), 800, 800, {"crop": [0, 0, 1]})
    turned = alpha_at([0, 0, 0])
    turned[225] = 0.6
    uv = project_to_photo(basis, turned, 800, 800, {"crop": [0, 0, 1]})
    assert not np.allclose(center, uv)


@pytest.mark.skipif(
    not (ASSETS / "face_model.npy").exists(), reason="3DMM basis is not installed"
)
def test_real_alpha_projects_the_face_inside_the_photo():
    photo = next(
        (
            p
            for p in storage.library()
            if p["status"] == "ready" and abs(p["angles"]["yaw"]) < 30
        ),
        None,
    )
    if photo is None:
        pytest.skip("no processed near-frontal photo")
    record = storage.photo(photo["id"])
    alignment = dict(photo["meta"].get("alignment") or {})
    if record["precropped"] and not alignment.get("crop"):
        alignment["mode"] = "manual_precropped"
    from PIL import Image, ImageOps

    from server.config import ROOT

    with Image.open(ROOT / record["path"]) as im:
        w, h = ImageOps.exif_transpose(im).size
    basis = basis_arrays()
    alpha = storage.load_features(record, ["alpha"])["alpha"]
    uv = project_to_photo(basis, alpha, w, h, alignment)
    assert uv.shape == (len(basis["u"]) // 3, 2)
    assert np.isfinite(uv).all()
    inside = ((uv > 0) & (uv < 1)).all(1).mean()
    assert inside > 0.6
    assert abs(np.median(uv[:, 0]) - 0.5) < 0.2
    assert abs(np.median(uv[:, 1]) - 0.5) < 0.2
