"""Регрессия для `app6/api`: контракт, не мок. Все проверки идут через реальный
FastAPI `TestClient` без подмены бизнес-логики.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.pop("DEEPUTIN_STAGE1_ROOT", None)
os.environ.pop("DEEPUTIN_STAGE2_ROOT", None)

from app6.api.server import app  # noqa: E402 - env must be cleared before import-time caching


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["not_a_verdict"] is True


def test_timeline_is_demo_and_honestly_labeled(client: TestClient) -> None:
    response = client.get("/api/v1/timeline")
    assert response.status_code == 200
    body = response.json()
    assert body["source_mode"] == "demo"
    assert body["not_a_verdict"] is True
    assert len(body["photos"]) > 0
    poses = {p["bucket"] for p in body["photos"]}
    assert poses == {
        "left_profile", "left_deep", "left_mid", "left_light", "frontal",
        "right_light", "right_mid", "right_deep", "right_profile",
    }


def test_timeline_photos_have_required_contract_fields(client: TestClient) -> None:
    """Контракт `ui/API_CONTRACT.md`: id, date, t, era, bucket, quality, boneScore, p0, p1, p2."""
    body = client.get("/api/v1/timeline").json()
    required = {"id", "date", "t", "era", "bucket", "quality", "boneScore", "p0", "p1", "p2"}
    for row in body["photos"][:20]:
        assert required.issubset(row.keys())


def test_photos_list_matches_timeline_count(client: TestClient) -> None:
    timeline = client.get("/api/v1/timeline").json()
    photos = client.get("/api/v1/photos").json()
    assert photos["source_mode"] == "demo"
    assert photos["count"] == len(timeline["photos"])


def test_get_single_photo_has_landmarks(client: TestClient) -> None:
    photos = client.get("/api/v1/photos").json()["photos"]
    photo_id = photos[0]["id"]
    response = client.get(f"/api/v1/photos/{photo_id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["landmarks_106"]) == 106
    assert len(body["landmarks_134"]) == 134


def test_get_unknown_photo_404(client: TestClient) -> None:
    assert client.get("/api/v1/photos/NOT_A_REAL_ID").status_code == 404


def test_compare_same_pose_bin_is_measured(client: TestClient) -> None:
    photos = client.get("/api/v1/photos").json()["photos"]
    frontal = [p for p in photos if p["bucket"] == "frontal"][:2]
    response = client.post("/api/v1/compare", json={"photo_a": frontal[0]["id"], "photo_b": frontal[1]["id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "measured"
    assert body["not_a_verdict"] is True
    assert len(body["heatmap_points"]) > 0
    assert "ldm134_rmse" in body["metrics"]


def test_compare_cross_pose_is_rejected_not_faked(client: TestClient) -> None:
    photos = client.get("/api/v1/photos").json()["photos"]
    frontal = next(p for p in photos if p["bucket"] == "frontal")
    profile = next(p for p in photos if p["bucket"] == "left_profile")
    response = client.post("/api/v1/compare", json={"photo_a": frontal["id"], "photo_b": profile["id"]})
    body = response.json()
    assert body["status"] == "pose_mismatch"
    assert body["metrics"] == {}
    assert body["heatmap_points"] == []


def test_compare_unknown_photo_404(client: TestClient) -> None:
    response = client.post("/api/v1/compare", json={"photo_a": "NOPE", "photo_b": "ALSO_NOPE"})
    assert response.status_code == 404


def test_compare_upload_returns_honest_not_implemented(client: TestClient) -> None:
    """Загруженное фото без Stage 1 не должно притворяться сравненным."""
    response = client.post(
        "/api/v1/compare/upload",
        params={"photo_id": "DEMO_00000"},
        files={"file": ("1999_01_01.jpg", b"fake bytes", "image/jpeg")},
    )
    assert response.status_code == 501


def test_calibration_health_reflects_real_dataset(client: TestClient) -> None:
    response = client.get("/api/v1/calibration/health")
    assert response.status_code == 200
    body = response.json()
    assert body["total_records"] == 943
    assert body["total_persons"] == 7
    assert set(body["buckets"].keys()) == {
        "left_profile", "left_deep", "left_mid", "left_light", "frontal",
        "right_light", "right_mid", "right_deep", "right_profile",
    }


def test_system_health_reports_missing_weights_honestly(client: TestClient) -> None:
    response = client.get("/api/v1/system/health")
    body = response.json()
    assert "model_assets" in body
    assert isinstance(body["model_assets"]["missing"], list)


def test_settings_roundtrip(client: TestClient) -> None:
    default = client.get("/api/v1/settings").json()
    updated = dict(default)
    updated["heatmap"] = {**default["heatmap"], "stop_blue_cyan": 0.33}
    put_response = client.put("/api/v1/settings", json=updated)
    assert put_response.status_code == 200
    assert put_response.json()["heatmap"]["stop_blue_cyan"] == 0.33

    reset_response = client.post("/api/v1/settings/reset")
    assert reset_response.json()["heatmap"]["stop_blue_cyan"] == 0.25


def test_upload_rejects_invalid_filename(client: TestClient, tmp_path: Path) -> None:
    response = client.post(
        "/api/v1/photos/upload",
        files={"file": ("not_a_date.jpg", b"content", "image/jpeg")},
    )
    assert response.status_code == 400


def test_upload_accepts_valid_filename_and_dedups(client: TestClient) -> None:
    files = {"file": ("1999_08_09.jpg", b"unique content for dedup test", "image/jpeg")}
    first = client.post("/api/v1/photos/upload", files=files)
    assert first.status_code == 200
    assert first.json()["stored"] is True

    second = client.post("/api/v1/photos/upload", files=files)
    assert second.status_code == 200
    assert second.json()["stored"] is False
    assert second.json()["photo_id"] == first.json()["photo_id"]


def test_extract_job_reports_blocked_without_weights(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/v1/jobs", json={"kind": "extract", "input_dir": str(tmp_path)})
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    import time
    for _ in range(50):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("blocked", "failed", "complete"):
            break
        time.sleep(0.05)
    assert job["status"] == "blocked"
    assert job["error"]


def test_unknown_job_kind_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/jobs", json={"kind": "not_a_real_kind"})
    assert response.status_code == 400


def test_recompute_without_stage1_root_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/jobs", json={"kind": "recompute_metrics"})
    assert response.status_code == 400


def test_data_clear_never_touches_source_photos(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/v1/data/clear")
    assert response.status_code == 200
    assert "исходные фото не удалены" in response.json()["note"]


def test_delete_photo_without_stage1_root_rejected(client: TestClient) -> None:
    response = client.delete("/api/v1/photos/DEMO_00000")
    assert response.status_code == 409
