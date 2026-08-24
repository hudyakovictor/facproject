#!/usr/bin/env bash
set -uo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# DEEPUTIN app6 — overnight full pipeline launcher
# Запускает все этапы последовательно + API + UI.
# Использование: ./RUN_ALL.sh [--skip-ui] [--skip-api] [--stage1-only]
# ═══════════════════════════════════════════════════════════════════════════════

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${DEEPUTIN_PYTHON:-$ROOT/.venv/bin/python}"

# ── Colors / helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ts() { date '+%Y-%m-%d %H:%M:%S'; }
log()  { echo -e "[$(ts)] ${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "[$(ts)] ${YELLOW}[WARN]${NC}  $*"; }
fail() { echo -e "[$(ts)] ${RED}[FAIL]${NC}  $*"; }

# ── Args ─────────────────────────────────────────────────────────────────────
SKIP_UI=true
SKIP_API=true
STAGE1_ONLY=false
FROM_STAGE2=false
for arg in "$@"; do
  case "$arg" in
    --with-ui)    SKIP_UI=false ;;
    --with-api)   SKIP_API=false ;;
    --stage1-only) STAGE1_ONLY=true ;;
    --from-stage2) FROM_STAGE2=true ;;
    *) echo "unknown arg: $arg"; exit 2 ;;
  esac
done

cd "$ROOT"

# ── Fixed paths (from user) ──────────────────────────────────────────────────
INPUT_DIR="/Volumes/SDCARD/photo/main"
CALIBRATION_DIR="/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"
STORAGE_DIR="/Volumes/SDCARD/storage"
mkdir -p "$STORAGE_DIR"
LOG_DIR="$STORAGE_DIR/_logs"
mkdir -p "$LOG_DIR"

export DEEPUTIN_STAGE1_ROOT="$STORAGE_DIR/stage1"
export DEEPUTIN_STAGE2_ROOT="$STORAGE_DIR/stage2"
export DEEPUTIN_STAGE3_ROOT="$STORAGE_DIR/stage3"
export DEEPUTIN_CALIBRATION_ROOT="$CALIBRATION_DIR"
export DEEPUTIN_STORAGE_ROOT="$STORAGE_DIR"

log "Input (photos):      $INPUT_DIR"
log "Calibration:         $CALIBRATION_DIR"
log "Storage root:        $STORAGE_DIR"
log "Stage1 root:         $DEEPUTIN_STAGE1_ROOT"
log "Stage2 root:         $DEEPUTIN_STAGE2_ROOT"
log "Stage3 root:         $DEEPUTIN_STAGE3_ROOT"
log "Python:              $PYTHON"

# ═══════════════════════════════════════════════════════════════════════════════
# 0. PREFLIGHT
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$FROM_STAGE2" == "true" ]]; then
  log "Skipping preflight (--from-stage2)."
else
  log "=== STEP 0/5: Preflight check ==="
  PREFLIGHT_ARGS=(
    --project-root "$ROOT"
    --calibration-root "$DEEPUTIN_CALIBRATION_ROOT"
    --output "$LOG_DIR/preflight.json"
  )
  if [[ -d "$DEEPUTIN_STAGE1_ROOT" ]]; then
    PREFLIGHT_ARGS+=(--stage1-root "$DEEPUTIN_STAGE1_ROOT")
  fi

  "$PYTHON" "$ROOT/app6/run_preflight.py" "${PREFLIGHT_ARGS[@]}" 2>&1 | tee "$LOG_DIR/00_preflight.log"

  PREFLIGHT_STATUS="${PIPESTATUS[0]}"
  if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
    fail "Preflight blocked (exit $PREFLIGHT_STATUS). Check $LOG_DIR/00_preflight.log"
    exit "$PREFLIGHT_STATUS"
  fi
  log "Preflight passed."
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 1. STAGE 1 — 3DDFA extraction
# ═══════════════════════════════════════════════════════════════════════════════
STAGE1_DONE=false
if [[ "$FROM_STAGE2" == "true" ]]; then
  log "Skipping stage1 (--from-stage2)."
  STAGE1_DONE=true
elif [[ -f "$DEEPUTIN_STAGE1_ROOT/main_timeline.csv" ]]; then
  log "Stage 1 already has main_timeline.csv — skipping."
  STAGE1_DONE=true
else
  log "=== STEP 1/5: Stage 1 (extraction) ==="
  log "Longest step (~1-2h for 1908 photos on CPU)."
  "$PYTHON" "$ROOT/app6/run_stage1.py" \
    --project-root "$ROOT" \
    --input "$INPUT_DIR" \
    --output "$DEEPUTIN_STAGE1_ROOT" \
    --device cpu \
    --fail-fast \
    2>&1 | tee "$LOG_DIR/01_stage1.log"

  STAGE1_STATUS="${PIPESTATUS[0]}"
  if [[ "$STAGE1_STATUS" -ne 0 ]]; then
    fail "Stage 1 failed (exit $STAGE1_STATUS). Check $LOG_DIR/01_stage1.log"
    exit "$STAGE1_STATUS"
  fi
  STAGE1_DONE=true
  log "Stage 1 complete."
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 2. STAGE 2 — pairwise analysis
# ═══════════════════════════════════════════════════════════════════════════════
STAGE2_DONE=false
if [[ "$STAGE1_ONLY" == "true" ]]; then
  log "Stage 1 only mode — skipping 2/2B/3."
else
  if [[ -f "$DEEPUTIN_STAGE2_ROOT/analysis_manifest.json" ]]; then
    log "Stage 2 already has analysis_manifest.json — skipping."
    STAGE2_DONE=true
  else
    log "=== STEP 2/5: Stage 2 (analysis) ==="
  STAGE2_ARGS=(
    --project-root "$ROOT"
    --stage1 "$DEEPUTIN_STAGE1_ROOT"
    --calibration "$DEEPUTIN_CALIBRATION_ROOT"
    --output "$DEEPUTIN_STAGE2_ROOT"
  )
  if [[ -f "$DEEPUTIN_STAGE2_ROOT/stage2_checkpoint.pkl" ]]; then
    STAGE2_ARGS+=(--resume)
  fi

  "$PYTHON" "$ROOT/app6/run_stage2.py" "${STAGE2_ARGS[@]}" \
    2>&1 | tee "$LOG_DIR/02_stage2.log"

    STAGE2_STATUS="${PIPESTATUS[0]}"
    if [[ "$STAGE2_STATUS" -ne 0 ]]; then
      fail "Stage 2 failed (exit $STAGE2_STATUS). Check $LOG_DIR/02_stage2.log"
      exit "$STAGE2_STATUS"
    fi
    STAGE2_DONE=true
    log "Stage 2 complete."
  fi

  # ═══════════════════════════════════════════════════════════════════════════════
  # 2B. STAGE 2B — post-processing
  # ═══════════════════════════════════════════════════════════════════════════════
  STAGE2B_DONE=false
  STAGE2B_OUT="$STORAGE_DIR/stage2b"
mkdir -p "$STAGE2B_OUT"
  if [[ -f "$STAGE2B_OUT/stage2b_manifest.json" ]]; then
    log "Stage 2B already has stage2b_manifest.json — skipping."
    STAGE2B_DONE=true
  else
    log "=== STEP 2B/5: Stage 2B (post-processing) ==="
    "$PYTHON" "$ROOT/app6/run_stage2b.py" \
      --project-root "$ROOT" \
      --stage2 "$DEEPUTIN_STAGE2_ROOT" \
      --output "$STAGE2B_OUT" \
      2>&1 | tee "$LOG_DIR/02b_stage2b.log"

    STAGE2B_STATUS="${PIPESTATUS[0]}"
    if [[ "$STAGE2B_STATUS" -ne 0 ]]; then
      fail "Stage 2B failed (exit $STAGE2B_STATUS). Check $LOG_DIR/02b_stage2b.log"
      exit "$STAGE2B_STATUS"
    fi
    STAGE2B_DONE=true
    log "Stage 2B complete."
  fi

  # ═══════════════════════════════════════════════════════════════════════════════
  # 3. STAGE 3 — final HTML/JSON report
  # ═══════════════════════════════════════════════════════════════════════════════
  STAGE3_DONE=false
  if [[ -f "$DEEPUTIN_STAGE3_ROOT/report_data.json" ]]; then
    log "Stage 3 already has report_data.json — skipping."
    STAGE3_DONE=true
  else
    log "=== STEP 3/5: Stage 3 (report) ==="
    "$PYTHON" "$ROOT/app6/run_stage3.py" \
      --analysis "$DEEPUTIN_STAGE2_ROOT" \
      --output "$DEEPUTIN_STAGE3_ROOT" \
      2>&1 | tee "$LOG_DIR/03_stage3.log"

    STAGE3_STATUS="${PIPESTATUS[0]}"
    if [[ "$STAGE3_STATUS" -ne 0 ]]; then
      fail "Stage 3 failed (exit $STAGE3_STATUS). Check $LOG_DIR/03_stage3.log"
      exit "$STAGE3_STATUS"
    fi
    STAGE3_DONE=true
    log "Stage 3 complete."
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 4. API server
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$SKIP_API" == "true" ]]; then
  log "Skipping API server (--skip-api)."
else
  log "=== STEP 4/5: API server ==="
  log "Starting uvicorn on http://0.0.0.0:8000 ..."
  cd "$ROOT"
  "$PYTHON" -m uvicorn app6.api.server:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    2>&1 | tee -a "$LOG_DIR/04_api.log" &
  API_PID=$!
  log "API PID: $API_PID"
  sleep 2
  if ! kill -0 "$API_PID" 2>/dev/null; then
    fail "API server crashed. Check $LOG_DIR/04_api.log"
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# 5. UI dev server
# ═══════════════════════════════════════════════════════════════════════════════
if [[ "$SKIP_UI" == "true" ]]; then
  log "Skipping UI (--skip-ui)."
else
  log "=== STEP 5/5: UI dev server ==="
  log "Starting Vite on http://localhost:5173 ..."
  cd "$ROOT/ui"
  npm run dev 2>&1 | tee -a "$LOG_DIR/05_ui.log" &
  UI_PID=$!
  log "UI PID: $UI_PID"
  sleep 3
  if ! kill -0 "$UI_PID" 2>/dev/null; then
    fail "UI server crashed. Check $LOG_DIR/05_ui.log"
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
echo ""
log "═══════════════════════════════════════════════════════════════"
log " ALL STAGES SUMMARY"
log "═══════════════════════════════════════════════════════════════"
log " Stage 1 (extraction):  $([[ ${STAGE1_DONE:-false} == true ]] && echo -e '${GREEN}done/skipped${NC}' || echo -e '${RED}failed${NC}')"
log " Stage 2 (analysis):    $([[ ${STAGE2_DONE:-false} == true ]] && echo -e '${GREEN}done/skipped${NC}' || echo -e '${RED}failed${NC}')"
log " Stage 2B (post-proc):  $([[ ${STAGE2B_DONE:-false} == true ]] && echo -e '${GREEN}done/skipped${NC}' || echo -e '${RED}failed${NC}')"
log " Stage 3 (report):      $([[ ${STAGE3_DONE:-false} == true ]] && echo -e '${GREEN}done/skipped${NC}' || echo -e '${RED}failed${NC}')"
log " API server:            $([[ $SKIP_API == true ]] && echo 'skipped' || echo -e "${GREEN}running (PID $API_PID)${NC}")"
log " UI dev server:         $([[ $SKIP_UI == true ]] && echo 'skipped' || echo -e "${GREEN}running (PID $UI_PID)${NC}")"
log " Logs:                  $LOG_DIR"
log "═══════════════════════════════════════════════════════════════"
log "Open UI:  http://localhost:5173"
log "Open API: http://localhost:8000/api/v1/health"
log "═══════════════════════════════════════════════════════════════"
