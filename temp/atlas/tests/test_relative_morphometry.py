import numpy as np
import pytest

from server.ocular import CATALOG, relative_face_metrics


def make_points(*, face_height, cheeks, jaw):
    points = np.zeros((478, 2), dtype=np.float64)
    points[10] = [0, 0]
    points[152] = [0, face_height]
    points[2] = [0, face_height * 0.72]
    points[234] = [-cheeks / 2, face_height * 0.42]
    points[454] = [cheeks / 2, face_height * 0.42]
    points[172] = [-jaw / 2, face_height * 0.8]
    points[397] = [jaw / 2, face_height * 0.8]
    points[149] = [-jaw * 0.2, face_height * 0.96]
    points[378] = [jaw * 0.2, face_height * 0.96]
    points[54] = [-cheeks * 0.38, face_height * 0.18]
    points[284] = [cheeks * 0.38, face_height * 0.18]
    points[468] = [-20, face_height * 0.35]
    points[473] = [20, face_height * 0.35]
    points[98] = [-18, face_height * 0.52]
    points[327] = [18, face_height * 0.52]
    points[193] = [-9, face_height * 0.25]
    points[417] = [9, face_height * 0.25]
    points[168] = [0, face_height * 0.3]
    return points


def test_twenty_relative_metric_tracks_are_catalogued():
    assert len(CATALOG) == 20
    assert len({item[0] for item in CATALOG}) == 20
    assert {"face_height_width", "jaw_cheek_ratio", "chin_jaw_ratio",
            "upper_face_width_cheek_ratio"} <= {item[0] for item in CATALOG}


def test_shape_ratios_distinguish_long_narrow_from_square_without_labels():
    thin = relative_face_metrics(make_points(face_height=240, cheeks=200, jaw=100))
    square = relative_face_metrics(make_points(face_height=200, cheeks=200, jaw=150))
    assert thin["face_height_width"] > square["face_height_width"]
    assert thin["jaw_cheek_ratio"] < square["jaw_cheek_ratio"]
    # Deliberately emits continuous ratios, not demographic or identity labels.
    assert not any(k in thin for k in ("identity", "face_class", "sex"))


def test_relative_face_metrics_reject_bad_landmarks():
    with pytest.raises(ValueError):
        relative_face_metrics(np.zeros((100, 2)))
    bad = np.zeros((478, 2))
    bad[10, 0] = np.nan
    with pytest.raises(ValueError):
        relative_face_metrics(bad)
