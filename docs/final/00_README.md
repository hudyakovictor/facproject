# Пакет передачи проекта: forensic facial comparison 1999–2026

## Назначение

Это каноническая точка входа для разработчика, аналитика и рецензента. Проект измеряет воспроизводимость и хронологическую устойчивость 3D-геометрии лица; он **не** выносит автоматический вывод о личности. Любой флаг — повод для ручной проверки источника, даты, качества и реконструкции.

## Порядок чтения

1. `01_FINAL_REMEDIATION_PLAN.md` — порядок применения патчей и критерии готовности.
2. `02_VALIDATED_METHOD.md` — метод, выбранный экспериментами.
3. `03_PROVENANCE_AND_DATING.md` — обязательный контракт P1-8.
4. `04_DATA_CONTRACTS.md` — входы, выходы и версии схем.
5. `05_CALIBRATION_PROTOCOL.md` — семь персон, девять ракурсов, защита от контаминации.
6. `06_STATISTICS_AND_THRESHOLDS.md` — пороги, FDR, ESS, LOPO.
7. `07_TESTING_AND_ACCEPTANCE.md` — тестовая пирамида и release gates.
8. `08_UI_AND_REPORTING.md` — API/UI/экспорт/публичная безопасность.
9. `09_RESULTS_REGISTER.md` — числа всех раундов.
10. `10_RISK_REGISTER.md` — известные ограничения и запреты.
11. `11_OPERATIONS_RUNBOOK.md` — команды воспроизводимого прогона.
12. `12_DECISION_LOG.md` — почему приняты ключевые решения.
13. `13_STATIC_REVIEW_BACKLOG.md` — идеи, не проверяемые симулятором.
14. `14_FORENSIC_REVIEW_PROTOCOL.md` — порядок экспертной интерпретации.
15. `../FORENSIC_EXPERT_99_LEVEL_PROJECT_REVIEW_AND_UI_V5_PLAN.md` — Экспертное антропологическое и судебно-биометрическое заключение (Level 99 Forensic Facial Comparison Expert): 70 ключевых анализов бэкенда/старого UI, редизайн Таймлайна ui-v5, спецификация первых 10 страниц, Pair Analysis (95 баллов по 25 факторам), Кластеризация, Валидация гипотез (99 баллов по 150 факторам), Инфраструктура и Воронка Монетизации NFT на блокчейне (99 баллов по 150 факторам) и 10-этапный план реализации до 100% готовности.
16. `16_ITERATION_11_PLAN_TO_100_PERCENT.md` — План работ на Итерацию 11: 4 инженерных эпика для перехода от текущей стадии готовности (93.0 / 100 баллов по 18 факторам ТЗ) к 100.0 / 100 баллам (интеграция Live API бэкенда, DOM-виртуализация 1,900 строк, Web Worker и боевая BFM-топология).
17. `../articles/00_PUBLIC_ARTICLES_MONOGRAPH_SERIES.md` и `../articles/00_PUBLIC_ARTICLES_FULL_INDEX.md` — Серия из 10 научно-журналистских статей для широкой публики, СМИ и биометристов (от цифровой археологии 1999–2026 до 3DDFA_v3, 21 зоны, LOPO 7/7, байесовского суда H0/H1/H2 и NFT/Arweave), полный реестр 100% реализованных функций бэкенда (`app6/`, `uv_module/`, `3ddfa_v3`), 4 наглядных рендера и интерактивная витрина `/articles` в рабочей станции.
18. `18_COMPLETE_REMAINING_TASKS_BACKLOG.md` — Полный реестр оставшихся 15 инженерных задач для достижения 100.0 / 100 баллов боевой готовности, разбитых на 5 потоков (A: Live REST API & Cache, B: Виртуализация 1,900 строк & Web Worker, C: Бинарная 3D BFM-топология, D: Экспорт СМИ & PDF, E: Live E2E и Release Gate).

## Визуальные артефакты и коллажи
- `docs/final/nft_blockchain_9screens_collage.jpg` — Коллаж из 9 экранов (3x3): NFT-артефакты, блокчейн-провенанс, карточки парных сравнений, 10s loop video морфинга, SNR-графики и сертификаты.
- `docs/final/morphing_heatmap_filters_collage.jpg` — Коллаж демонстрации 3D-морфинга с фильтрами тепловой карты костных структур, UV-текстуры, ключевых точек (68/91/106) и зума хронологии.
- `docs/articles/renders/01_archaeology_provenance_render.jpg` — Научная иллюстрация цифровой археологии портретов и EXIF-аудита.
- `docs/articles/renders/02_3ddfa_bfm_geometry_render.jpg` — Иллюстрация 3D-реконструкции Basel Face Model, 21 зоны и Subset-91.
- `docs/articles/renders/04_uv_albedo_deepfake_render.jpg` — Иллюстрация нормализации UV-альбедо и детекции дипфейков.
- `docs/articles/renders/07_chronology_aba_return_render.jpg` — Иллюстрация кривой старения и возврата A->B->A.

## Что входит в пакет патчей

- raw object-normalized координаты как primary geometry channel;
- axis-specific pose-gap gate: yaw ≤6°, pitch ≤2°, roll ≤5°;
- NaN-safe utility и детерминированный subset из ровно 91 точки;
- FDR 0.05 и передача фактического числа откалиброванных точек;
- абсолютный порог для A→B→A, устраняющий ложное срабатывание на NULL;
- contamination-hardened same-day baseline;
- полная датировочная запись: имя файла — authority, EXIF — corroboration;
- `input_provenance.csv`, dataset/code/model/config hashes;
- семь регрессионных тестов критических исправлений.

## Статус

Патчи компилируются Python 3.11+; новые регрессионные тесты проходят 7/7. Полный end-to-end прогон требует локальных весов 3DDFA и основного фотодатасета. UI-тесты в переданном архиве нельзя запустить без переустановки Linux optional dependency Rollup; это release blocker, а не основание считать UI проверенным.
