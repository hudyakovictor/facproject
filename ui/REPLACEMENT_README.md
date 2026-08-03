# UI production replacement

This directory replaces the previous `ui` folder.

## Install and run

```bash
npm ci
npm run typecheck
python3 scripts/check_production_no_simulation.py
npm run build
```

Set `VITE_API_BASE_URL` when the API is not served from the same origin.

## Strict behavior

- Only `source_mode: research` timeline responses are accepted.
- Non-research photo, mesh and comparison payloads are rejected.
- Missing API/artifacts produce blocking unavailable/error states.
- No generated dataset, proxy PCA, drawn face, illustrative landmarks, static investigation event claims or embedded baseline is used.
- Export is blocked until verified research data are loaded.

## Backend prerequisite

The current supplied backend must expose research implementations for photo detail, mesh, comparison and calibration routes. This UI intentionally rejects its legacy demo-only responses instead of imitating successful analysis.
