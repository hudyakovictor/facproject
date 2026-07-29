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


def test_calibration_match_by_explicit_angles(client: TestClient) -> None:
    response = client.get("/api/v1/calibration/match", params={"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "pose_bin": "frontal"})
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] > 0
    assert len(body["candidates"]) <= 5
    assert all(c["pose_bin"] == "frontal" for c in body["candidates"])
    # Results must be ranked by ascending angle distance.
    distances = [c["angle_distance"] for c in body["candidates"]]
    assert distances == sorted(distances)


def test_calibration_match_by_photo_id(client: TestClient) -> None:
    photos = client.get("/api/v1/photos").json()["photos"]
    photo_id = photos[0]["id"]
    response = client.get("/api/v1/calibration/match", params={"photo_id": photo_id})
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] > 0


def test_calibration_match_requires_angles_or_photo_id(client: TestClient) -> None:
    response = client.get("/api/v1/calibration/match")
    assert response.status_code == 400


def test_calibration_match_unknown_photo_404(client: TestClient) -> None:
    response = client.get("/api/v1/calibration/match", params={"photo_id": "NOPE"})
    assert response.status_code == 404


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
    # Unique content per test run avoids cross-run collisions with content
    # under runs/api_uploads/ (the endpoint intentionally dedups by content
    # hash, not by test-run identity — see server.py upload_photo()).
    import time
    unique_content = f"unique content for dedup test {time.time_ns()}".encode()
    files = {"file": ("1999_08_09.jpg", unique_content, "image/jpeg")}
    first = client.post("/api/v1/photos/upload", files=files)
    assert first.status_code == 200
    assert first.json()["stored"] is True

    second = client.post("/api/v1/photos/upload", files=files)
    assert second.status_code == 200
    assert second.json()["stored"] is False
    assert second.json()["photo_id"] == first.json()["photo_id"]



def test_extract_runner_blocks_when_model_weights_absent(tmp_path: Path) -> None:
    """P1.9 (DEV_FIX_TZ 2.9): тест проверяет ПОВЕДЕНИЕ, а не окружение.

    Прежняя версия ходила через HTTP и ожидала `blocked`, неявно полагаясь на
    отсутствие весов 3DDFA_V3 у разработчика. На машине, где все пять весов
    присутствуют, задание корректно уходило в `running`, и тест падал —
    сигнализируя о состоянии окружения, а не о дефекте кода.

    Здесь `project_root` — заведомо пустой tmp-каталог без `assets/`, поэтому
    результат детерминирован в любом окружении: extract обязан отказаться
    работать и назвать причину.
    """
    from app6.api.jobs import Job, _JobBlocked, make_extract_runner

    input_dir = tmp_path / "photos"
    input_dir.mkdir()
    (input_dir / "1999_08_09.jpg").write_bytes(b"not-a-real-jpeg-but-a-listed-input")

    runner = make_extract_runner(
        input_dir=input_dir,
        output_dir=tmp_path / "out",
        project_root=tmp_path / "empty_project_root",
    )
    with pytest.raises(_JobBlocked) as excinfo:
        runner(Job(id="test", kind="extract"))
    assert "веса модели" in str(excinfo.value) or "Python-пакеты" in str(excinfo.value)


def test_extract_runner_blocks_on_empty_input_directory(tmp_path: Path) -> None:
    """P3.14 (DEV_FIX_TZ): пустой вход — `blocked`, а не «успешно 0 фото».

    Проверяется только в окружении, где веса присутствуют: иначе сработает
    более ранний гейт по весам, и тест ничего не докажет.
    """
    from app6.api.jobs import Job, _JobBlocked, _check_stage1_dependencies, make_extract_runner

    project_root = Path(__file__).resolve().parents[3]
    required = ["face_model.npy", "net_recon.pth", "large_base_net.pth",
                "retinaface_resnet50_2020-07-20_old_torch.pth", "similarity_Lm3D_all.mat"]
    assets = project_root / "assets"
    if _check_stage1_dependencies() or any(not (assets / w).is_file() for w in required):
        pytest.skip("веса/зависимости Stage 1 отсутствуют — сработает гейт по весам, не по пустому входу")

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    runner = make_extract_runner(input_dir=empty_dir, output_dir=tmp_path / "out",
                                project_root=project_root)
    with pytest.raises(_JobBlocked) as excinfo:
        runner(Job(id="test", kind="extract"))
    assert "нет входных изображений" in str(excinfo.value)


def test_extract_job_via_api_reaches_terminal_status(client: TestClient, tmp_path: Path) -> None:
    """Контракт HTTP-слоя: задание обязано дойти до терминального статуса и,
    если оно не завершилось успешно, объяснить причину. Конкретный исход
    (`blocked` при отсутствии весов либо `complete`) зависит от окружения и
    здесь намеренно не фиксируется — за это отвечают два теста выше."""
    (tmp_path / "1999_08_09.jpg").write_bytes(b"placeholder")
    response = client.post("/api/v1/jobs", json={"kind": "extract", "input_dir": str(tmp_path)})
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    import time
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    for _ in range(100):
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["status"] in ("blocked", "failed", "complete", "cancelled"):
            break
        time.sleep(0.05)
    assert job["status"] in ("blocked", "failed", "complete", "cancelled")
    if job["status"] in ("blocked", "failed"):
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


def test_full_mesh_endpoint_returns_real_bfm_topology(client: TestClient) -> None:
    photos = client.get("/api/v1/photos").json()["photos"]
    photo_id = photos[0]["id"]
    response = client.get(f"/api/v1/photos/{photo_id}/mesh")
    assert response.status_code == 200
    body = response.json()
    assert len(body["vertices"]) == 35709
    assert len(body["triangles"]) == 70789
    assert len(body["primary_zone_ids"]) == 20
    assert body["primary_zone_ids"][0] == "A01"


def test_large_mesh_responses_are_gzip_compressed(client: TestClient) -> None:
    """3.7 MB JSON per full mesh must be compressed, or 3D views are needlessly heavy."""
    photos = client.get("/api/v1/photos").json()["photos"]
    photo_id = photos[0]["id"]
    response = client.get(f"/api/v1/photos/{photo_id}/mesh", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"


def test_full_mesh_endpoint_404_for_unknown_photo(client: TestClient) -> None:
    response = client.get("/api/v1/photos/NOT_REAL/mesh")
    assert response.status_code == 404


def test_compare_full_mesh_returns_real_topology_and_residuals(client: TestClient) -> None:
    photos = client.get("/api/v1/photos").json()["photos"]
    era1 = next(p for p in photos if p["era"] == "DEMO_SEGMENT_1")
    era3 = next(p for p in photos if p["era"] == "DEMO_SEGMENT_3")
    response = client.post("/api/v1/compare/full_mesh", json={"photo_a": era1["id"], "photo_b": era3["id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["vertex_count"] == 35709
    assert body["triangle_count"] == 70789
    assert len(body["residuals"]) == 35709
    assert len(body["vertices_b_aligned"]) == 35709
    assert body["residual_stats"]["max"] > 0
    assert body["not_a_verdict"] is True



def test_compare_full_mesh_unknown_photo_404(client: TestClient) -> None:
    response = client.post("/api/v1/compare/full_mesh", json={"photo_a": "NOPE", "photo_b": "ALSO_NOPE"})
    assert response.status_code == 404


def test_photo_detail_reports_full_mesh_availability(client: TestClient) -> None:
    photos = client.get("/api/v1/photos").json()["photos"]
    response = client.get(f"/api/v1/photos/{photos[0]['id']}")
    assert "full_mesh_available" in response.json()



def test_zones_catalog_served_from_atlas(client: TestClient) -> None:
    response = client.get("/api/v1/zones/catalog")
    assert response.status_code == 200
    body = response.json()
    assert body["zone_count"] == 40
    names = {z["name"] for z in body["zones"]}
    assert "forehead_center" in names
    # Веки/губы всегда исключены сегментацией — мягкие ткани, зависят от мимики.
    lip = next(z for z in body["zones"] if z["name"] == "upper_lip")
    assert lip["excluded_by_segmentation"] is True


def test_skin_zones_refuses_to_fake_data_in_demo_mode(client: TestClient) -> None:
    """В demo-режиме реального анализа кожи нет — эндпоинт обязан отказать.

    Это защита от главного класса дефектов интерфейса: показать синтетическое
    число как измерение кожи (`app6/AGENTS.md`).
    """
    photos = client.get("/api/v1/photos").json()["photos"]
    response = client.get(f"/api/v1/photos/{photos[0]['id']}/skin_zones")
    assert response.status_code == 409
    assert "Stage 1" in response.json()["detail"]


def test_photo_image_rejects_unknown_kind(client: TestClient) -> None:
    response = client.get("/api/v1/photos/whatever/image?kind=../../etc/passwd")
    assert response.status_code == 400
    assert "unknown image kind" in response.json()["detail"]


def test_photo_image_refuses_demo_mode_instead_of_serving_a_stub(client: TestClient) -> None:
    """В demo-режиме исходных фото не существует — нужен явный отказ.

    Заглушка вместо кадра в forensic-интерфейсе недопустима: её можно принять
    за реальное изображение из архива.
    """
    response = client.get("/api/v1/photos/any/image?kind=original")
    assert response.status_code == 409
    assert "Stage 1" in response.json()["detail"]


def test_compare_exposes_per_point_data_for_landmark_analysis(client: TestClient) -> None:
    """Каждая точка отдаётся с позицией A, выровненной B и знаковым смещением.

    Без `bx/by/bz` невозможен морфинг A→B на фронтенде, без `dx/dy/dz` — показ
    направления ухода точки.
    """
    photos = [p for p in client.get("/api/v1/photos").json()["photos"] if p["bucket"] == "frontal"]
    body = client.post("/api/v1/compare",
                       json={"photo_a": photos[0]["id"], "photo_b": photos[12]["id"]}).json()
    assert body["status"] == "measured"
    points = body["heatmap_points"]
    assert body["landmark_count"] == len(points)

    measured = [p for p in points if p["visible"]]
    assert measured, "нет ни одной измеренной точки"
    sample = measured[0]
    for key in ("x", "y", "z", "bx", "by", "bz", "dx", "dy", "dz", "residual", "zone"):
        assert key in sample, f"поле {key} отсутствует"

    # Смещение согласовано с координатами: dx == bx - x.
    assert sample["dx"] == pytest.approx(sample["bx"] - sample["x"], abs=1e-6)
    # Зоны — координатные, а не анатомические (контракт Stage 2).
    assert "НЕ анатомические" in body["zone_policy"]


def test_compare_keeps_invisible_points_as_no_data(client: TestClient) -> None:
    """Невидимая точка сохраняется с residual=None, а не выбрасывается.

    Молча удалённая точка на тепловой карте читается как «совпала».
    """
    photos = [p for p in client.get("/api/v1/photos").json()["photos"] if p["bucket"] == "frontal"]
    body = client.post("/api/v1/compare",
                       json={"photo_a": photos[0]["id"], "photo_b": photos[12]["id"]}).json()
    for point in body["heatmap_points"]:
        if not point["visible"]:
            assert point["residual"] is None
            assert point["x"] is None


def test_settings_merge_adds_new_sections_to_a_stored_file(tmp_path: Path) -> None:
    """Файл настроек от прежней версии не должен скрывать новые секции.

    Без слияния с умолчаниями `landmark_shift` приходил бы как None, и пороги
    классификации молча исчезали бы из интерфейса.
    """
    import json as _json

    from app6.api.settings import DEFAULT_SETTINGS, load_settings

    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "api_settings.json").write_text(
        _json.dumps({"heatmap": {"max_residual_reference": 0.99}}), encoding="utf-8")

    merged = load_settings(tmp_path)
    assert merged["heatmap"]["max_residual_reference"] == 0.99      # пользовательское сохранено
    assert merged["landmark_shift"] == DEFAULT_SETTINGS["landmark_shift"]  # новое добавлено
    assert "thresholds" in merged
