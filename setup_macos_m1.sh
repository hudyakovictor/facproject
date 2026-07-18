#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "WARNING: this installer is designed for native Apple Silicon macOS." >&2
fi
command -v brew >/dev/null || { echo "Install Homebrew: https://brew.sh"; exit 2; }
brew install python@3.11 libomp cmake pkg-config
PY="$(brew --prefix python@3.11)/bin/python3.11"
"$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r requirements-macos.txt
(
  cd 3ddfav3/util/cython_renderer
  python setup.py build_ext --inplace
)
python scripts/doctor.py
cat <<'EOF'
Environment ready. Put licensed 3DDFA assets in 3ddfav3/assets/, then run:
  source .venv/bin/activate
  python run_calibration.py --input /path/to/same_day_photos --output runs/my_calibration
  python run_main_analysis.py --input /path/to/main_dataset --calibration runs/my_calibration --output runs/main_analysis
EOF
