#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m pip install -r requirements-macos-m1.txt
if [ ! -d third_party/FFHQ-detect-face-wrinkles/.git ]; then
  git clone --depth 1 https://github.com/rmsandu/FFHQ-detect-face-wrinkles.git third_party/FFHQ-detect-face-wrinkles
fi
cat <<'EOF'
Surface Lab dependencies installed.
UV module intentionally stays as ../uv_module.
For FFHQ inference, pass --checkpoint /path/to/best_checkpoint_iou032.pth.
EOF
