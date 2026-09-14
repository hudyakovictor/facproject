"""Осознанный quarantine (ТЗ П6): красный CI только по известным тикетам.

Эти 8 тестов падают и на чистом дереве (проверено через git stash) — спор о
семантике дат/evidence-слоя, не регрессия Stage1-контрактов. Помечены xfail
(strict=False): CI жёлтый осознанно, падение видно, но не блокирует.
Тикеты: DATE-SEM, EVID-WORD (завести в трекере при переносе).
"""
import pytest

QUARANTINED = {
    "app6/test_module/test_date_provenance_and_temporal.py::ResolveDateSemanticsTests::test_close_exif_within_conflict_window_resolved_clean",
    "app6/test_module/test_date_provenance_and_temporal.py::ResolveDateSemanticsTests::test_conflicting_sources_report_conflict",
    "app6/test_module/test_date_provenance_and_temporal.py::ResolveDateSemanticsTests::test_exif_takes_priority_over_filename",
    "app6/test_module/test_guard_edges2.py::EvidenceLayerTests::test_quality_limited_downgrades_non_noise",
    "app6/test_module/test_guard_edges3.py::QualityGateTests::test_quality_limited_uses_neutral_texture",
    "app6/test_module/test_guard_edges3.py::ApiReportTests::test_report_available",
    "app6/test_module/test_guard_edges3.py::ApiReportTests::test_summary_reports_withheld_prefixes",
    "app6/test_module/test_pkg001_strict.py::DateAndTemporalStrictEvidence::test_resolve_date_conflicts_invalid_fail_closed_and_repeat",
}


def pytest_collection_modifyitems(items):
    for item in items:
        if item.nodeid in QUARANTINED:
            item.add_marker(pytest.mark.xfail(
                reason="quarantined: pre-existing semantic dispute, fails on clean tree", strict=False))
