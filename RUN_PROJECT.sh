#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3)"
fi

STORAGE="${DEEPUTIN_STORAGE_ROOT:-/Volumes/SDCARD/storage}"
export DEEPUTIN_STAGE1_ROOT="${DEEPUTIN_STAGE1_ROOT:-$STORAGE/stage1}"
export DEEPUTIN_STAGE2_ROOT="${DEEPUTIN_STAGE2_ROOT:-$STORAGE/stage2}"
export DEEPUTIN_STAGE3_ROOT="${DEEPUTIN_STAGE3_ROOT:-$STORAGE/stage3}"
export DEEPUTIN_CALIBRATION_ROOT="${DEEPUTIN_CALIBRATION_ROOT:-/Volumes/SDCARD/calibration}"

MODE="${1:-ui}"
case "$MODE" in
  ui)
    cd "$ROOT/ui-v5"
    exec npm run dev
    ;;
  api)
    shift
    cd "$ROOT"
    exec "$PY" -m uvicorn app6.api.server:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
    ;;
  check)
    cd "$ROOT"
    exec "$PY" -m pytest -q app6/test_module app6/api/tests
    ;;
  preflight)
    shift
    exec "$PY" "$ROOT/app6/run_preflight.py" --project-root "$ROOT" "$@"
    ;;
  stage1)
    shift
    exec "$PY" "$ROOT/app6/run_stage1.py" --project-root "$ROOT" "$@"
    ;;
  stage2)
    shift
    exec "$PY" "$ROOT/app6/run_stage2.py" "$@"
    ;;
  stage2b)
    shift
    exec "$PY" "$ROOT/app6/run_stage2b.py" "$@"
    ;;
  stage3)
    shift
    exec "$PY" "$ROOT/app6/run_stage3.py" "$@"
    ;;
  *)
    echo "usage: $0 {ui|api|check|preflight|stage1|stage2|stage2b|stage3} [args...]" >&2
    exit 2
    ;;
esac
