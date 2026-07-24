"""Temporary development gates integrated into app6 entry points.

The guard is intentionally controlled by gate_policy.json. Set ``enabled`` to
false when development acceptance is complete. Test subprocesses set
APP6_TEST_CONTEXT=1 to prevent recursive gate execution.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

TM_DIR = Path(__file__).resolve().parent
WORK_ROOT = TM_DIR.parent.parent
POLICY_PATH = TM_DIR / "gate_policy.json"


def load_policy() -> dict:
    if not POLICY_PATH.is_file():
        return {"enabled": False}
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def development_gates_enabled() -> bool:
    if os.environ.get("APP6_TEST_CONTEXT") == "1":
        return False
    override = os.environ.get("APP6_DEV_GATES")
    if override is not None:
        return override.strip().lower() not in {"0", "false", "no", "off"}
    return bool(load_policy().get("enabled", False))


def enforce_stage(stage: str, *, level: str | None = None) -> None:
    """Run the configured gate before a low-level stage entry point."""
    if not development_gates_enabled():
        return
    policy = load_policy()
    selected_level = level or str(policy.get("auto_level", "smoke"))
    cmd = [
        sys.executable,
        "-m",
        "app6.test_module.runner",
        "gate",
        "--stage",
        stage,
        "--run",
        "--level",
        selected_level,
    ]
    env = dict(os.environ)
    env["APP6_TEST_CONTEXT"] = "1"
    print(f"\n🧪 DEVELOPMENT GATE: {stage} / {selected_level}", flush=True)
    try:
        subprocess.run(cmd, check=True, cwd=str(WORK_ROOT), env=env)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"Development gate '{stage}' failed. Pipeline stage was not started. "
            f"Inspect app6/test_module/runs and synthetic_results.json. ({exc})"
        ) from exc
