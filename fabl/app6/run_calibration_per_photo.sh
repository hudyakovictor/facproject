#!/bin/bash
set -e
ROOT="/Users/victorkhudyakov/work"
STAGE1_DIR="/Volumes/SDCARD/storage/stage1"
CALIB_INPUT="/Volumes/SDCARD/storage/calibration_input"

export PYTHONPATH="${ROOT}/3ddfa_v3:${ROOT}/uv_module:${ROOT}/app6"
cd "$ROOT"

mkdir -p "$STAGE1_DIR"

total=$(ls "$CALIB_INPUT"/*.jpg 2>/dev/null | wc -l | tr -d ' ')
i=0
ok=0
fail=0

for f in "$CALIB_INPUT"/*.jpg; do
  [ -f "$f" ] || continue
  i=$((i+1))
  base=$(basename "$f")
  echo "[$i/$total] $base"

  # Temp dir with just this one photo
  tmpdir=$(mktemp -d)
  ln -sf "$f" "$tmpdir/$base"

  if python3 app6/run_stage1.py --input "$tmpdir" --output "$STAGE1_DIR" --overwrite 2>&1 | grep -q "success="; then
    echo "  OK"
    ok=$((ok+1))
  else
    echo "  STAGE1 FAIL"
    fail=$((fail+1))
  fi

  rm -rf "$tmpdir"
done

echo "DONE: ok=$ok fail=$fail total=$total"
