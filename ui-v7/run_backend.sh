#!/usr/bin/env bash
# Run backend server

cd "$(dirname "$0")/backend"
source .venv/bin/activate 2>/dev/null || /opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload