import numpy as np

from server.models.tddfa import TDDFA


def test_photo_uv_uses_tddfa_row_vector_rotation_convention():
    model = TDDFA.__new__(TDDFA)
    model.basis = {
        "u": np.array([1.2, 0.2, 0.1, 0.3, 1.1, -0.2, -0.7, 0.1, 0.2], np.float32),
        "id": np.zeros((9, 80), np.float32),
        "exp": np.zeros((9, 64), np.float32),
    }
    alpha = np.zeros(257, np.float32)
    alpha[224:227] = [0.16, 0.51, -0.08]
    alpha[254:257] = [0.1, -0.2, 0.3]
    got = model.photo_uv(alpha, 224, 224, {"crop": [0, 0, 1]})

    x, y, z = alpha[224:227]
    rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    shape = model.basis["u"].reshape(-1, 3)
    # Upstream Recon.compute_rotation returns this transpose for row vectors.
    camera = shape @ (rz @ ry @ rx).T + alpha[254:257]
    depth = 10.0 - camera[:, 2]
    px = 1015.0 * camera[:, 0] / depth + 112.0
    py = 1015.0 * camera[:, 1] / depth + 112.0
    expected = np.stack([px / 223.0, 1.0 - (223.0 - py) / 223.0], axis=-1).astype("<f4")
    np.testing.assert_allclose(got, expected, rtol=1e-6, atol=1e-6)


def test_photo_uv_rejects_nonfinite_rotation_projection():
    model = TDDFA.__new__(TDDFA)
    model.basis = {"u": np.zeros(9), "id": np.zeros((9, 80)), "exp": np.zeros((9, 64))}
    alpha = np.zeros(257)
    alpha[225] = np.nan
    try:
        model.photo_uv(alpha, 224, 224, {"crop": [0, 0, 1]})
    except ValueError as exc:
        assert "non-finite" in str(exc)
    else:
        raise AssertionError("non-finite projected UV must be rejected")
