#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT/_logs"
mkdir -p "$LOG_DIR"
PY="/Users/victorkhudyakov/work/.venv/bin/python"
STAGE2="/Volumes/SDCARD/storage/stage2"
STAGE1="/Volumes/SDCARD/storage/stage1"
STAGE3="/Volumes/SDCARD/storage/stage3"
CALIBRATION="/Volumes/SDCARD/photo/calibration_dataset/calibration_datasets"

echo "=== VALIDATION RUN: $(date) ===" | tee "$LOG_DIR/00_header.log"

run_test() {
  local num="$1"
  local script="$ROOT/$2"
  local log="$LOG_DIR/${num}_${2%.py}.log"
  shift 2
  echo "--- RUNNING: $2 ---" | tee -a "$LOG_DIR/00_header.log"
  if [[ ! -f "$script" ]]; then
    echo "SKIP: script not found: $script" | tee -a "$log"
    return 2
  fi
  local start=$(date +%s)
  set +e
  "$PY" "$script" "$@" 2>&1 | tee -a "$log"
  local rc=${PIPESTATUS[0]}
  set -e
  local end=$(date +%s)
  echo "EXIT_CODE=$rc DURATION=$((end-start))s" | tee -a "$log"
  echo "" | tee -a "$log"
  return $rc
}

echo "Logs directory: $LOG_DIR"
echo "Stage1: $STAGE1"
echo "Stage2: $STAGE2"
echo "Stage3: $STAGE3"
echo "Calibration: $CALIBRATION"
echo ""

# 1. Stage 2 contract (implemented)
run_test "01" "check_stage2_contract.py" "$STAGE2" --sample-limit 20 --max-depth 4

# 2-12. Scaffolds - run with minimal args, expect SCAFFOLD_ONLY
run_test "02" "check_stage1_to_stage2_link.py" "$STAGE1" "$STAGE2"
run_test "03" "check_pair_legality.py" "$STAGE2"
run_test "04" "check_calibration_health.py" "$CALIBRATION" "$STAGE2"
run_test "05" "check_expression_consistency.py" "$STAGE1" "$STAGE2"
run_test "06" "check_pose_alignment_diagnostics.py" "$STAGE1" "$STAGE2"
run_test "07" "check_primary_metrics_consistency.py" "$STAGE2"
run_test "08" "check_fdr_and_pvalues.py" "$STAGE2"
run_test "09" "check_chronology_logic.py" "$STAGE2" "$STAGE3"
run_test "10" "check_evidence_packet_integrity.py" "$STAGE2"
run_test "11" "check_stage2b_noninvention.py" "$STAGE2" "$ROOT/stage2b" 2>/dev/null || run_test "11" "check_stage2b_noninvention.py" "$STAGE2" "$STAGE2"
run_test "12" "check_stage3_claim_safety.py" "$STAGE3"

echo "=== ALL TESTS COMPLETED ===" | tee -a "$LOG_DIR/00_header.log"
echo "Logs: $LOG_DIR"
