#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 scripts/build_static.py
exec python3 -m http.server "${PORT:-4173}" -d dist
