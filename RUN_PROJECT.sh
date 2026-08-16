#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${DEEPUTIN_PYTHON:-$ROOT/.venv/bin/python}"

# Локальный рабочий набор уже содержит готовый Stage 1.  Внешний диск
# остаётся поддержанным через DEEPUTIN_STORAGE_ROOT, но больше не является
# неявным обязательным источником данных.
if [[ -n "${DEEPUTIN_STORAGE_ROOT:-}" ]]; then
  STORAGE="$DEEPUTIN_STORAGE_ROOT"
elif [[ -d "/Volumes/SDCARD/storage" ]]; then
  STORAGE="/Volumes/SDCARD/storage"
else
  STORAGE="$ROOT/storage_light/storage"
fi

if [[ -n "${DEEPUTIN_CALIBRATION_ROOT:-}" ]]; then
  CALIBRATION_ROOT="$DEEPUTIN_CALIBRATION_ROOT"
elif [[ -d "/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets" ]]; then
  CALIBRATION_ROOT="/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"
elif [[ -d "/Volumes/SDCARD/calibration" ]]; then
  CALIBRATION_ROOT="/Volumes/SDCARD/calibration"
elif [[ -d "$ROOT/storage_light/calibration" ]]; then
  CALIBRATION_ROOT="$ROOT/storage_light/calibration"
else
  CALIBRATION_ROOT="/Volumes/SDCARD/calibration"
fi

# A complete UI session must point to the same finished run for every stage.
export DEEPUTIN_STAGE1_ROOT="${DEEPUTIN_STAGE1_ROOT:-$STORAGE/stage1}"
export DEEPUTIN_STAGE2_ROOT="${DEEPUTIN_STAGE2_ROOT:-$STORAGE/stage2}"
export DEEPUTIN_STAGE3_ROOT="${DEEPUTIN_STAGE3_ROOT:-$STORAGE/stage3}"
export DEEPUTIN_CALIBRATION_ROOT="$CALIBRATION_ROOT"

MODE="${1:-ui}"
case "$MODE" in
  ui) cd "$ROOT/ui-v5/ui-v5"; exec npm run dev ;;
  api) shift; cd "$ROOT"; exec "$PYTHON" -m uvicorn app6.api.server:app --host 0.0.0.0 --port "${PORT:-8000}" "$@" ;;
  check) cd "$ROOT"; exec "$PYTHON" -m pytest -q app6/test_module ;;
  preflight) shift; exec "$PYTHON" "$ROOT/app6/run_preflight.py" --project-root "$ROOT" "$@" ;;
  stage1) shift; exec "$PYTHON" "$ROOT/app6/run_stage1.py" --project-root "$ROOT" "$@" ;;
  stage2)
    shift
    if [[ "$#" -eq 0 ]]; then
      set -- --project-root "$ROOT" \
        --stage1 "$DEEPUTIN_STAGE1_ROOT" \
        --calibration "$DEEPUTIN_CALIBRATION_ROOT" \
        --output "$DEEPUTIN_STAGE2_ROOT"
    fi
    exec "$PYTHON" "$ROOT/app6/run_stage2.py" "$@"
    ;;
  stage2b) shift; exec "$PYTHON" "$ROOT/app6/run_stage2b.py" "$@" ;;
  stage3) shift; exec "$PYTHON" "$ROOT/app6/run_stage3.py" "$@" ;;
  *) echo "usage: $0 {ui|api|check|preflight|stage1|stage2|stage2b|stage3} [args...]" >&2; exit 2 ;;
esac
