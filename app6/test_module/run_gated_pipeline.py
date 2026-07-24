#!/usr/bin/env python3
"""🔐 Запуск РЕАЛЬНОГО анализа с воротами: каждая стадия запускается только
после того, как её сценарные тесты зелёные. Главная точка интеграции с пайплайном.

Пример:
  python test_module/run_gated_pipeline.py --input <папка_фото> --output <папка_результатов> --priority P1
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_module.config import APP6_DIR, CALIB_ROOT, TM_DIR, WORK_ROOT


def _run(args: list) -> None:
    cmd = [sys.executable] + [str(a) for a in args]
    print(">>", " ".join(cmd))
    env = dict(os.environ)
    env["APP6_TEST_CONTEXT"] = "1"
    subprocess.run(cmd, check=True, cwd=str(WORK_ROOT), env=env)


def _gate(stage: str, priority: str | None) -> None:
    args = [TM_DIR / "runner.py", "gate", "--stage", stage, "--run", "--level", "stage"]
    if priority:
        args += ["--priority", priority]
    try:
        _run(args)
    except subprocess.CalledProcessError:
        raise SystemExit(f"\n🚫 СТОП: тестовые ворота '{stage}' не пройдены.\n"
                         f"См. test_module/runs/*/check_result.json, почините код/сценарий и повторите.")


def main() -> int:
    p = argparse.ArgumentParser(description="Реальный анализ с тестовыми воротами между стадиями")
    p.add_argument("--input", required=True, help="папка с реальными фото для расследования")
    p.add_argument("--output", required=True, help="папка результатов (будут подпапки stage1/2/2b/3)")
    p.add_argument("--device", default="auto")
    p.add_argument("--priority", choices=["P1", "P2", "P3"], default=None,
                   help="строгость ворот (P1 = только главные тесты, быстрее)")
    p.add_argument("--skip-stage1", action="store_true", help="stage1 уже посчитан в output/stage1")
    a = p.parse_args()
    out = Path(a.output)

    _gate("stage1", a.priority)
    if not a.skip_stage1:
        _run([APP6_DIR / "run_stage1.py", "--project-root", WORK_ROOT, "--input", a.input,
              "--output", out / "stage1", "--device", a.device])

    _gate("stage2", a.priority)
    _run([APP6_DIR / "run_stage2.py", "--stage1", out / "stage1", "--calibration", CALIB_ROOT,
          "--output", out / "stage2", "--overwrite"])

    _gate("stage2b", a.priority)
    _run([APP6_DIR / "run_stage2b.py", "--project-root", WORK_ROOT, "--stage2", out / "stage2",
          "--output", out / "stage2b", "--overwrite"])

    _gate("stage3", a.priority)
    _run([APP6_DIR / "run_stage3.py", "--analysis", out / "stage2", "--output", out / "stage3", "--overwrite"])

    print("\n🏁 Готово: все стадии прошли через зелёные ворота.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
