import io, json, zipfile
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from server.app import app
from server import storage
from server.config import ROOT
import server.app as api_module
import server.models.tddfa as model_module


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def sample_ids(minimum=2):
    # Use only active, already-cached images. Never revive trashed demos, infer
    # against uncached user uploads, or mutate the user's library in tests.
    ids = [p["id"] for p in storage.library() if p["status"] == "ready"]
    if len(ids) < minimum:
        pytest.skip(f"requires {minimum} preprocessed sample photos")
    return ids


def test_health_and_cpu_optional_models(client):
    assert client.get("/api/health").json()["ffmpeg"]
    models = client.get("/api/models").json()
    model = next(m for m in models if m["id"] == "3ddfa_v3")
    if not model["available"]:
        pytest.skip("3DDFA model assets are excluded from this snapshot")
    mp = next(m for m in models if m["id"] == "mediapipe")
    if mp["available"]:
        assert mp["device"] == "CPU"
    else:
        assert mp["reason"]
    assert all(not m["available"] for m in models if m["id"] in ("fan", "adaface"))


def test_missing_weights_degrades_without_losing_cached_view(
    client, monkeypatch, tmp_path
):
    monkeypatch.setattr(model_module, "ASSETS", tmp_path)
    m = client.get("/api/models").json()[0]
    assert not m["available"] and not m["enabled"] and m["reason"]
    assert client.get("/api/library").status_code == 200
    assert client.get("/api/metrics").status_code == 200
    assert client.get("/api/photos/" + sample_ids()[0] + "/mesh").status_code == 200
    assert client.post("/api/process", json={}).status_code == 503


def test_disabled_model_rejects_new_inference(client, monkeypatch):
    monkeypatch.setattr(api_module, "model_settings", lambda: {"3ddfa_v3": False})
    assert client.post("/api/process", json={}).status_code == 409
    assert client.get("/api/photos/" + sample_ids()[0] + "/mesh").status_code == 200


def test_binary_mesh_and_version_headers(client):
    response = client.get("/api/photos/" + sample_ids()[0] + "/mesh")
    assert response.status_code == 200
    assert np.frombuffer(response.content, dtype="<f4").size == 35709 * 9
    assert "no-cache" in response.headers["cache-control"] and response.headers["etag"]


def test_invalid_export_counts_and_parameters(client):
    ids = sample_ids()
    for payload in [
        {"photo_ids": ids[:1]},
        {"photo_ids": [ids[0]] * 2},
        {"photo_ids": ids[:2], "resolution": 999},
        {"photo_ids": ids[:2], "vmin": 0.3, "vmax": 0.1},
    ]:
        assert client.post("/api/morph", json=payload).status_code == 400
    assert (
        client.post(
            "/api/projection", json={"photo_ids": ids[:2], "method": "not-a-method"}
        ).status_code
        == 400
    )


def test_invalid_profile_is_not_written(client):
    before = (ROOT / "configs/pose_profiles.yaml").read_bytes()
    profiles = client.get("/api/profiles").json()
    profiles["profiles"][0]["yaw"] = [40, 20]
    assert client.put("/api/profiles", json=profiles).status_code == 400
    assert (ROOT / "configs/pose_profiles.yaml").read_bytes() == before


def test_csv_contains_values_and_robust_z(client):
    r = client.get("/api/export/metrics.csv")
    assert r.status_code == 200
    assert "mesh_eye_area:value" in r.text and "mesh_eye_area:robust_z" in r.text


def test_storage_upload_and_safe_zip_in_temporary_root(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(storage, "DB", tmp_path / "data/library.json")
    b = io.BytesIO()
    Image.new("RGB", (50, 50), (120, 130, 140)).save(b, "JPEG")
    content = b.getvalue()
    ids = storage.ingest([("group-A/2003_10_16__hash.jpg", content)])
    assert len(ids) == 1 and storage.photo(ids[0])["date"] == "2003-10-16"
    assert not storage.ingest([("group-A/2003_10_16__hash.jpg", content)])
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as archive:
        archive.writestr("../../../../2009_12_10_2.jpg", content)
    items = storage.unpack_zip(z.getvalue())
    more = storage.ingest(items)
    assert len(more) == 1
    assert (
        (tmp_path / storage.photo(more[0])["path"]).resolve().is_relative_to(tmp_path)
    )
    with pytest.raises(ValueError):
        storage.unpack_zip(b"not a zip")


def test_cpu_preview_renders_all_heat_modes(client):
    ids = sample_ids()
    base = {"reference": ids[0], "other": ids[1], "size": 128, "t": 0.45, "vmax": 0.025}
    images = []
    for variant in [
        {"heatmap": False, "texture": False},
        {
            "metric": "identity",
            "smoothing": 2,
            "palette": "custom",
            "low": "#1155aa",
            "mid": "#ffdd22",
            "high": "#ee4444",
            "inverse": True,
        },
        {
            "metric": "normal",
            "vmin": 0.001,
            "outsideOpacity": 0.15,
            "onlyAbove": True,
            "yaw": 35,
            "pitch": 15,
            "zoom": 1.2,
            "wireframe": True,
        },
    ]:
        response = client.get(
            "/api/photos/" + ids[0] + "/preview", params=base | variant
        )
        assert response.status_code == 200, response.text
        image = Image.open(io.BytesIO(response.content))
        assert image.size == (128, 128) and np.asarray(image).std() > 4
        images.append(response.content)
    assert len(set(images)) == 3


def test_manual_pose_date_override_is_saved_without_reinference(
    client, monkeypatch, tmp_path
):
    import shutil
    from server.config import classify

    original_root = storage.ROOT
    original = next(p for p in storage.library() if p["status"] == "ready")
    original_key = storage.key_for(original)
    dest = tmp_path / "cache" / original["id"]
    dest.mkdir(parents=True)
    source = original_root / "cache" / original["id"]
    for name in ("meta.json", "features-" + original_key + ".npz"):
        shutil.copyfile(source / name, dest / name)
    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(storage, "DB", tmp_path / "data/library.json")
    storage.write_db({"photos": [original], "demo": True})
    response = client.patch(
        "/api/photos/" + original["id"],
        json={
            "date": "2003-10-16",
            "angle_override": {"yaw": 45, "pitch": 0, "roll": 0},
        },
    )
    assert response.status_code == 200
    changed = response.json()
    assert changed["date"] == "2003-10-16" and changed["angles"]["yaw"] == 45
    assert changed["pose"] == classify(changed["angles"])
    assert storage.key_for(next(p for p in storage.read_db()["photos"] if p["id"] == original["id"])) == original_key
    before = storage.DB.read_bytes()
    assert (
        client.patch(
            "/api/photos/" + original["id"], json={"angle_override": {"yaw": 999}}
        ).status_code
        == 400
    )
    assert storage.DB.read_bytes() == before
    reset = client.patch(
        "/api/photos/" + original["id"], json={"angle_override": None}
    ).json()
    assert reset["angles"] == reset["meta"]["angles"]
