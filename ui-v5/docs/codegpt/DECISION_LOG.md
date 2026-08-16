# Decision Log — CodeGPT (итерация «Release Gates»)

Префикс CD- (CodeGPT Decision). Существующие D-001…D-010 — в docs/final/12_DECISION_LOG.md.

| ID | Решение | Альтернативы | Причина | Затронутые файлы |
|---|---|---|---|---|
| CD-101 | Цель итерации — закрыть проверяемые release gates (docs/final/01,07,08), а не новый функционал | новая фича анализа / рефакторинг пайплайна | ТЗ проекта — зрелое; наибольшая ценность — доказуемая готовность и воспроизводимость | весь проект |
| CD-102 | API-тесты: pytest + FastAPI TestClient в `app6/api/tests/` (путь уже прописан в pyproject) | отдельный стенд / ручной smoke | нулевая стоимость интеграции, runtime-покрытие 36 маршрутов | pyproject.toml, app6/api/tests/* |
| CD-103 | ruff довести до 0 вручную (F401/UP035/F811/B007/UP017/B905/F841/S), а не `--fix` вслепую | автофикс | F811/F841 требуют понимания контекста; S603/S310 — решение по существу | app6/** |
| CD-104 | ui-v3: сгенерировать package-lock.json, добавить typecheck+build+минимальный vitest | удалить v3 / вернуться к v2 | v3 — целевой интерфейс; блокер воспроизводимости устраняется без смены стека | ui-v3/* |
| CD-105 | Public-term lint вынести в переиспользуемый модуль и применить к финальным артефактам | оставить только evidence packets | требование R-F02; блокирует publication build | новый модуль + stage3/export |
| CD-106 | Golden synthetic E2E fixture: детерминированный синтетический Stage1/Stage2/Stage3 + snapshot API/report/export | реальный прогон | весов и фото нет; синтетика покрывает сценарии ТЗ (9 bins, NULL, step, return, конфликты) | tests/e2e_fixture*, api/tests |
| CD-107 | CI: GitHub Actions с gates (pytest, ruff, ui-v2, ui-v3, lint, determinism) | Makefile-гейты | требуется автоматизация на push; среда GitHub позволит и реальный E2E по secrets | .github/workflows/* |
| CD-108 | Determinism harness: двойной прогон синтетики, сравнение hash quartet | разовый ручной замер | требование R-G04, документированный риск «Non-deterministic run» | tests/determinism* |
| CD-109 | НЕ менять 9 bins, primary coordinates, FDR, пороги — только добавлять проверки | — | D-001…D-010, запреты docs/final/10 | — |
| CD-110 | Итерация НЕ включает реальный E2E (LOPO, negative control, golden bundle) — блокировано отсутствием весов/фото | задержать релиз | данные недоступны в среде; фиксируется как открытое условие 95+ | — |
| CD-111 | Эксперименты (fuzzing parsers, mutation testing) — отдельно, с Leverage Index и откатом | в основной план | снижение риска дестабилизации зелёных gates | — |
| CD-112 | API-пути портируемы: env-first (DEEPUTIN_*), fallback в `runs/` проекта; `/Volumes/SDCARD` только как явный override | оставить как есть | ER-131/132: 500 и 400 на любой машине без этого пути; API-тесты в CI невозможны | api/settings.py, api/server.py, run_calibration.py |
| CD-113 | Единый источник atlas: каноничен `app6/atlas/pose_policy_v3_9bins.csv` (грузится пайплайном); устаревшую копию в 3ddfa_v3/atlas удалить, README исправить | мигрировать на 3ddfa_v3/atlas | разные схемы (exclude/limited vs primary) → риск тихой подмены политики | atlas/*, README.md |
| CD-114 | Калибровочный адаптер info.json→Record (нормализация из `normalization.center/scale`) + генератор all_calibration_index.csv | ждать весов | 943 кадра, 7 персон, 9 бинов уже в репо; открывает LOPO/contamination/negative control в CI без фото | loaders.py, tools/build_calibration_index.py |
| CD-115 | Narrative Stage 3 выводится из manifest/metric_catalog (кол-во наборов, семейств) | оставить захардкоженным | ER-144: «7 наборов/13 семейств» уже не совпадает с 6 семействами/100 метриками | stage3/engine.py |
| CD-116 | ui-v3 чинит контракт: run/keys → run/artifacts (совпадает с v2 и KEYS_IMPLEMENTATION.md); полнота forensических функций v3 (mesh/compare/health) — отдельный этап | добавить alias-маршрут run/keys | маршрут уже документирован; alias создал бы два пути к одному ресурсу | ui-v3/src/lib/api.ts, RunPage.tsx |

| CD-122 | Отмена всех новых SHA-256/hash-работ: C02 (assets manifest), C04 (hash-pinned downloader), C05 (единый hash quartet), Q01/Q02 (пересчёт/обязательность quartet), Q10 (file-hashes индекса), X04 (BFM cache hash), канонизация | делать | избыточно; существующее хэширование photo_id/ledger не трогаем | plan |
| CD-123 | Отмена D02/E04: detector recoverable error, независимый 2D fit, overlay review | делать | не требуется ТЗ | plan |
| CD-124 | Отмена всей UV-аналитики: R01/R02/R03/R07/R08/R09/S01/S02/S06/S09. UV — только визуализация на 3D-модели; анализ кожи — по face_mask.png | делать | решение пользователя | plan |
| CD-125 | Отмена X01 (кэш inventory) и X02 (расширение из info.json) | делать | не требуется | plan |
| CD-126 | UI-стратегия: v3 — единственный целевой интерфейс; функциональность v2 портируется в v3; план UI-1…UI-16 | два параллельных UI | один интерфейс проще поддерживать; v3 — современная основа | ui-v3/* |

| CD-127 | Приватный слой (private_hypothesis_seed + stage2b) включён в план как IT-18: интеграция legacy_bridge, тесты, fail-closed, переименование «confirmed_independently», seed-снимок с регенерацией в runs/ | оставить вне плана | пользователь требует охвата; слой содержит 6223 записей и влияет на Stage2B | IT-18 |