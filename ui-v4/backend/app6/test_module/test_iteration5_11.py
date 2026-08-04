"""Iteration 05–11 API tests: Run Manager, Report Manager, Morphing,
Landmark Comparison, batch pairs, Calibration Workspace.

Uses a compact synthetic Stage 1 + calibration fixture (no model weights
required). The fixture generator lives in app6/scripts/make_synthetic_stage1.py
and produces artifacts with exactly the same names/contracts as the real
Stage 1 output.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FIXTURE_ROOT = Path(os.environ.get("DEEPUTIN_TEST_FIXTURE", "/tmp/deeputin_test_fixture"))


@pytest.fixture(scope="module")
def fixture() -> Path:
    """Build (once) a compact synthetic Stage 1 + calibration."""
    if (FIXTURE_ROOT / "storage" / "stage1" / "main_timeline.csv").is_file():
        return FIXTURE_ROOT
    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    script = ROOT / "app6" / "scripts" / "make_synthetic_stage1.py"
    subprocess.run(
        [sys.executable, str(script), "--root", str(FIXTURE_ROOT), "--main-photos", "45", "--cal-frames", "126"],
        check=True,
        capture_output=True,
    )
    return FIXTURE_ROOT


@pytest.fixture()
def client(fixture: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEEPUTIN_STORAGE_ROOT", str(fixture / "storage"))
    monkeypatch.setenv("DEEPUTIN_CALIBRATION_ROOT", str(fixture / "calibration"))
    from fastapi.testclient import TestClient
    from app6.api.server import app
    with TestClient(app) as test_client:
        yield test_client


def _first_bin_photos(client, pose: str = "frontal") -> list[dict]:
    payload = client.get("/api/v1/morphing/bins").json()
    bin_rows = next(item for item in payload["pose_bins"] if item["pose"] == pose)
    assert bin_rows["photos"], f"no photos in bin {pose}"
    return bin_rows["photos"]


# ---------------------------------------------------------------------------
# Iteration 09 — Morphing
# ---------------------------------------------------------------------------
class TestMorphingApi:
    def test_morphing_bins_nine_poses(self, client):
        payload = client.get("/api/v1/morphing/bins")
        assert payload.status_code == 200
        data = payload.json()
        assert len(data["pose_bins"]) == 9
        for bin_rows in data["pose_bins"]:
            assert "camera" in bin_rows
            assert "photos" in bin_rows
            assert all(photo["id"] and photo["date"] for photo in bin_rows["photos"])
            dates = [photo["date"] for photo in bin_rows["photos"]]
            assert dates == sorted(dates), "photos must be in chronology order"

    def test_morphing_photo_payload(self, client):
        photos = _first_bin_photos(client)
        payload = client.get(f"/api/v1/morphing/photo/{photos[0]['id']}")
        assert payload.status_code == 200
        data = payload.json()
        assert data["vertex_count"] > 0
        assert data["triangle_count"] > 0
        assert len(data["vertices"]) == data["vertex_count"] * 3
        assert len(data["triangles"]) == data["triangle_count"] * 3
        assert data["has_uv"]
        assert data["texture_url"].endswith("/image?kind=uv_texture")
        assert "canonical_pose_deg" in data

    def test_morphing_photo_shared_topology(self, client):
        photos = _first_bin_photos(client)
        a = client.get(f"/api/v1/morphing/photo/{photos[0]['id']}").json()
        b = client.get(f"/api/v1/morphing/photo/{photos[1]['id']}").json()
        # identical topology ⇒ morphing is well-defined
        assert a["triangle_count"] == b["triangle_count"]
        assert a["vertex_count"] == b["vertex_count"]
        assert a["triangles"] == b["triangles"]

    def test_morphing_photo_unknown_id(self, client):
        payload = client.get("/api/v1/morphing/photo/does_not_exist")
        assert payload.status_code in (404, 422)

    def test_morphing_diff_heatmap(self, client):
        photos = _first_bin_photos(client)
        payload = client.get(f"/api/v1/morphing/diff/{photos[0]['id']}/{photos[1]['id']}")
        assert payload.status_code == 200, payload.text
        data = payload.json()
        assert data["vertex_count"] > 0
        assert len(data["magnitudes"]) == data["vertex_count"]
        assert len(data["vertices_a"]) == data["vertex_count"] * 3
        assert len(data["vertices_b"]) == data["vertex_count"] * 3
        assert all(value >= 0 for value in data["magnitudes"])
        stats = data["stats"]
        assert 0 <= stats["min"] <= stats["median"] <= stats["p95"] <= stats["max"]
        # calibration context: when a Stage 2 run exists, per-vertex p95 map present
        if data["calibration"]["available"]:
            assert len(data["calibration"]["per_vertex_p95"]) == data["vertex_count"]

    def test_morphing_diff_identical_photos(self, client):
        photos = _first_bin_photos(client)
        payload = client.get(f"/api/v1/morphing/diff/{photos[0]['id']}/{photos[0]['id']}")
        assert payload.status_code == 200
        data = payload.json()
        # same photo → alignment is identity, displacement ≈ 0
        assert data["stats"]["max"] < 0.02


# ---------------------------------------------------------------------------
# Iteration 08 — Landmark comparison
# ---------------------------------------------------------------------------
class TestLandmarkCompareApi:
    def test_compare_106_and_134(self, client):
        photos = _first_bin_photos(client)
        for count in (106, 134):
            payload = client.get(f"/api/v1/landmarks/compare/{photos[0]['id']}/{photos[1]['id']}?count={count}&space=chronology")
            assert payload.status_code == 200
            data = payload.json()
            assert len(data["points"]) == count
            assert data["summary"]["rms"] is not None
            point = data["points"][0]
            for key in ("x_a", "y_a", "z_a", "x_b", "y_b", "z_b", "dx", "dy", "dz", "magnitude"):
                assert key in point
            assert "region" in point

    def test_compare_bad_count(self, client):
        photos = _first_bin_photos(client)
        payload = client.get(f"/api/v1/landmarks/compare/{photos[0]['id']}/{photos[1]['id']}?count=99")
        assert payload.status_code == 422

    def test_batch_pairs(self, client):
        photos = _first_bin_photos(client)
        payload = client.post("/api/v1/pairs/batch", json={"pairs": [[photos[0]["id"], photos[1]["id"]]], "count": 106})
        assert payload.status_code == 200
        data = payload.json()
        assert data["result_count"] == 1
        assert data["results"][0]["rms"] is not None
        assert data["results"][0]["count"] == 106

    def test_batch_pairs_cap(self, client):
        photos = _first_bin_photos(client)
        pairs = [[photos[0]["id"], photos[1]["id"]] for _ in range(500)]
        payload = client.post("/api/v1/pairs/batch", json={"pairs": pairs})
        assert payload.status_code == 400


# ---------------------------------------------------------------------------
# Iteration 10 — Calibration workspace
# ---------------------------------------------------------------------------
class TestCalibrationWorkspaceApi:
    def test_workspace_dashboard(self, client):
        payload = client.get("/api/v1/calibration/workspace")
        assert payload.status_code == 200
        data = payload.json()
        assert data["status"] == "ready"
        assert data["person_count"] == 7
        assert data["covered_bin_count"] == 9
        assert data["total_frames"] > 0
        assert len(data["pose_bins"]) == 9

    def test_thresholds_before_stage2_unavailable(self, client, fixture):
        # ensure no stage2 runs exist for this check
        runs = fixture / "storage" / "stage2" / "runs"
        if runs.exists():
            shutil.rmtree(runs)
        payload = client.get("/api/v1/calibration/thresholds")
        assert payload.status_code == 200
        data = payload.json()
        assert data["calibrated"] is False


# ---------------------------------------------------------------------------
# Iteration 05 — Run Manager (full lifecycle)
# ---------------------------------------------------------------------------
class TestRunManagerApi:
    def test_preflight(self, client):
        payload = client.post("/api/v1/runs/preflight", json={})
        assert payload.status_code == 200
        data = payload.json()
        assert data["ready"] is True
        assert data["stage1"]["record_count"] > 0
        assert data["calibration"]["person_count"] == 7
        assert data["pairs"]["total_estimate"] > 0
        assert data["pairs"]["adjacent"] >= 9  # one adjacent pair per bin minimum

    def test_run_lifecycle_stage2b_report(self, client):
        """Full loop: start → poll → complete → stage2b → reports → lint."""
        payload = client.post("/api/v1/runs/stage2", json={"label": "pytest run"})
        assert payload.status_code == 200, payload.text
        run = payload.json()
        run_id = run["run_id"]
        assert run["status"] in ("queued", "running")

        deadline = time.time() + 240
        while time.time() < deadline:
            detail = client.get(f"/api/v1/runs/{run_id}").json()
            if detail["status"] in ("complete", "failed", "cancelled"):
                break
            time.sleep(2)
        assert detail["status"] == "complete", detail.get("error")
        assert detail["valid"] is True
        assert detail["pair_count"] is not None and detail["pair_count"] > 0
        assert detail["record_count"] == 45
        assert detail["included_count"] == 45
        assert any("analysis_manifest.json" == name for name in detail["artifacts"])

        # stage2b (output outside the run tree)
        payload = client.post(f"/api/v1/runs/{run_id}/stage2b", json={})
        assert payload.status_code == 200, payload.text
        assert payload.json()["stage2b_output"]

        # second stage2b must be refused (no overwrite)
        payload = client.post(f"/api/v1/runs/{run_id}/stage2b", json={})
        assert payload.status_code == 409

        # calibrated thresholds now available (bins with enough calibration
        # support appear; the compact fixture may not cover all 9×2 combos)
        thresholds = client.get("/api/v1/calibration/thresholds").json()
        assert thresholds["calibrated"] is True
        assert len(thresholds["references"]) >= 9
        for reference in thresholds["references"]:
            assert reference["scalar"]["p95"] is not None

        # reports: technical + public (lint)
        tech = client.post("/api/v1/reports", json={"run_id": run_id, "mode": "technical"})
        assert tech.status_code == 200, tech.text
        report = tech.json()
        assert report["valid"] is True
        assert report["mode"] == "technical"
        assert "pairs.csv" in report["exports"]
        assert "report.json" in report["exports"]

        public = client.post("/api/v1/reports", json={"run_id": run_id, "mode": "public"})
        assert public.status_code == 200, public.text
        assert public.json()["public_lint"]["status"] == "pass"

        # second report from the same run is allowed (multi-report per run)
        internal = client.post("/api/v1/reports", json={"run_id": run_id, "mode": "internal"})
        assert internal.status_code == 200

        # report files downloadable
        html = client.get(f"/api/v1/reports/{report['report_id']}/file/index.html")
        assert html.status_code == 200
        assert b"<html" in html.content[:2000].lower() or b"<!doctype" in html.content[:2000].lower()
        pairs = client.get(f"/api/v1/reports/{report['report_id']}/file/exports/pairs.csv")
        assert pairs.status_code == 200
        assert b"photo_a" in pairs.content[:2000]

        # regeneration re-renders without re-running Stage 2
        regen = client.post(f"/api/v1/reports/{report['report_id']}/regenerate")
        assert regen.status_code == 200, regen.text

        # runs list contains the run; reports list contains 3
        runs = client.get("/api/v1/runs").json()["runs"]
        assert any(item["run_id"] == run_id for item in runs)
        reports = client.get("/api/v1/reports").json()["reports"]
        assert len(reports) >= 3

    def test_run_cancel(self, client):
        payload = client.post("/api/v1/runs/stage2", json={"label": "cancel me"})
        assert payload.status_code == 200
        run_id = payload.json()["run_id"]
        cancelled = client.post(f"/api/v1/runs/{run_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] in ("cancelling", "cancelled")
        # archived state after completion is covered by lifecycle; cancel must not crash listing
        assert client.get("/api/v1/runs").status_code == 200


# ---------------------------------------------------------------------------
# Iteration 05 — selection-aware run (profile filtering)
# ---------------------------------------------------------------------------
class TestRunManagerSelection:
    def test_preflight_with_profile(self, client):
        created = client.post("/api/v1/profiles", json={"name": "pytest profile"})
        assert created.status_code == 200, created.text
        profile_id = created.json()["id"]
        payload = client.post("/api/v1/runs/preflight", json={"profile_id": profile_id})
        assert payload.status_code == 200, payload.text
        data = payload.json()
        assert data["selection"]["profile_id"] == profile_id
        assert data["stage1"]["selected_count"] <= data["stage1"]["record_count"]


# ---------------------------------------------------------------------------
# Iteration 07b — Timeline findings layer
# ---------------------------------------------------------------------------
class TestTimelineFindings:
    def test_findings_payload(self, client):
        payload = client.get("/api/v1/timeline/findings")
        assert payload.status_code == 200, payload.text
        data = payload.json()
        assert data["schema"] == "deeputin-timeline-findings-v1.0"
        assert data["has_stage2"] is True
        assert data["run_id"]
        assert len(data["bins"]) == 9
        frontal = data["bins"]["frontal"]
        assert frontal["pairs"], "frontal bin must have adjacent pairs after the run"
        pair = frontal["pairs"][0]
        assert pair["a"] and pair["b"]
        assert "rmse" in pair["shape"]
        assert "status" in pair["shape"]
        assert "texture" in pair and "status" in pair["texture"]

    def test_findings_change_and_return_arrays(self, client):
        data = client.get("/api/v1/timeline/findings").json()
        for pose, bin_data in data["bins"].items():
            assert isinstance(bin_data["change_points"], list)
            assert isinstance(bin_data["returns"], list)
            assert isinstance(bin_data["zones"], list)

    def test_dense_zone_prune_suggestions(self):
        """Zone logic: dense cluster → prune suggestions with reasons."""
        from app6.api.timeline_findings import _dense_zones
        photos = []
        base = "2020-01-01"
        for i in range(8):
            photos.append({
                "id": f"dense_{i:02d}",
                "date": f"2020-01-{i + 1:02d}",
                "t": None,  # replaced below
                "bucket": "frontal",
                "quality": 0.9 - 0.05 * (i % 3),
                "yaw": 2.0 if i != 3 else 18.0,   # one extreme pose outlier
                "pitch": 0.0,
                "roll": 0.0,
                "near_duplicate_of": "dense_00" if i == 7 else "",
            })
        from datetime import datetime, timezone
        for photo in photos:
            parsed = datetime.fromisoformat(photo["date"]).replace(tzinfo=timezone.utc)
            photo["t"] = int(parsed.timestamp() * 1000)
        zones = _dense_zones(photos)
        assert len(zones) == 1
        zone = zones[0]
        assert zone["count"] == 8
        assert zone["remove"], "dense zone must suggest removals"
        ids = [entry["id"] for entry in zone["remove"]]
        # the extreme pose outlier and the duplicate are the strongest noise
        assert "dense_03" in ids or "dense_07" in ids
        for entry in zone["remove"]:
            assert entry["reasons"], "every suggestion must carry reasons"
        assert len(zone["keep"]) >= 3

    def test_findings_before_stage2(self, client, fixture):
        runs = fixture / "storage" / "stage2" / "runs"
        if runs.exists():
            import shutil as _shutil
            _shutil.rmtree(runs)
        payload = client.get("/api/v1/timeline/findings")
        assert payload.status_code == 200
        data = payload.json()
        assert data["has_stage2"] is False
        for pose, bin_data in data["bins"].items():
            assert bin_data["pairs"] == []
            # zones still computed from Stage 1 inventory (density is stage-1 data)
            assert isinstance(bin_data["zones"], list)


# ---------------------------------------------------------------------------
# Iteration 12 — Event log panel
# ---------------------------------------------------------------------------
class TestEventLog:
    def test_logs_endpoint_and_middleware(self, client):
        # provoke 404 → middleware must record a warn event
        client.get("/api/v1/photos/definitely_missing_photo")
        payload = client.get("/api/v1/logs")
        assert payload.status_code == 200
        data = payload.json()
        assert data["schema"] == "deeputin-event-log-v1.0"
        events = data["events"]
        assert events, "journal must contain the provoked 404"
        assert any(
            event.get("level") == "warn" and "definitely_missing_photo" in event.get("message", "")
            for event in events
        )

    def test_client_ingest_and_filters(self, client):
        payload = client.post("/api/v1/logs/client", json={"events": [
            {"level": "error", "source": "timeline", "message": "frontend boom", "detail": "detail x", "path": "/api/v1/timeline"},
            {"level": "warn", "source": "morphing", "message": "texture failed", "path": "/api/v1/morphing/photo/x"},
        ]})
        assert payload.status_code == 200
        assert payload.json()["received"] == 2

        all_events = client.get("/api/v1/logs").json()["events"]
        client_events = [event for event in all_events if event.get("origin") == "client"]
        assert len(client_events) >= 2
        assert any("frontend boom" in event["message"] for event in client_events)

        errors = client.get("/api/v1/logs?level=error").json()["events"]
        assert any("frontend boom" in event["message"] for event in errors)
        warn_morph = client.get("/api/v1/logs?source=morphing").json()["events"]
        assert warn_morph and warn_morph[0]["source"] == "morphing"

    def test_logs_summary(self, client):
        payload = client.get("/api/v1/logs/summary")
        assert payload.status_code == 200
        data = payload.json()
        assert "levels" in data and "sources" in data
        assert data["total"] > 0

    def test_logs_export(self, client):
        payload = client.get("/api/v1/logs/export")
        assert payload.status_code == 200
        assert "ndjson" in payload.headers.get("content-type", "")
        assert b"\n" in payload.content
        assert b"deeputin-event-log-v1.0" in payload.content

    def test_client_ingest_caps_and_validation(self, client):
        # too many events → capped, no crash
        many = [{"level": "info", "source": "load", "message": f"m{i}"} for i in range(250)]
        payload = client.post("/api/v1/logs/client", json={"events": many})
        assert payload.status_code == 200
        assert payload.json()["received"] <= 100
        # empty message → skipped
        payload = client.post("/api/v1/logs/client", json={"events": [{"level": "error", "source": "x", "message": ""}]})
        assert payload.status_code == 200
        assert payload.json()["received"] == 0
