#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH=. 

echo "Running route coverage audit..."

# Execute the smoke‑tests that verify all public routes are exercised.
.venv/bin/python -m pytest app6/api/tests/test_route_smoke.py app6/api/tests/test_route_parameterized.py -q

echo "Route coverage audit completed successfully."