#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d node_modules ]]; then
  echo "Установка зависимостей UI…"
  npm ci
fi
exec npm run dev -- --port "${PORT:-5173}"
