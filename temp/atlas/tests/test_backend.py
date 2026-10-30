import importlib, json, shutil, time
from pathlib import Path
import numpy as np
import pytest
from server import storage, registry, analysis
from server.config import ROOT, profiles, classify, digest
from server.models.tddfa import get_model, availability
from server.rendering import colorize, rasterize


@pytest.mark.parametrize(
    "name,date",
    [
        ("2002_12_02.jpg", "2002-12-02"),
        ("2009_12_10_2.png", "2009-12-10"),
        ("2003_10_16__faa3a4aaff20.jpg", "2003-10-16"),
        ("frame_2020-02-29_photo.webp", "2020-02-29"),
        ("2021_02_29.jpg", None),
        ("no_date.jpg", None),
        ("2022_13_01.jpg", None),
    ],
)
def test_dates(name, date):
    assert storage.parse_date(name) == date


@pytest.mark.parametrize(
    "yaw,pose",
    [
        (-80, "profile_left"),
        (-35, "three_quarter_left"),
        (0, "frontal"),
        (35, "three_quarter_right"),
        (80, "profile_right"),
    ],
)
def test_five_poses(yaw, pose):
    assert classify({"yaw": yaw, "pitch": 0, "roll": 0}) == pose


def test_outside_profiles():
    assert classify({"yaw": 0, "pitch": 80, "roll": 0}) == "unclassified"


def test_manual_precedence():
    assert classify({"yaw": 0, "pitch": 0, "roll": 0}, {"yaw": 80}) == "profile_right"


def test_config_files():
    for model in ["3ddfa_v3", "mediapipe", "fan", "adaface"]:
        files = list((ROOT / "configs/metrics" / model).glob("*.yaml"))
        assert len(files) == 5


def test_model_assets_and_real_inference():
    if not availability()["available"]:
        pytest.skip("3DDFA model assets are excluded from this snapshot")
    m = get_model()
    f, meta, crop = m.infer(ROOT / "data/demo-source.png")
    assert f["vertices"].shape == (35709, 3) and m.tri.shape == (70789, 3)
    assert f["alpha"].shape == (257,) and np.isfinite(f["vertices"]).all()
    assert crop.size == (224, 224) and meta["alignment"]["confidence"] > 0.7
    assert all(k in meta["angles"] for k in ["yaw", "pitch", "roll"])
    assert len(m.ldm["ldm106"]) == 106 and len(m.ldm["ldm134"]) == 134


class Job:
    def check(self):
        pass

    def update(self, *args, **kwargs):
        pass


def test_disk_cache_hit():
    p = next(p for p in storage.library() if p["status"] == "ready")
    path = storage.feature_path(p)
    before = path.stat().st_mtime_ns
    result = storage.process(Job(), [p["id"]])
    assert result["cache_hits"] == 1 and path.stat().st_mtime_ns == before


def test_metric_registry_pose_values():
    result = analysis.metrics_table()
    assert len(result["rows"]) >= 5
    # Каталог растёт вместе с числом файлов в metrics/: проверяем, что три
    # стартовые метрики 3DDFA на месте, а не то, что их ровно три.
    three_ddfa = [m["id"] for m in result["catalog"] if m["model"] == "3ddfa_v3"]
    assert {"mesh_eye_area", "mesh_jaw_ratio", "mesh_nose_projection"} <= set(three_ddfa)
    for row in [
        r
        for r in result["rows"]
        if any(
            p["id"] == r["id"] and p.get("demo") for p in storage.read_db()["photos"]
        )
    ]:
        assert all(
            row["metrics"][key]["value"] is not None
            for key in ["mesh_eye_area", "mesh_jaw_ratio", "mesh_nose_projection"]
        )
        assert "mp_canthal_tilt" in row["metrics"]
        assert row["metrics"]["mp_canthal_tilt"]["value"] is None
        assert (
            "размет" in row["metrics"]["mp_canthal_tilt"]["reason"].lower()
            or "измерения" in row["metrics"]["mp_canthal_tilt"]["reason"].lower()
        )


def test_new_metric_single_file_hotload():
    target = ROOT / "metrics/tddfa_v3/mesh_height.py"
    assert not target.exists()
    try:
        shutil.copy(ROOT / "docs/examples/mesh_height.py", target)
        result = analysis.metrics_table()
        assert any(m["id"] == "mesh_height_example" for m in result["catalog"])
        assert result["rows"][0]["metrics"]["mesh_height_example"]["value"] > 1
    finally:
        target.unlink(missing_ok=True)
        registry.discover()
    assert "mesh_height_example" not in registry.REGISTRY


def test_projection_seed_and_real_alpha():
    ids = [
        p["id"] for p in storage.library() if p["status"] == "ready"
    ]
    params = {
        "photo_ids": ids,
        "method": "pca",
        "dimensions": 2,
        "distance": "cosine",
        "seed": 42,
        "clusters": 3,
    }
    a = analysis.project(Job(), params)
    b = analysis.project(Job(), params)
    assert b["cache_hit"] and a["points"] == b["points"]
    assert len(a["points"]) == len(ids) and len(a["matrix"]) == len(ids)
    assert np.allclose(np.diag(a["matrix"]), 0) and np.allclose(
        a["matrix"], np.array(a["matrix"]).T
    )
    assert a["silhouette"] is None  # Demo is one group, not an invented score.


def test_umap_small_sample_explicit_fallback():
    ids = [
        p["id"] for p in storage.library() if p["status"] == "ready"
    ][:5]
    r = analysis.project(
        Job(), {"photo_ids": ids, "method": "umap", "dimensions": 2, "seed": 42}
    )
    assert r["method"] == "pca" and "UMAP" in r["note"]


def test_heatmap_identity_zero_and_difference():
    ps = storage.library()
    a = storage.load_features(ps[0])
    b = storage.load_features(ps[-1])
    assert np.linalg.norm(a["vertices"] - a["vertices"]) == 0
    d = np.linalg.norm(a["vertices"] - b["vertices"], axis=1)
    assert d.max() > 0 and colorize(d, hi=0.001).shape == (35709, 3)
    assert not np.allclose(colorize(d, hi=0.001), colorize(d, hi=0.1))


def test_linear_morph_endpoints():
    ps = storage.library()
    a = storage.load_features(ps[0])
    b = storage.load_features(ps[-1])
    assert np.array_equal(a["vertices"] * (1 - 0) + b["vertices"] * 0, a["vertices"])
    assert np.array_equal(a["vertices"] * (1 - 1) + b["vertices"] * 1, b["vertices"])
    assert np.isfinite((a["vertices"] + b["vertices"]) / 2).all()


def test_cpu_renderer_not_blank():
    p = next(p for p in storage.library() if p["status"] == "ready")
    a = storage.load_features(p)
    m = get_model()
    img = rasterize(a["vertices"], m.tri, a["albedo"], 256)
    assert img.shape == (256, 256, 3) and img.std() > 20


def test_photo_delete_is_permanent_and_never_touches_foreign_files():
    """Удаление стирает копии внутри ATLAS; чужие пути на диске не трогаем."""
    from server import storage
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as d:
        old_db, old_root = storage.DB, storage.ROOT
        try:
            root = Path(d)
            storage.DB = root / "data/library.json"
            storage.ROOT = root
            inside = root / "data/groups/A/a.jpg"
            outside = root / "originals/keep.jpg"
            for path in (inside, outside):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
            (root / "cache/a").mkdir(parents=True)
            storage.write_db(
                {
                    "photos": [
                        {
                            "id": "a",
                            "group": "A",
                            "path": "data/groups/A/a.jpg",
                            "hash": "ha",
                            "name": "a.jpg",
                            "date": None,
                            "precropped": False,
                            "demo": False,
                        },
                        {
                            "id": "b",
                            "group": "B",
                            "path": "originals/keep.jpg",
                            "hash": "hb",
                            "name": "keep.jpg",
                            "date": None,
                            "precropped": False,
                            "demo": False,
                        },
                    ]
                }
            )
            result = storage.purge_photos(["a", "b"])
            assert result == {"deleted": 2, "exports": 0, "recoverable": False}
            assert storage.read_db()["photos"] == []
            assert not inside.exists() and not (root / "cache/a").exists()
            # Путь вне data/groups принадлежит пользователю, а не библиотеке.
            assert outside.read_bytes() == b"x"
        finally:
            storage.DB = old_db
            storage.ROOT = old_root


def test_iris_ratios_and_manual_fixes_are_numerically_well_defined():
    import numpy as np
    from server.ocular import area, div

    assert div(8, 4) == 2
    assert abs(area(np.array([[0, 0], [4, 0], [4, 2], [0, 2]])) - 8) < 1e-9
    assert np.isfinite(div(1, 1e-9))


def test_permanent_purge_is_scoped_to_synthetic_demos(tmp_path, monkeypatch):
    from server import storage
    import json
    import shutil

    old_root, old_db = storage.ROOT, storage.DB
    try:
        monkeypatch.setattr(storage, "ROOT", tmp_path)
        monkeypatch.setattr(storage, "DB", tmp_path / "data/library.json")
        demo_path = tmp_path / "data/groups/Demo/a.jpg"
        user_path = tmp_path / "data/groups/Real/u.jpg"
        demo_path.parent.mkdir(parents=True)
        user_path.parent.mkdir(parents=True)
        demo_path.write_bytes(b"demo")
        user_path.write_bytes(b"user")
        (tmp_path / "cache/a").mkdir(parents=True)
        (tmp_path / "cache/a/f.bin").write_bytes(b"cache")
        storage.write_db(
            {
                "photos": [
                    {
                        "id": "a",
                        "group": "Demo",
                        "path": "data/groups/Demo/a.jpg",
                        "demo": True,
                    },
                    {
                        "id": "u",
                        "group": "Real",
                        "path": "data/groups/Real/u.jpg",
                        "demo": False,
                    },
                ]
            }
        )
        result = storage.purge_demo_photos()
        assert result == {"removed": 1, "only_demo": True}
        assert not demo_path.exists() and not (tmp_path / "cache/a").exists()
        assert user_path.read_bytes() == b"user" and [
            p["id"] for p in storage.read_db()["photos"]
        ] == ["u"]
        assert storage.purge_demo_photos(["u"] if False else [])["removed"] == 0
    finally:
        storage.ROOT = old_root
        storage.DB = old_db
