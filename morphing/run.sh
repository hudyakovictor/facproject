#!/usr/bin/env bash
set -e

echo "=========================================="
echo "🎭 Запуск 3D Face Morphing (app8 + uv_module)"
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 1. Запуск Backend API (FastAPI) на порту 8000
echo "🚀 Запуск FastAPI бэкенда на http://localhost:8000 ..."
python3 -m uvicorn morphing.backend.server:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Всегда завершаем backend вместе с frontend (в том числе при Ctrl-C).
cleanup() {
    kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# 2. Проверка Node модулей и запуск Frontend (Vite) на порту 3000
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "📦 Установка npm зависимостей..."
    npm install
fi

echo "✨ Запуск React/Three.js фронтенда на http://localhost:3000 ..."
npm run dev -- --host 0.0.0.0 --port 3000
