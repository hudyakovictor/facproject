"""📦 PACKAGE → DEEPUTIN forensic workstation API (`app6/AGENTS.md` §"Судебно-медицинская рабочая станция").

Реализует `/api/v1/*` для `ui/` (см. `ui/API_CONTRACT.md`). Работает в двух
режимах, оба явно помечены в ответах через `source_mode`:

- ``demo`` — `DEEPUTIN_STAGE1_ROOT`/`DEEPUTIN_STAGE2_ROOT` не заданы или не
  содержат валидного вывода Stage 1/2. Отдаётся синтетическая, но
  геометрически честная хронология (`demo_data.py`, `timeline.py`),
  вычисленная тем же кодом `app6.stage2.core`, что и Stage 2.
- ``research`` — переменные окружения указывают на настоящий вывод Stage 1
  (`main_timeline.csv`) и/или Stage 2 (`analysis_manifest.json`); тогда API
  отдаёт реальные записи вместо демо-генератора.

Ни один режим не публикует вердикт о личности — см. `app6/AGENTS.md`.

Запуск: ``uvicorn app6.api.server:app --host 0.0.0.0 --port 8000``
(см. `app6/api/README.md` и `RUN_PROJECT.sh api`).
"""
from __future__ import annotations
