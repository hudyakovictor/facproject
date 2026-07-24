#!/usr/bin/env python3
"""🚪 CLI тестового модуля DEEPUTIN.

Порядок работы:
  pool → gen → build --all → cache --run → run --all --mode fast → report
Ворота (продвигаемся только на зелёных тестах):
  gate --stage stage2 [--run] [--priority P1]
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_module.config import (APP6_DIR, CACHE_DIR, CALIB_ROOT, DUMMY_DATE, RUNS_DIR,
                                SCENARIOS_DIR, TESTS_DIR, WORK_ROOT)
from test_module.pool import load_pool, write_pool_index
from test_module.registry import STAGE_GATES, gate_scenarios
from test_module import synthetic_runner
from test_module import build as buildmod
from test_module import check as checkmod
from test_module import fast_assemble
from test_module import report as reportmod
from test_module import scenarios as scen


def _base_id(sid: str) -> str:
    return re.sub(r"_v\d+$", "", sid)


def _test_root(sid: str) -> Path:
    base = _base_id(sid)
    variant = sid.replace(base, "").lstrip("_")
    if not variant:
        variant = "v00"
    return TESTS_DIR / base / variant


def _run(args: list) -> None:
    cmd = [sys.executable] + [str(a) for a in args]
    print(">>", " ".join(cmd))
    env = dict(os.environ)
    env["APP6_TEST_CONTEXT"] = "1"
    subprocess.run(cmd, check=True, cwd=str(WORK_ROOT), env=env)


def _load_scenarios(only: str | None = None, variant: int | None = None) -> list[dict]:
    out = []
    for p in sorted(SCENARIOS_DIR.glob("*.json")):
        stem = p.stem
        if only and stem != only and not stem.startswith(only + "_"):
            continue
        if variant is not None:
            if not stem.endswith(f"_v{variant:02d}"):
                continue
        out.append(json.loads(p.read_text(encoding="utf-8")))
    if not out:
        raise SystemExit("сценарии не найдены — сначала: python -m test_module.runner gen")
    return out


def cmd_build(only: str | None, plan: bool, variant: int | None = None) -> None:
    pool = load_pool()
    for s in _load_scenarios(only, variant):
        m = buildmod.build_scenario(s, pool, plan_only=plan)
        n = len(m["frames"])
        print(("📝 план " if plan else "🏗 собран ") + f"{s['id']} ({n} кадров)")


def cmd_cache(run: bool, device: str) -> None:
    inp = CACHE_DIR / "input"
    inp.mkdir(parents=True, exist_ok=True)
    seen: dict[str, Path] = {}
    missing = 0
    for mp in sorted(TESTS_DIR.glob("*/v*/build_manifest.json")):
        m = json.loads(mp.read_text(encoding="utf-8"))
        for fr in m["frames"]:
            if fr["tag"] in seen:
                continue
            src = Path(fr["src"])
            if not src.is_file():
                missing += 1
                continue
            dst = inp / f"{DUMMY_DATE}_{fr['tag']}{src.suffix.lower()}"
            if not dst.is_file():
                shutil.copy2(src, dst)
            seen[fr["tag"]] = dst
    print(f"в кэш-входе {len(seen)} уникальных кадров; нет фото для {missing}")
    if missing:
                print("⚠️ часть фото ещё не выложена в calibration_dataset/photos/")
    if run and seen:
        _run([APP6_DIR / "run_stage1.py", "--project-root", WORK_ROOT, "--input", inp,
              "--output", CACHE_DIR / "stage1", "--device", device])
    elif run:
        print("запуск stage1 пропущен — нет ни одного фото")


def _scenario_selector_to_ids(selector: str | None) -> list[str]:
    return scen.select_base_ids(selector or "all")


def cmd_execute(scenario: str, pose: str, combinations: int, stage: str, mode: str,
                device: str, fail_fast: bool, dry_run: bool, check_only: bool) -> int:
    """Single-command orchestrator: gen → build → cache/stages → check."""
    if combinations < 1 or combinations > 7:
        raise SystemExit("--combinations must be 1..7")
    if stage not in {"1", "2", "2b", "3", "all"}:
        raise SystemExit("--stage must be 1, 2, 2b, 3, or all")
    # Generate only the requested matrix. gen cleans old JSONs on purpose.
    generated = scen.generate(combinations, clean=True, scenario=scenario, pose=pose)
    selected = _load_scenarios()
    print(f"🧩 generated cases: {generated}")
    if dry_run:
        print("DRY RUN cases:")
        for s in selected:
            print(f"  {s['id']} pose={s.get('pose_no')} combo={s.get('combo_no')}")
        return 0
    # Build inputs for exactly generated cases.
    cmd_build(None, False, None)
    if stage == "1":
        cmd_cache(True, device)
        return 0
    if not check_only:
        # Stage2+ uses FAST assembly from the shared Stage1 cache.
        cmd_cache(True, device)
    failures = 0
    for s in selected:
        try:
            if check_only:
                mp = _test_root(s["id"]) / "build_manifest.json"
                rdir = RUNS_DIR / s["id"]
                if not mp.is_file() or not (rdir / "stage2").exists():
                    print(f"⚠️ {s['id']}: нет готового stage2 для check-only")
                    failures += 1
                    if fail_fast: break
                    continue
                res = checkmod.run_checks(json.loads(mp.read_text(encoding="utf-8")), rdir)
                (rdir / "check_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
                print(("✅ PASS " if res["passed"] else "❌ FAIL ") + s["id"])
            elif stage in {"2", "2b", "3", "all"}:
                res = _pipeline_one(s["id"], mode, device)
            else:
                res = {"passed": True}
            if not res.get("passed", False):
                failures += 1
                if fail_fast:
                    break
        except (RuntimeError, subprocess.CalledProcessError, SystemExit) as e:
            print(f"❌ {s['id']}: {e}")
            failures += 1
            if fail_fast:
                break
    print(f"SUMMARY cases={len(selected)} failures={failures}")
    return 1 if failures else 0


def _pipeline_one(tid: str, mode: str, device: str) -> dict:
    tdir = _test_root(tid)
    mp = tdir / "build_manifest.json"
    if not mp.is_file():
        raise SystemExit(f"нет {mp} — сначала: python -m test_module.runner build --id {tid}")
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    rdir = RUNS_DIR / tid
    if mode == "fast":
        fast_assemble.assemble(manifest, CACHE_DIR / "stage1", rdir / "stage1")
    else:
        _run([APP6_DIR / "run_stage1.py", "--project-root", WORK_ROOT, "--input", tdir,
              "--output", rdir / "stage1", "--device", device, "--overwrite"])
    _run([APP6_DIR / "run_stage2.py", "--stage1", rdir / "stage1", "--calibration", CALIB_ROOT,
          "--output", rdir / "stage2", "--overwrite"])
    for extra in ((APP6_DIR / "run_stage2b.py", "--project-root", WORK_ROOT, "--stage2", rdir / "stage2",
                   "--output", rdir / "stage2b", "--overwrite"),
                  (APP6_DIR / "run_stage3.py", "--analysis", rdir / "stage2",
                   "--output", rdir / "stage3", "--overwrite")):
        try:
            _run(list(extra))
        except subprocess.CalledProcessError as e:
            print(f"⚠️ некритичная стадия упала: {e}")
    res = checkmod.run_checks(manifest, rdir)
    (rdir / "check_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(("✅ PASS " if res["passed"] else "❌ FAIL ") + tid)
    return res


def cmd_run(only: str | None, mode: str, device: str) -> int:
    fails = 0
    for s in _load_scenarios(only):
        try:
            if not _pipeline_one(s["id"], mode, device)["passed"]:
                fails += 1
        except (RuntimeError, subprocess.CalledProcessError) as e:
            print(f"❌ {s['id']}: {e}")
            fails += 1
    return 1 if fails else 0


def cmd_check(only: str | None) -> int:
    fails = 0
    for s in _load_scenarios(only):
        mp = _test_root(s["id"]) / "build_manifest.json"
        rdir = RUNS_DIR / s["id"]
        if not mp.is_file() or not (rdir / "stage2").exists():
            print(f"⚠️ {s['id']}: нет прогона")
            fails += 1
            continue
        res = checkmod.run_checks(json.loads(mp.read_text(encoding="utf-8")), rdir)
        (rdir / "check_result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(("✅ PASS " if res["passed"] else "❌ FAIL ") + s["id"])
        if not res["passed"]:
            for check in res.get("checks", []):
                if not check.get("ok", False):
                    print(f"   - {check.get('check', 'unknown')}: {check.get('detail', '')}")
        fails += 0 if res["passed"] else 1
    return 1 if fails else 0


def _face_model_path() -> Path:
    policy_path = Path(__file__).with_name("gate_policy.json")
    policy = json.loads(policy_path.read_text(encoding="utf-8")) if policy_path.is_file() else {}
    return WORK_ROOT / str(policy.get("face_model", "assets/face_model.npy"))


def cmd_synthetic(suites: list[str] | None = None) -> int:
    payload = synthetic_runner.run(_face_model_path(), suites)
    out = Path(__file__).with_name("synthetic_results.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    synthetic_runner.print_result(payload)
    print(f"synthetic result → {out}")
    return 0 if payload["passed"] else 1


def _stage_completion(stage: str, run_dir: Path) -> tuple[bool, str]:
    if stage == "stage2b":
        p = run_dir / "stage2b" / "stage2b_manifest.json"
        data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        return data.get("status") == "complete", str(data.get("status") or "missing stage2b_manifest.json")
    if stage == "stage3":
        p = run_dir / "stage3" / "report_validation.json"
        data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
        files_ok = (run_dir / "stage3" / "index.html").is_file() and (run_dir / "stage3" / "report_data.json").is_file()
        return data.get("status") == "complete" and files_ok, str(data.get("status") or "missing Stage3 report")
    return True, "not required"


SMOKE_SCENARIOS = {
    "stage2": ["S20_minimal_pair_v00"],
    "stage2b": ["S20_minimal_pair_v00"],
    "stage3": ["S20_minimal_pair_v00"],
}


def cmd_gate(stage: str, do_run: bool, priority: str | None, mode: str, device: str,
             level: str = "stage") -> int:
    """Ворота стадии: все привязанные сценарии должны быть зелёными. 0 = можно двигаться дальше."""
    synthetic_suites = list(STAGE_GATES[stage].get("synthetic", []))
    if synthetic_suites:
        print(f"🧬 synthetic prerequisites: {', '.join(synthetic_suites)}")
        if cmd_synthetic(synthetic_suites) != 0:
            print(f"🚫 ворота {stage} ЗАКРЫТЫ: synthetic prerequisite failed")
            return 1

    all_scenarios = _load_scenarios()
    if level == "smoke":
        wanted = set(SMOKE_SCENARIOS.get(stage, []))
        todo = [s for s in all_scenarios if s["id"] in wanted]
    else:
        effective_priority = priority
        if level in ("quick", "stage") and effective_priority is None:
            effective_priority = "P1"
        todo = gate_scenarios(stage, all_scenarios, effective_priority)
    if level == "quick":
        todo = [s for s in todo if int(s.get("variant", 0)) == 0]
    elif level == "stage":
        # stage keeps all generated variants for the selected priority.
        pass
    elif level == "release":
        # release intentionally uses all generated scenarios in the stage blocks.
        pass
    if not todo:
        print(f"🚪 {stage}: ворота пока пусты ({STAGE_GATES[stage]['note']})")
        return 0
    print(f"🚪 ворота {stage}: {len(todo)} сценариев ({STAGE_GATES[stage]['note']})")
    fails = []
    for s in todo:
        rdir = RUNS_DIR / s["id"]
        cr = rdir / "check_result.json"
        if do_run:
            try:
                res = _pipeline_one(s["id"], mode, device)
            except (RuntimeError, subprocess.CalledProcessError, SystemExit) as e:
                print(f"❌ {s['id']}: {e}")
                fails.append(s["id"])
                continue
        elif cr.is_file():
            res = json.loads(cr.read_text(encoding="utf-8"))
        else:
            print(f"❌ {s['id']}: ещё не прогнан (добавьте --run)")
            fails.append(s["id"])
            continue
        if not res["passed"]:
            print(f"❌ FAIL {s['id']}")
            for check in res.get("checks", []):
                if not check.get("ok", False):
                    print(f"   - {check.get('check', 'unknown')}: {check.get('detail', '')}")
            fails.append(s["id"])
            continue
        stage_ok, stage_detail = _stage_completion(stage, rdir)
        if not stage_ok:
            print(f"❌ {s['id']}: {stage} completion check failed: {stage_detail}")
            fails.append(s["id"])
    if fails:
        print(f"🚫 ворота {stage} ЗАКРЫТЫ: провалено {len(fails)}: {', '.join(fails)}")
        return 1
    print(f"🟢 ворота {stage} ОТКРЫТЫ — можно доверять стадии / менять её код")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="DEEPUTIN test_module — сценарные тесты пайплайна app6")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pool", help="индекс пула кадров (углы + наличие фото)")
    ge = sub.add_parser("gen", help="сгенерировать библиотеку сценариев")
    ge.add_argument("--combinations", "-n", type=int, default=-1,
                    help="сколько комбинаций на каждый тест; -1 = минимум, только v00")
    ge.add_argument("--scenario-combinations", action="append", default=[], metavar="BASE_ID=N",
                    help="переопределить число комбинаций для конкретного теста, например S18_corroboration_multibin=15")
    ge.add_argument("--keep", action="store_true",
                    help="не удалять старые JSON сценариев перед генерацией")
    ge.add_argument("--scenario", default="all", help="S01..S21, номер, список через запятую или all")
    ge.add_argument("--pose", default="frontal", help="frontal, all или номер 1..9")
    b = sub.add_parser("build", help="собрать входные папки тестов")
    b.add_argument("--id")
    b.add_argument("--all", action="store_true")
    b.add_argument("--plan", action="store_true", help="только план без копирования фото")
    b.add_argument("--variant", type=int, default=None, help="номер варианта 0..4 (по умолчанию все)")
    c = sub.add_parser("cache", help="stage1-кэш нужных кадров (единственный медленный шаг, один раз)")
    c.add_argument("--run", action="store_true")
    c.add_argument("--device", default="auto")
    r = sub.add_parser("run", help="прогнать тест(ы) через пайплайн + чекер")
    r.add_argument("--id")
    r.add_argument("--all", action="store_true")
    r.add_argument("--mode", default="fast", choices=["fast", "full"])
    r.add_argument("--device", default="auto")
    ex = sub.add_parser("execute", help="один запуск: gen→build→cache/stage→check")
    ex.add_argument("--scenario", default="20", help="S01..S21, номер, список через запятую или all")
    ex.add_argument("--pose", default="frontal", help="frontal, all или номер 1..9")
    ex.add_argument("--combinations", "-n", type=int, default=1, help="1..7")
    ex.add_argument("--stage", default="all", choices=["1", "2", "2b", "3", "all"])
    ex.add_argument("--mode", default="fast", choices=["fast", "full"])
    ex.add_argument("--device", default="auto")
    ex.add_argument("--fail-fast", action="store_true")
    ex.add_argument("--dry-run", action="store_true")
    ex.add_argument("--check-only", action="store_true")
    ch = sub.add_parser("check", help="перепроверить ожидания по готовым прогонам")
    ch.add_argument("--id")
    g = sub.add_parser("gate", help="ворота стадии: 0 = зелено, 1 = стоп")
    g.add_argument("--stage", required=True, choices=sorted(STAGE_GATES))
    g.add_argument("--run", action="store_true", help="прогнать сценарии ворот заново")
    g.add_argument("--priority", choices=["P1", "P2", "P3"], help="ограничить, например только P1")
    g.add_argument("--mode", default="fast", choices=["fast", "full"])
    g.add_argument("--device", default="auto")
    g.add_argument("--level", default="smoke", choices=["smoke", "quick", "stage", "release"],
                   help="smoke=smallest scenario; quick=v00 P1; stage=all variants P1; release=full generated matrix")
    sy = sub.add_parser("synthetic", help="детерминированные тесты face_model/геометрии/Stage2")
    sy.add_argument("--suite", action="append", choices=list(synthetic_runner.SUITES),
                    help="можно повторять; по умолчанию все suites")
    sub.add_parser("report", help="сводный отчёт по прогонам")
    sub.add_parser("coverage", help="карта покрытия функций app6 тестами")
    a = p.parse_args()
    if a.cmd == "pool":
        st = write_pool_index()
        print(f"пул: {st['total']} кадров, с фото: {st['with_photo']}, люди: {', '.join(st['persons'])}")
        if st["with_photo"] == 0:
            print("⚠️ фото ещё не выложены — доступны только планы (build --plan)")
        return 0
    if a.cmd == "gen":
        overrides = scen.parse_combination_overrides(a.scenario_combinations)
        print(f"сгенерировано сценариев: {scen.generate(a.combinations, overrides, clean=not a.keep, scenario=a.scenario, pose=a.pose)} → {SCENARIOS_DIR}")
        return 0
    if a.cmd == "build":
        cmd_build(a.id, a.plan, a.variant)
        return 0
    if a.cmd == "cache":
        cmd_cache(a.run, a.device)
        return 0
    if a.cmd == "run":
        return cmd_run(a.id, a.mode, a.device)
    if a.cmd == "execute":
        return cmd_execute(a.scenario, a.pose, a.combinations, a.stage, a.mode, a.device, a.fail_fast, a.dry_run, a.check_only)
    if a.cmd == "check":
        return cmd_check(a.id)
    if a.cmd == "gate":
        return cmd_gate(a.stage, a.run, a.priority, a.mode, a.device, a.level)
    if a.cmd == "synthetic":
        return cmd_synthetic(a.suite)
    if a.cmd == "report":
        return reportmod.report()
    if a.cmd == "coverage":
        return reportmod.coverage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
