import json
from pathlib import Path


def test_withinbin_report_has_mad_p95():
    rep = Path('/Users/victorkhudyakov/work/app10/reports/calib_all_full_withinbin/calibration_one_person.json')
    assert rep.exists()
    d = json.loads(rep.read_text())
    # frontal should have stats
    f = d['by_bin']['frontal']
    assert f['count'] > 10
    assert f['mad_within_bin'] is not None
    assert f['p95_within_bin'] is not None
