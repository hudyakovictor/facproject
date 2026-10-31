import numpy as np
import pytest
from test_within_bin_only import make_base

from src.face_model_io import ANNOTATION_NAMES, load_face_model
from src.zones import check_disjoint
from src.zones_annotation import zones_from_annotation


def synthetic_annotation(v):
    x, y = v[:, 0], v[:, 1]
    ax = np.abs(x)
    ids = np.arange(len(v))
    eye = (y > -0.2) & (y < -0.05) & (ax > 0.1) & (ax < 0.35)
    brow = (y > 0.0) & (y < 0.1) & (ax > 0.15) & (ax < 0.4)
    nose = (ax < 0.1) & (y > -0.4) & (y < -0.1)
    lips = (ax < 0.2) & (y > -0.65) & (y < -0.5)
    return [ids[eye & (x > 0)], ids[eye & (x < 0)], ids[brow & (x > 0)], ids[brow & (x < 0)],
            ids[nose], ids[lips & (y >= -0.575)], ids[lips & (y < -0.575)], ids]


def test_zones_from_annotation_disjoint_and_named():
    v = make_base(n=6000)
    zones = zones_from_annotation(synthetic_annotation(v), v)
    assert check_disjoint(zones)
    for name in ["right_eye", "left_eye", "nose", "upper_lip", "lower_lip", "forehead", "chin",
                 "cheek_r", "cheek_l", "jaw_r", "jaw_l"]:
        assert name in zones
    assert np.all(v[zones["cheek_r"], 0] > 0) and np.all(v[zones["cheek_l"], 0] < 0)
    assert np.all(v[zones["forehead"], 1] > v[zones["lower_lip"], 1].mean())
    assert len(np.concatenate(list(zones.values()))) == len(v)


def test_flipped_y_axis_is_error():
    v = make_base(n=6000)
    ann = synthetic_annotation(v)
    flipped = v.copy()
    flipped[:, 1] *= -1
    with pytest.raises(ValueError):
        zones_from_annotation(ann, flipped)


def test_load_face_model(tmp_path):
    ann = [np.arange(3) for _ in ANNOTATION_NAMES]
    path = tmp_path / "fm.npy"
    np.save(path, {"tri": np.array([[0, 1, 2]]), "annotation": ann, "ldm106": np.arange(106)}, allow_pickle=True)
    fm = load_face_model(path)
    assert fm["tri"].shape == (1, 3) and len(fm["annotation"]) == 8 and fm["ldm106"].shape == (106,)
    bad = tmp_path / "bad.npy"
    np.save(bad, {"annotation": ann}, allow_pickle=True)
    with pytest.raises(ValueError):
        load_face_model(bad)
