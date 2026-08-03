"""Пакет DEEPUTIN forensic workstation API.

Реализует `/api/v1/*` для `ui/` (см. `ui/API_CONTRACT.md`) и отдаёт только
реальные исследовательские данные из Stage 1/Stage 2. Ни один режим не
публикует вердикт о личности — см. `app6/AGENTS.md`.

Запуск: ``uvicorn app6.api.server:app --host 0.0.0.0 --port 8000``
(см. `app6/api/README.md` и `RUN_PROJECT.sh api`).
"""
from __future__ import annotations
