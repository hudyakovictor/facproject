#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-ui}"
case "$MODE" in
  ui) exec "$ROOT/ui/START_UI.sh" ;;
  check) exec python3 "$ROOT/app6/scripts/project_readiness.py" --project-root "$ROOT" ;;
  preflight) shift; exec python3 "$ROOT/app6/run_preflight.py" --project-root "$ROOT" "$@" ;;
  stage1) shift; exec python3 "$ROOT/app6/run_stage1.py" --project-root "$ROOT" "$@" ;;
  stage2) shift; exec python3 "$ROOT/app6/run_stage2.py" "$@" ;;
  stage2b) shift; exec python3 "$ROOT/app6/run_stage2b.py" "$@" ;;
  stage3) shift; exec python3 "$ROOT/app6/run_stage3.py" "$@" ;;
  *) echo "usage: $0 {ui|check|preflight|stage1|stage2|stage2b|stage3} [args...]" >&2; exit 2 ;;
esac
