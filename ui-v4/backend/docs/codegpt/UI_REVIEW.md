# UI Review — v2 vs v3 (2026-08-03) и план улучшений

## Что есть в каждой версии

### ui-v2 (старая, «forensic-плотная»)
- 14 режимов: FULL (таймлайн), MATRIX, CLUSTER, ERA_COMPARE, COMPARE, PAIR_COMPARE, INSPECTOR, DRIFT, METRICS, STATS, CALIBRATION, RUN, REPORT, DATA.
- Богатый таймлайн: эры (eraMeta), playhead, CurrentStateBar, baseline API, скрытые кадры, размер миниатюр.
- Полноценный 3D: MeshViewer (three.js, полный BFM-меш 35 709 вершин, heatmap, KNN-линии, vectors), MorphPlayerOverlay (морфинг A→B), LazyMeshViewer (код-сплиттинг).
- Сравнение диапазонов (range A/B), HeatmapWorkbench (редактор градиента), NoiseCalibrationPanel (вычитание углового шума), SkinZonesPanel, ChronologyAnomalies, ProvenancePopup, DataManagementView (upload/clear), SettingsModal.
- i18n (ru/en, 1120 ключей), темы dark/light, гипотезная легенда H0/H1/H2 (устарела, M05).
- Минусы: 14 пунктов навигации — перегруз; шрифты 9–10 px mono; легенда H0/H1/H2 противоречит M05; настройки в модале без валидации.

### ui-v3 (новая, тёмная forensic-станция)
- 10 разделов: Обзор, Хронология, Галерея, Инспектор, Пары, Калибровка, Сводка прогона, Отчёт, Управление анализом, Настройки.
- Чистый Shell: чипы backend/фото/аномалии/режим/not-a-verdict; честные состояния (loading/error/empty), small-sample предупреждения, «—» вместо 0.
- Обзор: статистика, покрытие 9 бинов, последние кадры. Галерея: поиск/фильтр/флаги.
- Таймлайн: SVG-треки по 8 метрикам, разрыв линий на bin, фильтр ракурсов, список кадров.
- Инспектор: слои (original/face_crop/thumbnail/uv/zones), вкладки (сводка/keys/кожа/raw), prev/next, applicability-баннер, конфликт датировки.
- Пары: выбор A/B в одном бине, предпросмотр, JSON. Калибровка/Отчёт/Сводка: JSON-дампы.
- Управление: jobs с прогрессом, extract/recompute/clear. Настройки: JSON-текстарея.
- Минусы: нет 3D-инспектора и морфинга (ядро v2); JSON вместо таблиц; нет noise-калибровки; нет provenance popup; нет upload; нет analytics-режимов (matrix/drift/metrics/stats); нет i18n/theme/ErrorBoundary; RunPage бьёт в несуществующий `/api/v1/run/keys`.

## План улучшений (порт v2→v3, приоритизирован)

### UI-P0 — ядро рабочего процесса аналитика
| # | Идея | Что делает |
|---|---|---|
| UI-1 | 3D-инспектор в v3 | Порт LazyMeshViewer+full_mesh: вкладка «3D» в Инспекторе (меш, heatmap на 134 ландмарках, wireframe, векторы); MorphPlayer A→B для пары |
| UI-2 | Workspace пары | Сайд-бай-сайд: оригиналы + face_crop + оверлей ландмарков + heatmap; метрики-карточки (p95_z, points, gaps, FDR q, calibrated count), не JSON; «raw» — сворачиваемая вкладка |
| UI-3 | Рендер данных вместо JSON | Калибровка (health: 9 бинов × персоны × confidence — таблица), Отчёт (секции-компоненты, экспорт JSON/CSV/HTML), Сводка прогона (статусы стадий, ограничения), Пары (см. UI-2) |
| UI-4 | Настройки — типизированная форма | Секции (пороги heatmap, display/scientific, язык); слайдеры+валидация; JSON-редактор — advanced-вкладка; разделение display vs scientific порогов (Y02) |
| UI-5 | Починка RunPage | run/keys → run/artifacts; состояния ошибок/пустоты для каждого артефакта |

### UI-P1 — аналитическая глубина (порт из v2)
| # | Идея | Что делает |
|---|---|---|
| UI-6 | Таймлайн v2-класса | Эры-сегменты, маркеры аномалий/флагов/EXIF-конфликтов, baseline-линия, playhead+CurrentStateBar, тултипы, brush-выбор диапазонов A/B (для ERA_COMPARE) |
| UI-7 | Analytics-режимы | Matrix (фото×фото heatmap по p95_z внутри бина), Drift (пер-биновые ряды), Metrics/Stats (гистограммы качества, распределения z, ESS/CI, FDR-сводка) |
| UI-8 | Noise calibration | Порт NoiseCalibrationPanel: подбор калибровочной пары, вычитание шума, before/after, coverage-отчёт |
| UI-9 | Provenance popup | Порт ProvenancePopup: sidecar, EXIF-конфликт, delta days, near-duplicate, chain-of-custody; открытие из Инспектора/Галереи |
| UI-10 | Upload/ingest | Drag&drop в «Управление анализом»: превью имени (YYYY_MM_DD), валидация, sidecar-поле, пофайловый статус; замена отсутствующего upload в v3 |
| UI-11 | DataManagement | Список run (stage1/2/3 roots), readiness-статусы, очистка с подтверждением и маркером output-root, экспорт-бандл (JSON+CSV+HTML) с not_a_verdict-вотермаркой |

### UI-P2 — операции и UX-инфраструктура
| # | Идея | Что делает |
|---|---|---|
| UI-12 | ErrorBoundary + хоткеи | ErrorBoundary (как в v2), клавиши ←/→ в инспекторе, `/` фокус поиска, `g` галерея, `t` таймлайн; aria-метки |
| UI-13 | i18n + theme | Порт i18n (ru/en, сокращённый ~300 ключей); тёмная/светлая тема; размер миниатюр |
| UI-14 | Обзор: статус пайплайна | Чипы стадий S1/S2/S3 (ready/blocked/absent), гистограмма качества, покрытие бинов графиком, ETA активных jobs |
| UI-15 | Candidate-легенда | Легенда статусов (persistent_geometric_change_candidate, same_day_conflict_candidate, quality_limited, …) вместо H0/H1/H2; цвета закреплены |
| UI-16 | Глобальный поиск | Ctrl+K: поиск по фото/парам/датам/ведущим (leads) из любого раздела |

## Принципы (наследуются из v2 и docs/final/08)
null/исключено ≠ 0 · not_a_verdict всегда видим · «TEST SUBSET» предупреждение · артефакт недоступен — честное состояние · candidate не становится утверждением · экспорт версионирован.

## Статус
План UI-1…UI-16 принят голосованием (циклы 131–136). Файлы: ui-v3/src/pages/*, ui-v3/src/components/*, ui-v3/src/lib/api.ts (фикс run/keys).