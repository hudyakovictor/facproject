"""Регрессия `app6/api/skin_zones.py` — чтение УЖЕ сохранённых артефактов Stage 1.

Ключевой инвариант: модуль ничего не вычисляет заново и не подставляет ноль
вместо отсутствующих данных (`app6/AGENTS.md`).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app6.api.skin_zones import load_skin_zone_report, zone_catalog

REAL_SAMPLE = Path(__file__).resolve().parents[3] / "3ddfa_v3" / "examples" / "results" / "2000_06_14"


def test_zone_catalog_matches_atlas() -> None:
    """Каталог зон строится из атласа, а не из захардкоженного списка."""
    zones = zone_catalog()
    assert len(zones) == 40
    by_name = {z["name"]: z for z in zones}
    # Веки и губы исключаются сегментацией — мягкие ткани, зависят от мимики.
    assert by_name["upper_lip"]["excluded_by_segmentation"] is True
    assert by_name["forehead_center"]["excluded_by_segmentation"] is False
    assert by_name["forehead_center"]["group"] == "forehead"


@pytest.mark.skipif(not REAL_SAMPLE.is_dir(), reason="нет примера вывода Stage 1")
def test_reads_real_stage1_artifacts() -> None:
    report = load_skin_zone_report(REAL_SAMPLE)
    assert report["pose_bin"] == "frontal"
    assert report["active_zone_count"] > 0
    assert report["zone_count"] == len(report["zones"])
    assert (report["active_zone_count"] + report["excluded_zone_count"]
            + report["no_data_zone_count"]) == report["zone_count"]

    forehead = next(z for z in report["zones"] if z["name"] == "forehead_center")
    # Значения должны совпадать с тем, что лежит на диске, без пересчёта.
    on_disk = json.loads((REAL_SAMPLE / "skin_zone_quality.json").read_text(encoding="utf-8"))
    assert forehead["skin_pixels"] == on_disk["zones"]["forehead_center"]["skin_pixels"]
    assert forehead["visible_fraction"] == pytest.approx(
        on_disk["zones"]["forehead_center"]["visible_fraction"])
    assert report["available_sources"]["skin_zone_quality"] is True


def test_missing_artifacts_produce_no_data_not_zero(tmp_path: Path) -> None:
    """Отсутствующий канал = `null` и статус `no_data`, а НЕ 0.

    Ноль означал бы измеренное нулевое значение и исказил бы отчёт.
    """
    report = load_skin_zone_report(tmp_path)
    assert report["active_zone_count"] == 0
    assert report["no_data_zone_count"] == report["zone_count"] > 0
    for zone in report["zones"]:
        assert zone["status"] == "no_data"
        assert zone["texture_score"] is None
        assert zone["visible_fraction"] is None
    assert report["available_sources"]["per_zone_quality"] is False


def test_quality_zone_name_aliases_are_matched(tmp_path: Path) -> None:
    """`forehead_L` в quality.json соответствует `forehead_left` в атласе."""
    (tmp_path / "quality.json").write_text(json.dumps({
        "per_zone_quality": {"forehead_L": {"texture_score_0_1": 0.5, "quality_class": "good"}}
    }), encoding="utf-8")
    report = load_skin_zone_report(tmp_path)
    zone = next(z for z in report["zones"] if z["name"] == "forehead_left")
    assert zone["texture_score"] == 0.5
    assert zone["status"] == "active"
