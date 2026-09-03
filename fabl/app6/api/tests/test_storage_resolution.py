"""Регрессии выбора реальных артефактов Stage 1/2 из storage."""
from __future__ import annotations

import json
from pathlib import Path

from app6.api import server


def _stage2(path: Path, *, status: str = "complete", created_at: str = "2026-08-16T00:00:00Z") -> None:
    path.mkdir(parents=True)
    (path / "analysis_manifest.json").write_text(
        json.dumps({"status": status, "created_at_utc": created_at}), encoding="utf-8"
    )
    (path / "pair_metrics.csv").write_text("photo_a,photo_b\n", encoding="utf-8")


def test_storage_root_prefers_canonical_external_storage(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DEEPUTIN_STORAGE_ROOT", raising=False)
    monkeypatch.setattr(server, "_CANONICAL_STORAGE_ROOT", tmp_path / "canonical")
    server._CANONICAL_STORAGE_ROOT.mkdir()
    assert server._storage_root() == server._CANONICAL_STORAGE_ROOT.resolve()


def test_stage1_is_resolved_from_storage_when_env_is_absent(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DEEPUTIN_STAGE1_ROOT", raising=False)
    monkeypatch.setattr(server, "_CANONICAL_STORAGE_ROOT", tmp_path)
    stage1 = tmp_path / "stage1"
    stage1.mkdir()
    (stage1 / "main_timeline.csv").write_text("photo_id,date\n", encoding="utf-8")
    assert server._stage1_root() == stage1


def test_stage2_ignores_incomplete_and_selects_newest_complete(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DEEPUTIN_STAGE2_ROOT", raising=False)
    monkeypatch.setattr(server, "_CANONICAL_STORAGE_ROOT", tmp_path)
    _stage2(tmp_path / "stage2_incomplete", status="running", created_at="2026-08-17T00:00:00Z")
    _stage2(tmp_path / "stage2_old", created_at="2026-08-01T00:00:00Z")
    newest = tmp_path / "stage2_resumable_20260816"
    _stage2(newest, created_at="2026-08-16T02:15:22Z")
    assert server._stage2_root() == newest


def test_explicit_stage2_root_must_be_complete(monkeypatch, tmp_path: Path):
    incomplete = tmp_path / "stage2"
    _stage2(incomplete, status="running")
    monkeypatch.setenv("DEEPUTIN_STAGE2_ROOT", str(incomplete))
    assert server._stage2_root() is None


def test_stage3_is_resolved_from_storage_when_env_is_absent(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DEEPUTIN_STAGE3_ROOT", raising=False)
    monkeypatch.setattr(server, "_CANONICAL_STORAGE_ROOT", tmp_path)
    stage3 = tmp_path / "stage3"
    stage3.mkdir()
    (stage3 / "report_data.json").write_text("{}", encoding="utf-8")
    assert server._stage3_root() == stage3


def test_explicit_stage3_root_without_report_is_not_ready(monkeypatch, tmp_path: Path):
    missing = tmp_path / "stage3"
    missing.mkdir()
    monkeypatch.setenv("DEEPUTIN_STAGE3_ROOT", str(missing))
    assert server._stage3_root() is None


def test_health_exposes_selected_run(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DEEPUTIN_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("DEEPUTIN_STAGE1_ROOT", raising=False)
    monkeypatch.delenv("DEEPUTIN_STAGE2_ROOT", raising=False)
    monkeypatch.setattr(server, "_CANONICAL_STORAGE_ROOT", tmp_path)
    (tmp_path / "stage1").mkdir()
    (tmp_path / "stage1" / "main_timeline.csv").write_text("photo_id,date\n", encoding="utf-8")
    _stage2(tmp_path / "stage2", created_at="2026-08-16T02:15:22Z")
    (tmp_path / "stage3").mkdir()
    (tmp_path / "stage3" / "report_data.json").write_text("{}", encoding="utf-8")
    payload = server.health()
    assert payload["source_mode"] == "research"
    assert payload["stage1_ready"] is True
    assert payload["stage2_ready"] is True
    assert payload["stage2_status"] == "complete"
    assert payload["stage3_ready"] is True
    assert payload["stage3_root"] == str(tmp_path / "stage3")
