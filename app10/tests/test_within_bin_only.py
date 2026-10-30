import json
import subprocess
import sys
from pathlib import Path


def test_no_between_keys():
    # проверяем что в отчёте нет между-групповых ключей
    rep = Path('/Users/victorkhudyakov/work/app10/reports/calib_all_withinbin/calibration_one_person.json')
    if not rep.exists():
        return
    d = json.loads(rep.read_text())
    for k in d.get('by_bin', {}).keys():
        assert not k.startswith('between_'), f'found between key {k}'
