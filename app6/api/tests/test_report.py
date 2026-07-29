"""Тесты API-слоя публичного отчёта Stage 3.

🚨 Эталонной фикстуры Stage 3 в репозитории нет: `app6/test_data/
S04_fdr_stress_A_p05_v00` — неполный вывод Stage 2 (нет `zone_metrics.csv`,
`change_points.json`, `analysis_validation.json`), и `Stage3Engine.run()` на
нём не запускается. Поэтому здесь проверяется именно слой чтения на
структуре, воспроизводящей формат `stage3.engine`, а не сам Stage 3.
Структура сверена с `Stage3Engine.run()` — см. ключи `data={...}`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app6.api.report import (
    REPORT_SECTIONS, WITHHELD_COLUMN_PREFIXES, load_report_section, load_report_summary,
    report_available,
)


def _write_report(root: Path, **overrides: Any) -> Path:
    """Минимальный `report_data.json` в формате `stage3.engine`."""
    data: dict[str, Any] = {
        "schema_version": "deeputin-stage3-v1.4",
        "analysis_manifest": {
            "schema_version": "deeputin-stage2-v1",
            "created_at_utc": "2026-07-29T00:00:00Z",
            "main_record_count": 520,
            "calibration_dataset_count": 7,
        },
        "summary": {
            "pair_count": 25, "zone_count": 9, "change_count": 2,
            "lead_pair_count": 1,
            "status_counts": {"within_noise": 20, "elevated_uncertain": 5},
            "pose_counts": {"frontal": 25},
        },
        "narrative": ["Исследование охватывает 520 фотографий."],
        "timelines": {"frontal": [{"date": "2001-02-10", "p95_point_z": 1.2}]},
        "motion_maps": [{"pair_id": f"p{i}", "points": []} for i in range(5)],
        "pairs": [
            {
                "pair_id": f"p{i}",
                "status": "within_noise",
                "measurement_status": "expression_dominated",
            }
            for i in range(10)
        ],
        "lead_pairs": [{"pair_id": "p0"}],
        "lead_registry": {"date_count": 3, "metric_count": 4},
        "change_points": [{"pair_id": "p1", "date": "2001-03-01"}],
        "zones": [{"zone": "Z01"}],
        "metric_catalog": {"registry_size": 13, "metrics": []},
        "methodology": {"stage1": "single inference"},
    }
    data.update(overrides)
    root.mkdir(parents=True, exist_ok=True)
    (root / "report_data.json").write_text(json.dumps(data), encoding="utf-8")
    return root


@pytest.fixture()
def report_root(tmp_path: Path) -> Path:
    return _write_report(tmp_path / "stage3")


# --- доступность ------------------------------------------------------------

def test_report_available(report_root: Path, tmp_path: Path) -> None:
    assert report_available(report_root) is True
    assert report_available(tmp_path / "absent") is False
    assert report_available(None) is False


def test_missing_report_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_report_summary(tmp_path)


def test_non_object_report_rejected(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "report_data.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_report_summary(tmp_path)


# --- обзор ------------------------------------------------------------------

def test_summary_exposes_versions(report_root: Path) -> None:
    payload = load_report_summary(report_root)
    assert payload["report_schema_version"] == "deeputin-stage3-v1.4"
    assert payload["stage2_schema_version"] == "deeputin-stage2-v1"
    assert payload["not_a_verdict"] is True


def test_summary_omits_heavy_sections(report_root: Path) -> None:
    """Обзор не должен тянуть 40 карт движения по 134 точки."""
    payload = load_report_summary(report_root)
    assert "pairs" not in payload
    assert "motion_maps" not in payload


def test_summary_lists_all_sections_with_size(report_root: Path) -> None:
    payload = load_report_summary(report_root)
    by_name = {s["name"]: s for s in payload["sections"]}
    assert set(by_name) == set(REPORT_SECTIONS)
    assert by_name["pairs"]["size"] == 10
    assert by_name["pairs"]["paged"] is True
    assert by_name["methodology"]["paged"] is False


def test_absent_section_marked_not_present(tmp_path: Path) -> None:
    """Отсутствующая секция перечисляется, а не пропадает молча."""
    root = _write_report(tmp_path / "s3")
    data = json.loads((root / "report_data.json").read_text(encoding="utf-8"))
    del data["change_points"]
    (root / "report_data.json").write_text(json.dumps(data), encoding="utf-8")

    payload = load_report_summary(root)
    entry = next(s for s in payload["sections"] if s["name"] == "change_points")
    assert entry["present"] is False
    assert entry["size"] is None


def test_summary_documents_status_semantics(report_root: Path) -> None:
    """Разная семантика `status` между Stage 2 и Stage 3 должна быть явной.

    `stage3.engine.public_pair_projection` подменяет `status` на
    `evidence_state`. Без пометки сравнение отчёта с таблицей пары дало бы
    ложный вывод о расхождении данных.
    """
    payload = load_report_summary(report_root)
    semantics = payload["status_semantics"]
    assert "evidence_state" in semantics["status"]
    assert "measurement_status" in semantics


def test_summary_documents_withheld_columns(report_root: Path) -> None:
    """Отсутствие texture_*/uv_* — политика публикации, а не потеря."""
    payload = load_report_summary(report_root)
    assert payload["withheld_column_prefixes"] == list(WITHHELD_COLUMN_PREFIXES)
    assert "texture" in payload["withheld_note"]


def test_validation_included_when_present(report_root: Path) -> None:
    (report_root / "report_validation.json").write_text(
        json.dumps({"status": "complete", "errors": []}), encoding="utf-8")
    payload = load_report_summary(report_root)
    assert payload["validation"]["status"] == "complete"


def test_validation_none_when_absent(report_root: Path) -> None:
    assert load_report_summary(report_root)["validation"] is None


def test_corrupt_validation_does_not_break_summary(report_root: Path) -> None:
    (report_root / "report_validation.json").write_text("{not json", encoding="utf-8")
    assert load_report_summary(report_root)["validation"] is None


# --- секции -----------------------------------------------------------------

def test_section_rejects_arbitrary_key(report_root: Path) -> None:
    with pytest.raises(KeyError):
        load_report_section(report_root, "../../etc/passwd")


def test_section_pagination(report_root: Path) -> None:
    page = load_report_section(report_root, "pairs", offset=0, limit=4)
    assert page["total"] == 10
    assert page["returned"] == 4
    assert page["paged"] is True

    tail = load_report_section(report_root, "pairs", offset=8, limit=4)
    assert tail["returned"] == 2


def test_section_offset_beyond_end_is_empty_not_error(report_root: Path) -> None:
    page = load_report_section(report_root, "pairs", offset=999, limit=10)
    assert page["payload"] == []
    assert page["total"] == 10


def test_dict_section_not_paged(report_root: Path) -> None:
    section = load_report_section(report_root, "methodology")
    assert section["payload"] == {"stage1": "single inference"}
    assert section["offset"] is None


def test_section_preserves_both_statuses(report_root: Path) -> None:
    """Оба статуса должны доходить до интерфейса без склейки."""
    section = load_report_section(report_root, "pairs", limit=1)
    row = section["payload"][0]
    assert row["status"] == "within_noise"
    assert row["measurement_status"] == "expression_dominated"


# --- эндпоинты --------------------------------------------------------------

def test_endpoints_report_absence_as_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без прогона Stage 3 отчёт недоступен — но это 409, а не 500.

    Разница существенна: 409 означает «данных нет, вот что сделать»,
    500 — «сервис сломан». Интерфейс показывает эти состояния по-разному.
    """
    from fastapi.testclient import TestClient

    from app6.api.server import app

    monkeypatch.delenv("DEEPUTIN_STAGE3_ROOT", raising=False)
    client = TestClient(app)
    for url in ("/api/v1/report/summary", "/api/v1/report/sections/pairs"):
        response = client.get(url)
        assert response.status_code == 409
        assert "Stage 3" in response.json()["detail"]


def test_endpoints_serve_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app6.api.server import app

    root = _write_report(tmp_path / "stage3")
    monkeypatch.setenv("DEEPUTIN_STAGE3_ROOT", str(root))
    client = TestClient(app)

    summary = client.get("/api/v1/report/summary")
    assert summary.status_code == 200
    assert summary.json()["report_schema_version"] == "deeputin-stage3-v1.4"

    section = client.get("/api/v1/report/sections/pairs", params={"limit": 3})
    assert section.status_code == 200
    assert section.json()["returned"] == 3


def test_endpoint_rejects_unknown_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app6.api.server import app

    monkeypatch.setenv("DEEPUTIN_STAGE3_ROOT", str(_write_report(tmp_path / "s3")))
    client = TestClient(app)
    assert client.get("/api/v1/report/sections/secrets").status_code == 400


def test_endpoint_validates_paging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from app6.api.server import app

    monkeypatch.setenv("DEEPUTIN_STAGE3_ROOT", str(_write_report(tmp_path / "s3")))
    client = TestClient(app)
    assert client.get("/api/v1/report/sections/pairs", params={"limit": 0}).status_code == 400
    assert client.get("/api/v1/report/sections/pairs", params={"limit": 9999}).status_code == 400
    assert client.get("/api/v1/report/sections/pairs", params={"offset": -1}).status_code == 400
