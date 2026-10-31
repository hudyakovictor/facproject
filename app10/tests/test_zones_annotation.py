import numpy as np
import pytest
from test_within_bin_only import make_base  # noqa: F401  (используется в других тестах модуля)

from src.face_model_io import ANNOTATION_NAMES, load_face_model
from src.landmarks import EXPECTED_SIZES, SCALAR_KEYS, load_landmark_groups
from src.mesh_geometry import vertex_normals
from src.zones import check_disjoint, zones_sha256
from src.zones_annotation import NON_FACE_ZONES, zones_from_annotation


def make_face(nx=41, ny=41):
    """Симметричный плоский грид-лицо: нечётное nx -> есть центральный столбец x=0 (ориентиры средней линии); y вверх."""
    xs = (np.arange(nx) + 0.5) / nx * 2.4 - 1.2
    ys = (np.arange(ny) + 0.5) / ny * 2.8 - 1.4
    X, Y = np.meshgrid(xs, ys)
    return np.column_stack([X.ravel(), Y.ravel(), np.zeros(X.size)])


def grid_triangles(nx=41, ny=41):
    """Треугольники грида; нормаль плоской сетки смотрит в +z."""
    tri = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            b, c, d = a + 1, a + nx, a + nx + 1
            tri += [[a, b, d], [a, d, c]]
    return np.array(tri, dtype=np.int64)


def _nearest(v, xy):
    return int(np.argmin(((v[:, :2] - np.asarray(xy)) ** 2).sum(1)))


def _ldm106_targets():
    T = [None] * 106
    for i, th in enumerate(np.linspace(np.pi, 2 * np.pi, 33)):  # контур 0..32 (U снизу), 16 = низ подбородка
        T[i] = (1.1 * np.cos(th), 1.3 * np.sin(th) + 0.2)
    T[33] = (-0.72, 0.95)  # brow_outer_right
    for k, i in enumerate(range(34, 42)):  # right_eyebrow
        T[i] = (-0.66 + 0.06 * k, 0.96)
    for k, i in enumerate(range(42, 51)):  # left_eyebrow (46 = внешний)
        T[i] = (0.72, 0.95) if i == 46 else (0.30 + 0.06 * k, 0.96)
    nose = [(0, .55), (0, .45), (0, .15), (0, .05), (0, .35),
            (-.12, .1), (-.16, -.05), (-.12, -.15), (-.05, -.12), (0, -.15),
            (.05, -.12), (.12, -.15), (.16, -.05), (.12, .1), (.05, .3)]
    for i, xy in zip(range(51, 66), nose, strict=True):
        T[i] = xy
    for k, i in enumerate(range(66, 75)):  # right_eye
        T[i] = (-0.5 + 0.05 * k, 0.55)
    for k, i in enumerate(range(75, 84)):  # left_eye
        T[i] = (0.15 + 0.05 * k, 0.55)
    T[84] = (-0.35, -0.5)  # mouth_corner_right
    T[90] = (0.35, -0.5)   # mouth_corner_left
    for k, i in enumerate([85, 86, 87, 88, 89, 97, 98, 99]):  # upper_lip
        T[i] = (-0.28 + 0.08 * k, -0.45)
    for k, i in enumerate([91, 92, 93, 94, 95, 96, 100, 101, 102, 103]):  # lower_lip
        T[i] = (-0.3 + 0.1 * k, -0.62)
    T[104] = (-0.35, 0.55)
    T[105] = (0.35, 0.55)
    return T


def synthetic_face(curved=False, radius=1.3):
    v = make_face()
    T = _ldm106_targets()
    ldm106 = np.array([_nearest(v, xy) for xy in T], dtype=np.int64)
    x, y = v[:, 0], v[:, 1]
    ax = np.abs(x)
    ids = np.arange(len(v))
    eye = (y > 0.45) & (y < 0.68) & (ax > 0.12) & (ax < 0.55)
    brow = (y > 0.85) & (y < 1.05) & (ax > 0.2) & (ax < 0.78)
    nose = (ax < 0.18) & (y > -0.2) & (y < 0.6)
    lips = (ax < 0.4) & (y > -0.7) & (y < -0.4)
    feat = [ids[eye & (x < 0)], ids[eye & (x > 0)], ids[brow & (x < 0)], ids[brow & (x > 0)],
            ids[nose], ids[lips & (y >= -0.55)], ids[lips & (y < -0.55)]]
    used = np.concatenate(feat)
    skin = ids[~np.isin(ids, used)]
    annotation = feat + [skin]
    if curved:  # выпуклая к зрителю поверхность: нормаль ~ (x/R, 0, z/R)
        v = v.copy()
        v[:, 2] = np.sqrt(np.maximum(radius ** 2 - v[:, 0] ** 2, 1e-9))
    return annotation, v, ldm106


GROUPS = load_landmark_groups()


def _as_sets(zones):
    return {k: set(int(i) for i in v) for k, v in zones.items()}


def test_zones_from_landmarks_disjoint_cover_and_side():
    ann, v, ldm106 = synthetic_face()
    zones = zones_from_annotation(ann, v, ldm106, groups=GROUPS)
    assert check_disjoint(zones)
    assert len(np.concatenate(list(zones.values()))) == len(v)  # полное покрытие
    for name in ["right_eye", "left_eye", "nose", "upper_lip", "lower_lip", "forehead", "chin",
                 "cheek_r", "cheek_l", "jaw_r", "jaw_l", "side"]:
        assert name in zones
    assert v[zones["cheek_r"], 0].max() < v[zones["cheek_l"], 0].min()
    assert np.all(v[zones["forehead"], 1] > v[zones["cheek_r"], 1].max() - 1.0)
    assert v[zones["side"], 0].min() < v[zones["cheek_r"], 0].min()
    assert set(NON_FACE_ZONES) <= set(zones)


def test_cheek_and_jaw_symmetry_on_symmetric_grid():
    ann, v, ldm106 = synthetic_face()
    zones = zones_from_annotation(ann, v, ldm106, groups=GROUPS)
    for a, b in [("cheek_r", "cheek_l"), ("jaw_r", "jaw_l")]:
        ra, rb = len(zones[a]), len(zones[b])
        assert abs(ra - rb) <= 0.05 * max(ra, rb), (a, ra, rb)


def test_symmetry_survives_real_asymmetry_of_the_face():
    """Правая половина лица шире на 3%: зеркальная граница не должна разъехать щёки и челюсти."""
    ann, v, ldm106 = synthetic_face()
    wide = v.copy()
    wide[wide[:, 0] < 0, 0] *= 1.03
    zones = zones_from_annotation(ann, wide, ldm106, groups=GROUPS)
    ra, rb = len(zones["cheek_r"]), len(zones["cheek_l"])
    assert abs(ra - rb) <= 0.05 * max(ra, rb), ("cheek", ra, rb)
    ja, jb = len(zones["jaw_r"]), len(zones["jaw_l"])
    assert abs(ja - jb) <= 0.10 * max(ja, jb), ("jaw", ja, jb)  # в челюсти ~50 вершин, допуск шире


def test_zones_invariant_to_rigid_shift_along_x():
    """Все x-границы относительно плоскости симметрии: сдвиг всей сетки не меняет состав зон."""
    ann, v, ldm106 = synthetic_face()
    base = _as_sets(zones_from_annotation(ann, v, ldm106, groups=GROUPS))
    shifted = v.copy()
    shifted[:, 0] += 0.07
    moved = _as_sets(zones_from_annotation(ann, shifted, ldm106, groups=GROUPS))
    differ = sum(len(base[k] ^ moved[k]) for k in base)
    # допускаем единичные вершины ровно на границе (на синтетике пороги совпадают с координатами вершин);
    # прежняя схема с разными системами отсчёта x давала ~6% вершин
    assert differ <= 0.005 * len(v), differ


def test_flat_surface_normals_do_not_change_zones():
    ann, v, ldm106 = synthetic_face()
    tri = grid_triangles()
    a = _as_sets(zones_from_annotation(ann, v, ldm106, groups=GROUPS))
    b = _as_sets(zones_from_annotation(ann, v, ldm106, tri=tri, groups=GROUPS))
    assert a == b  # у плоской сетки |nx| = 0, боковое правило не срабатывает


def test_lateral_normal_rule_applies_only_above_mouth():
    ann, v, ldm106 = synthetic_face(curved=True, radius=1.3)
    tri = grid_triangles()
    without = zones_from_annotation(ann, v, ldm106, groups=GROUPS)
    with_tri = zones_from_annotation(ann, v, ldm106, tri=tri, groups=GROUPS)
    extra = np.setdiff1d(with_tri["side"], without["side"])
    assert len(extra) > 0, "боковая нормаль на выпуклой поверхности должна добавить вершины в side"
    nx = np.abs(vertex_normals(v, tri)[extra, 0])
    assert np.all(nx > 0.8)
    mouth_y = (v[ldm106[84], 1] + v[ldm106[90], 1]) / 2
    assert np.all(v[extra, 1] > mouth_y)  # ниже рта боковая нормаль не применяется
    for name in ("jaw_r", "jaw_l", "chin"):
        assert _as_sets({name: with_tri[name]}) == _as_sets({name: without[name]})
    assert check_disjoint(with_tri)
    assert len(np.concatenate(list(with_tri.values()))) == len(v)


def test_flipped_y_axis_is_error():
    ann, v, ldm106 = synthetic_face()
    flipped = v.copy()
    flipped[:, 1] *= -1
    with pytest.raises(ValueError):
        zones_from_annotation(ann, flipped, ldm106, groups=GROUPS)


def test_landmark_group_sizes_and_scalars():
    groups = load_landmark_groups()
    for name, size in EXPECTED_SIZES.items():
        assert len(groups[name]) == size, name
    for name in SCALAR_KEYS:
        assert isinstance(groups[name], int) and 0 <= groups[name] <= 105, name


def test_zones_sha256_is_content_hash():
    z = {"a": [3, 1, 2], "b": [9, 8]}
    assert zones_sha256(z) == zones_sha256({"a": [1, 2, 3], "b": [8, 9]})  # порядок индексов не важен
    assert zones_sha256(z) != zones_sha256({"a": [1, 2, 4], "b": [8, 9]})  # смена индексов -> другой хеш


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
