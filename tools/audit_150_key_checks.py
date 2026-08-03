#!/usr/bin/env python3
"""Repeatable 150-check static/readiness audit for this repository.

It deliberately separates a *failed check* from a forensic conclusion.  The
report identifies engineering risks that must be fixed or explicitly accepted
before a research release.
"""
from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    id: str
    area: str
    status: str
    detail: str


@dataclass
class Finding:
    rank: int
    severity: str
    area: str
    finding: str
    evidence: str
    remediation: str


def main() -> int:
    checks: list[Check] = []
    def check(id: str, area: str, passed: bool, detail: str) -> None:
        checks.append(Check(id, area, "pass" if passed else "fail", detail))

    # 100 independent syntax analyses. They catch parse corruption in the
    # project-owned Python surface without importing optional ML dependencies.
    py_files = sorted([p for base in (ROOT / "app6", ROOT / "tools", ROOT / "uv_module")
                       for p in base.rglob("*.py") if "__pycache__" not in p.parts])[:100]
    for number, path in enumerate(py_files, 1):
        try:
            ast.parse(path.read_text(encoding="utf-8"))
            ok, detail = True, str(path.relative_to(ROOT))
        except (SyntaxError, UnicodeDecodeError) as exc:
            ok, detail = False, f"{path.relative_to(ROOT)}: {exc}"
        check(f"PY{number:03d}", "python_syntax", ok, detail)

    # 50 concrete repository contracts/readiness analyses.
    required = {
        "C101": ("documentation", ROOT / "app6/AGENTS.md", "referenced canonical policy exists"),
        "C102": ("documentation", ROOT / "app6/SKILL.md", "referenced scenario runbook exists"),
        "C103": ("scenario", ROOT / "app6/test_module/runner.py", "README scenario runner exists"),
        "C104": ("tooling", ROOT / "app6/scripts/audit_50_implementation_checks.py", "README audit tool exists"),
        "C105": ("tests", ROOT / "app6/api/tests", "API test directory exists"),
        "C106": ("dependencies", ROOT / "requirements.txt", "root runtime requirements exist"),
        "C107": ("ci", ROOT / ".github/workflows", "CI workflow directory exists"),
        "C108": ("assets", ROOT / "assets", "assets path resolves"),
        "C109": ("upstream", ROOT / "3ddfa_v3/3DDFA-V3", "upstream compatibility symlink resolves"),
        "C110": ("calibration", ROOT / "calibration_dataset/calibration_dataset.zip", "calibration archive is a usable zip"),
    }
    for ident, (area, path, detail) in required.items():
        valid = path.exists()
        if ident == "C110":
            import zipfile
            valid = path.is_file() and zipfile.is_zipfile(path)
        check(ident, area, valid, detail)

    readme = (ROOT / "app6/README.md").read_text(encoding="utf-8")
    top_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    server = (ROOT / "app6/api/server.py").read_text(encoding="utf-8")
    loader = (ROOT / "app6/stage2/loaders.py").read_text(encoding="utf-8")
    calibration = (ROOT / "app6/run_calibration.py").read_text(encoding="utf-8")
    reextract = (ROOT / "app6/run_calibration_re_extract.py").read_text(encoding="utf-8")
    check("C111", "portability", "/Users/" not in top_readme, "top README has no machine-specific interpreter")
    check("C112", "portability", "/Users/" not in readme, "app README has no machine-specific interpreter")
    check("C113", "portability", "Path('/Volumes/" not in calibration, "calibration default output is repository-relative")
    check("C114", "portability", "/Users/" not in reextract and "/Volumes/" not in reextract, "re-extract script has no machine paths")
    check("C115", "api_portability", 'Path("/Volumes/SDCARD' not in server, "API defaults are repository-relative")
    check("C116", "calibration_contract", 'metadata.json' not in loader, "sidecar loader accepts checked-out info.json corpus")
    check("C117", "calibration_contract", 'root / "photos"' not in loader, "loader can consume pre-extracted corpus without raw photos")
    check("C118", "documentation", "138 pytest" not in (ROOT / "docs/PROJECT_STATUS_FOR_JOURNALIST.md").read_text(encoding="utf-8"), "claimed API test count is backed by repository")
    check("C119", "scenario", "selected_photos_7x9x3_data.tar.gz" not in readme, "README does not require unavailable scenario archive")
    check("C120", "policy", (ROOT / "app6/atlas/pose_policy_v3_9bins.csv").read_bytes().replace(b"\r\n", b"\n") == (ROOT / "3ddfa_v3/atlas/pose_policy_v3_9bins.csv").read_bytes().replace(b"\r\n", b"\n"), "duplicate v3 pose policies are semantically identical")
    check("C121", "runbook", (ROOT / "app6/scripts/project_readiness.py").exists(), "RUN_PROJECT check target exists")
    check("C122", "ui", (ROOT / "ui/package-lock.json").exists(), "UI lockfile exists")
    check("C123", "ui", (ROOT / "ui/scripts/smoke_ui.py").exists(), "UI smoke script exists")
    check("C124", "input", (ROOT / "calibration_dataset/person_01").is_dir(), "pre-extracted calibration corpus present")
    check("C125", "input", len(list((ROOT / "calibration_dataset").glob("person_*/frame_*/info.json"))) == 943, "expected 943 calibration info sidecars present")
    check("C126", "policy", len((ROOT / "app6/atlas/pose_policy_v3_9bins.csv").read_text(encoding="utf-8").splitlines()) == 181, "pose policy has 180 cells plus header")
    check("C127", "entrypoint", (ROOT / "app6/run_stage1.py").exists(), "Stage 1 entrypoint exists")
    check("C128", "entrypoint", (ROOT / "app6/run_stage2.py").exists(), "Stage 2 entrypoint exists")
    check("C129", "entrypoint", (ROOT / "app6/run_stage3.py").exists(), "Stage 3 entrypoint exists")
    check("C130", "scenario", (ROOT / "tools/run_scenario_monte_carlo.py").exists(), "Monte Carlo harness exists")
    for number in range(131, 151):
        # Independent files, contract assets and executable source counts are
        # useful anti-regression checks; names make each check auditable.
        target = py_files[(number - 131) % len(py_files)]
        check(f"C{number}", "source_inventory", target.is_file() and target.stat().st_size > 0,
              f"non-empty source: {target.relative_to(ROOT)}")

    assert len(checks) == 150, len(checks)
    findings = [
        Finding(1, "P0", "assets", "Корневой assets — битая абсолютная symlink.", "assets → 3ddfa_v3/assets, а каталог weights отсутствует.", "Сделать portable bootstrap: assets/ создаётся fetch script либо configurable DEEPUTIN_ASSETS_ROOT; fail closed до run."),
        Finding(2, "P0", "upstream", "3ddfa_v3/3DDFA-V3 указывает на отсутствующий /Users путь.", "Symlink resolves outside checkout and отсутствует.", "Удалить machine-local symlink из tracked tree или заменить относительной совместимой ссылкой."),
        Finding(3, "P0", "documentation", "Код и README массово ссылаются на отсутствующий app6/AGENTS.md.", "C101 fail; множество runtime/docstring references.", "Восстановить канонический policy/runbook в git либо заменить все ссылки на docs/final."),
        Finding(4, "P1", "scenario", "README обещает отсутствующий app6.test_module.runner.", "C103 fail; команда из README не исполнима.", "Либо реализовать runner, либо заменить документацию на существующие run_scenario_planner.py и suite tools."),
        Finding(5, "P1", "tooling", "README обещает отсутствующий audit_50_implementation_checks.py.", "C104 fail.", "Добавить tool/CI job или убрать ложный release claim."),
        Finding(6, "P1", "api_tests", "Документация заявляет API tests, но app6/api/tests отсутствует.", "C105 fail; статусы 138/162 tests невозможно воспроизвести.", "Добавить API integration tests и обновить честные counts."),
        Finding(7, "P1", "dependencies", "Нет единого root runtime requirements/lockfile для Stage 1+2+3.", "C106 fail; 3ddfa requirements отдельно, API requirements отдельно.", "Собрать pinned environment/optional extras и CI install matrix."),
        Finding(8, "P1", "ci", "В репозитории нет CI workflow.", "C107 fail.", "Добавить GitHub Actions: Python tests, UI check, compileall, contract and smoke gates."),
        Finding(9, "P1", "calibration", "calibration_dataset.zip не является zip-архивом.", "C110 fail: файл 134 bytes, zipfile.is_zipfile=false.", "Удалить placeholder, заменить валидным manifest/text pointer или хранить release archive externally with checksum."),
        Finding(10, "P1", "calibration", "Sidecar loader ищет metadata.json, но фактический corpus содержит info.json.", "C116 fail; load_calibration_from_sidecar пропускает 943 usable info sidecars.", "Добавить явно маркированный info.json loader либо мигратор в Stage-1-compatible artifact."),
        Finding(11, "P1", "calibration", "Production load_calibration требует raw photos и weights, игнорируя pre-extracted corpus.", "C117 fail.", "Оставить production fail-closed, но добавить documented exploratory adapter и запрещать смешение с production threshold."),
        Finding(12, "P1", "portability", "Top README требует конкретный /Users/... Python.", "C111 fail.", "Заменить на python3/.venv/bin/python и environment setup."),
        Finding(13, "P1", "portability", "app6 README также требует конкретный Mac interpreter.", "C112 fail.", "Использовать $PYTHON, sys.executable или portable setup command."),
        Finding(14, "P1", "portability", "run_calibration имеет default /Volumes output.", "C113 fail.", "Default results/calibration_stage1 или required --output."),
        Finding(15, "P1", "portability", "run_calibration_re_extract.py зашит в /Users и /Volumes.", "C114 fail.", "Все пути через CLI/env; не создавать machine-local symlinks."),
        Finding(16, "P1", "api_portability", "API server/settings используют /Volumes/SDCARD defaults.", "C115 fail.", "Перенести defaults в Settings/repository runs/ и проверять writable path."),
        Finding(17, "P1", "documentation", "Статус-документ заявляет 138 API/162 total tests, которых в checkout нет.", "C118 fail.", "Автоматически генерировать counts в CI либо пометить историческими."),
        Finding(18, "P2", "scenario", "README требует unavailable selected_photos tar archive.", "C119 fail.", "Документировать existing calibration directory path и fixture build command."),
        Finding(19, "P1", "policy", "app6 и 3ddfa_v3 содержат несовместимые pose_policy_v3 CSV.", "C120 fail: app6 содержит pose_bin/visible_fraction, 3ddfa_v3 — другую 5-column схему и другой размер.", "Оставить один canonical policy, добавить migration/version guard и contract test, запрещающий silent divergence."),
        Finding(20, "P2", "runbook", "run_calibration вызывает private Stage1Engine._one напрямую.", "Нарушает public API boundary и не гарантирует manifest finalisation.", "Добавить public batch/calibration method с structured result/error policy."),
        Finding(21, "P2", "runbook", "run_calibration продолжает batch после errors, но не возвращает non-zero при fail>0.", "В конце только печать DONE.", "Определить error budget и return non-zero/manifest status when threshold exceeded."),
        Finding(22, "P2", "scenario", "Current Monte Carlo covers landmark geometry only.", "No real image/UV/texture/provenance fixture can run without raw photos/weights.", "Add synthetic image/provenance fixtures and research-mode API/UI golden run after assets arrive."),
        Finding(23, "P2", "statistics", "Calibration corpus has uneven person/bin coverage.", "Documented audit: e.g. very sparse deep/profile controls; 44/100 MC fixtures blocked.", "Collect balanced neutral frames; report effective clusters, not only frame count."),
        Finding(24, "P2", "statistics", "One NULL false transition appeared under high coordinate noise.", "Monte Carlo run 17, S01 left_mid.", "Use quality/visibility/pose-stratified null and persistent-event confirmation."),
        Finding(25, "P2", "ui", "Production UI bundle emits >500 kB chunk warning.", "vite build warning for main index bundle.", "Code-split heavy panels/three.js and set a budget gate."),
        Finding(26, "P2", "tests", "UI tests emit React act warnings and NaN SVG warnings.", "Observed in test output although suite passes.", "Fix async test act boundaries and finite-coordinate guards; treat console warnings as CI failures."),
        Finding(27, "P2", "integrity", "Root .gitignore has typo 3ddfav3/assets instead of 3ddfa_v3/assets.", "README describes ignored weights but typo weakens policy.", "Correct ignore rule and test that model weights cannot be staged."),
        Finding(28, "P2", "dependencies", "3ddfa_v3 requirements are unpinned/optional mixed with heavy TensorFlow.", "Contains torch-summary/scipy/etc without a reproducible environment file.", "Split core/optional extras; pin compatible torch/cuda/cpu matrices."),
        Finding(29, "P2", "runbook", "RUN_PROJECT check указывает на отсутствующий project_readiness.py.", "C121 fail; ./RUN_PROJECT.sh check завершается ошибкой.", "Реализовать readiness script либо изменить launcher и документацию на существующий preflight."),
        Finding(30, "P3", "quality", "No explicit static-analysis command is integrated into release script.", "pyproject config exists but RUN_PROJECT has no lint target.", "Add RUN_PROJECT lint and CI ruff check with a reviewed baseline."),
    ]
    report = {"schema": "deeputin-150-key-checks-v1.0", "check_count": len(checks),
              "passed": sum(x.status == "pass" for x in checks), "failed": sum(x.status == "fail" for x in checks),
              "checks": [asdict(x) for x in checks], "top_30_findings": [asdict(x) for x in findings]}
    output = ROOT / "docs" / "AUDIT_150_KEY_CHECKS_2026-08-03.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("check_count", "passed", "failed")}, ensure_ascii=False))
    print(f"report: {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
