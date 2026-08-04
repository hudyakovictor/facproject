#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

FRAMES_212="${FRAMES_212:-}"
CALIBRATION_943="${CALIBRATION_943:-}"
UI_ROOT="${UI_ROOT:-$PROJECT_ROOT/ui}"

if [[ -z "$FRAMES_212" ]]; then
  echo "FAIL: задайте FRAMES_212=/path/to/calibration_frames" >&2
  exit 2
fi

if [[ -z "$CALIBRATION_943" ]]; then
  echo "FAIL: задайте CALIBRATION_943=/path/to/calibration_dataset" >&2
  exit 2
fi

echo "=== 1/5 Python compile ==="
python3 -m py_compile \
  tools/acceptance_round6.py \
  tools/acceptance_a11.py \
  tools/rebuild_landmark_utility.py

echo "=== 2/5 Backend tests ==="
python3 -m unittest \
  app6.test_module.test_guard_edges \
  app6.test_module.test_guard_edges2 \
  app6.test_module.test_guard_edges3 \
  app6.test_module.test_p18_hardening \
  app6.test_module.test_provenance_integration \
  app6.test_module.test_round5_patches \
  app6.test_module.test_a11_artifacts

echo "=== 3/5 Round 6 acceptance ==="
python3 tools/acceptance_round6.py --frames "$FRAMES_212"

echo "=== 4/5 Rebuild and accept A11 ==="
python3 tools/rebuild_landmark_utility.py \
  --calibration-root "$CALIBRATION_943"

python3 tools/acceptance_a11.py \
  --calibration-root "$CALIBRATION_943"

echo "=== 5/5 UI ==="
if [[ ! -f "$UI_ROOT/package-lock.json" ]]; then
  echo "FAIL: UI package-lock.json не найден: $UI_ROOT" >&2
  exit 2
fi

(
  cd "$UI_ROOT"
  rm -rf node_modules dist
  npm ci
  npm run check
)

echo
echo "========================================"
echo "PROJECT ACCEPTANCE: PASS"
echo "========================================"
