#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 NUMBA_NUM_THREADS=2
if ! python -c 'import fastapi, uvicorn, torch, imageio_ffmpeg' >/dev/null 2>&1 || [[ ! -f web/dist/index.html ]]; then
  bash scripts/setup.sh
fi
if [[ ! -f /Users/victorkhudyakov/work/3ddfa_v3/assets/net_recon_mbnet.pth || ! -f /Users/victorkhudyakov/work/3ddfa_v3/assets/face_model.npy ]]; then
  python scripts/download_assets.py || echo 'Assets unavailable; starting in cached/degraded mode.'
fi
exec python -m uvicorn server.app:app --host 0.0.0.0 --port "${PORT:-5173}"
