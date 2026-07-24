"""📊 Сводный отчёт по всем прогонам + карта покрытия кода тестами."""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_module.config import RUNS_DIR, SCENARIOS_DIR
from test_module.registry import FUNCTION_MAP


def report() -> int:
    rows = []
    for cr in sorted(RUNS_DIR.glob("*/check_result.json")):
        r = json.loads(cr.read_text(encoding="utf-8"))
        sid = r["scenario_id"]
        sp = SCENARIOS_DIR / f"{sid}.json"
        block = json.loads(sp.read_text(encoding="utf-8")).get("block", "?") if sp.is_file() else "?"
        failed = [c["check"] for c in r["checks"] if not c["ok"]]
        rows.append({"scenario": sid, "block": block, "passed": r["passed"], "failed_checks": ";".join(failed)})
    if not rows:
        print("нет результатов — сначала: python -m test_module.runner run --all")
        return 1
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out = RUNS_DIR / "summary.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "block", "passed", "failed_checks"])
        w.writeheader()
        w.writerows(rows)
    npass = sum(1 for r in rows if r["passed"])
    print(f"PASS {npass}/{len(rows)}  →  {out}")
    for r in rows:
        mark = "✅" if r["passed"] else "❌"
        print(f" {mark} {r['scenario']} [{r['block']}] {r['failed_checks']}")
    return 0 if npass == len(rows) else 1


def coverage() -> int:
    print("Карта покрытия кода app6 сценарными тестами:")
    for e in FUNCTION_MAP:
        mark = {"implemented": "✅", "partial": "🟡", "planned": "📝"}.get(e["status"], "?")
        scen = ", ".join(e["scenarios"]) or "—"
        print(f" {mark} {e['code']}")
        print(f"    что проверяем: {e['what']}")
        print(f"    сценарии: {scen}")
    return 0
