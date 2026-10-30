#!/usr/bin/env bash
# Reconstruct the ephemeral dependencies/weights after an Arena snapshot restore.
set -euo pipefail
cd "$(dirname "$0")/.."
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 NUMBA_NUM_THREADS=2
export GOMEMLIMIT=160MiB GOGC=30
python -m pip install --no-cache-dir torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install --no-cache-dir -r requirements.txt
(cd web && npm ci --no-audit --no-fund && npm run build)
python scripts/download_mediapipe.py || echo 'WARNING: MediaPipe eye measurements unavailable.'
if ! python scripts/download_assets.py; then
  echo 'WARNING: assets unavailable. App can still open cached reconstructions; new inference is disabled.'
fi
(cd vendor/3DDFA-V3/util/cython_renderer && python setup.py build_ext -i) || echo 'WARNING: CPU export renderer unavailable. Browser 3D still works.'
printf '\nReady. Use scripts/start.sh in a long-running process (Arena start_process).\n'
