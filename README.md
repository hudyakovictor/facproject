# DEEPUTIN — Face Analysis Pipeline

## Публичная версия для ревью

GitHub-снимок проекта намеренно урезан: исходный код, документация и тесты
сохранены, а извлечённые данные представлены небольшим реальным fixture в
[`fixtures/public-sample`](fixtures/public-sample). Для трёх кадров там оставлен
полный набор артефактов, включая 3D-модели OBJ/MTL, NPZ, текстуры, маски,
landmarks и метаданные; это позволяет проверять отображение и находить ошибки.

Полная локальная версия продолжает работать с данными Stage1/Stage2 на
`/Volumes/SDCARD/storage`. В GitHub не загружаются веса моделей, полный массив
извлечённых данных и локальные результаты запусков. Это ограничение публичной
копии, а не отсутствие этих данных в локальной установке.

Пересобрать пример из локальных данных можно командой:

```bash
python3 tools/build_public_fixture.py
```

DEEPUTIN — исследовательская workstation для продольного технического сравнения фотоархива 1999–2026. Она извлекает и визуализирует геометрию, landmarks, pose, visibility, provenance, quality и хронологические измерения. Автоматический статус является наблюдением/кандидатом на ручную проверку, **не вердиктом о личности**.

Основные компоненты:

- **`3ddfa_v3/`** — 3DDFA_V3: 3D-реконструкция лица (форк [wang-zidu/3DDFA-V3](https://github.com/wang-zidu/3DDFA-V3));
- **`app6/`** — Stage 1 (извлечение), Stage 2 (парный/хронологический анализ), Stage 2B (private retest), Stage 3 (отчёт) и FastAPI;
- **`ui-v5/`** — целевой интерфейс; создан runnable foundation и внутренний раздел `/design-system`, исходные дизайн-рендеры сохранены в `ui-v5/screens/`;
- **`docs/final/`** — валидированные методические и data contracts.

Используйте активное локальное Python-окружение (`.venv/bin/python` или явно заданный `$PYTHON`). Абсолютный путь владельца `/Users/victorkhudyakov/work/.venv/bin/python` допустим в его локальной среде, но не является переносимым контрактом репозитория.

Перед разработкой прочитайте [`AGENTS.md`](AGENTS.md), [`SKILL.md`](SKILL.md) и, при работе через Claude Code, [`CLAUDE.md`](CLAUDE.md).

Быстрый запуск UI v5:

```bash
cd ui-v5 && npm ci
cd .. && ./RUN_PROJECT.sh ui
```

Первый внутренний маршрут: `http://localhost:4175/design-system`.

---

## 📦 Файлы локально / не в репозитории

Следующие файлы и директории существуют только локально (игнорируются `.gitignore`).
Их нужно воспроизвести или скопировать при развёртывании на другой машине.

### Веса моделей — `/3ddfa_v3/assets/`

| Файл | Размер | Назначение |
|------|--------|------------|
| `face_model.npy` | 99 MB | BFM-топология (35709 вершин) |
| `net_recon.pth` | 92 MB | ResNet-50 реконструкция (основная) |
| `net_recon_mbnet.pth` | 12 MB | MobileNet-V3 реконструкция (быстрая) |
| `large_base_net.pth` | 27 MB | Крупная базовая сеть |
| `retinaface_resnet50_*.pth` | 104 MB | Детектор лиц |
| `similarity_Lm3D_all.mat` | 1 KB | Матрица сходства ландмарок |
| `face_model.tar.gz` | 86 MB | BFM-архив |
| `indices_*.npy` | ~140-286 KB | Индексы соответствия вершин |
| `meanshape-*.obj` | ~5 MB | Mean-shape меши (106/134/68 лдм) |

### Фото — `/calibration_dataset/photos/`

| Директория | Размер | Содержание |
|------------|--------|------------|
| `person_01/` … `person_07/` | ~100 MB | Исходные фото для калибровки (943 шт) |

### Runtime — `/Volumes/SDCARD/storage`

| Файл/папка | Размер | Назначение |
|------------|--------|------------|
| `api_settings.json` | — | Настройки API-сервера |
| `api_uploads/` | — | Загруженные через API фото |
| `bfm_cache/` | ~100 MB | Кэш BFM-модели |
| `stage1/` | — | Результаты Stage 1 (извлечение) |
| `stage2/` | — | Результаты Stage 2 (парный анализ) |
| `stage2b/` | — | Результаты Stage 2B (пост-обработка) |
| `stage3/` | — | Результаты Stage 3 (отчёт) |

> ⚠️ **ВАЖНО:** Все данные пайплайна сохраняются ТОЛЬКО в `/Volumes/SDCARD/storage`. Никогда не сохраняйте данные локально в проекте.

### Тестовые данные

| Файл | Размер | Назначение |
|------|--------|------------|
| `testphoto/` (в корне) | — | Набор тестовых фото для быстрой проверки |
| `.venv/` | — | Виртуальное окружение Python 3.11 |

---

## 🗑 Локальные файлы (не в git)

| Путь | Статус | Комментарий |
|------|--------|-------------|
| `runs/` | ✅ Runtime | Настройки API, загрузки, кэш BFM (~100 MB) |
| `docs/PROJECT_STATUS_FOR_JOURNALIST.md` | ✅ Документ | Статус-отчёт проекта |
| `app6/scripts/fetch_external_assets.py` | ✅ Оставить | Загрузка весов при развёртывании |
| `3ddfa_v3/atlas/` | ✅ Данные | Вендоренные atlas/metadata 3DDFA; канонические analysis policies находятся в `app6/atlas/` |

---

## 🖥 Целевой стек UI v5

Архитектурное решение зафиксировано для будущей реализации:

```text
React 19 + strict TypeScript + Vite
TanStack Router + Query + Table + Virtual
Zustand + zundo
Radix UI + CSS Modules + design tokens
DOM + Canvas 2D + d3-scale/array/shape для timeline
Three.js + React Three Fiber + GLSL для 3D/morphing
Web Workers + Comlink + OffscreenCanvas
React Hook Form + Zod
OpenAPI-generated client
FastAPI + Pydantic + Python analytics
SSE для progress/jobs
Vitest + RTL + MSW + Playwright + axe
```

Почему именно этот стек и правила по каждому модулю подробно описаны в [`ui-v5/README.md`](ui-v5/README.md). Полная карта страниц, controls, API и этапов реализации до 100%: [`docs/UI_V5_COMPLETE_IMPLEMENTATION_SPEC.md`](docs/UI_V5_COMPLETE_IMPLEMENTATION_SPEC.md). Приоритетный roadmap специализированных forensic/statistical methods: [`docs/SPECIALIST_METHODS_ROADMAP.md`](docs/SPECIALIST_METHODS_ROADMAP.md).

### MacBook M1

Нужно различать два независимых compute path:

1. **3DDFA Stage 1:** по текущей validated policy работает на CPU; PyTorch MPS не включается без отдельной проверки bundled renderer и численной эквивалентности.
2. **UI morphing/3D:** выполняется на Apple GPU через WebGL2/Three.js в браузере. CUDA и PyTorch MPS здесь не нужны. A/B vertices находятся в GPU buffers, а scrubber обновляет shader uniform. WebGPU может быть добавлен позже только как progressive enhancement; WebGL2 остаётся baseline.

Интерполированный morph frame является только визуализацией и никогда не создаёт новую точку измерения Stage 2.

### UI v5 design synthesis

По результатам оценки 23 рендеров:

- timeline: R23 + R04 + R21 + R05;
- Pair Analysis: R19 + R18 + R11;
- Morphing: R20 + R10;
- Clustering: R15 + R12, R13 как secondary mode;
- Hypothesis Validation: R16 + R17.

Полная 19-факторная оценка: [`docs/UI_V5_RENDER_REVIEW_19_FACTORS_2026-08-05.md`](docs/UI_V5_RENDER_REVIEW_19_FACTORS_2026-08-05.md).

## 📰 Публикационные черновики

Stage 2 формирует `journalist_handoff.json`, а Stage 3 — детерминированный пакет `drafts/` для четырёх аудиторий:

- понятный method explainer для широкой аудитории;
- technical appendix для специалистов;
- skeptic Q&A с альтернативами и falsification tests;
- machine-review packet и claims ledger для воспроизводимой AI/static проверки;
- results story draft для совместной работы журналиста и технического редактора.

Это черновики, а не готовые статьи и не автоматический verdict. Каждая числовая формулировка должна сохранять denominator, evidence refs, limitations и review state. Подробный контракт: [`docs/PUBLICATION_PIPELINE.md`](docs/PUBLICATION_PIPELINE.md). Текущая структурная оценка по 25 факторам: [`95/100`](docs/PUBLICATION_PIPELINE_25_FACTOR_REVIEW.md); реальный редакционный approval оценивается только после production run и human review.

---

## 📐 Структура `app6/`

```
app6/
  run_stage1.py          — 🚪 Извлечение данных (3DDFA inference)
  run_stage2.py          — 🚪 Парный анализ
  run_stage2b.py         — 🚪 Пост-обработка Stage2
  run_stage3.py          — 🚪 Финальный отчёт
  run_calibration.py     — 🚪 Калибровка
  run_preflight.py       — 🚪 Предзапусковая проверка
  run_scenario_planner.py— 🚪 Планировщик сценариев
  stage1/                — Stage 1: извлечение
  stage2/                — Stage 2: анализ
  stage2b/               — Stage 2B: пост-обработка
  stage3/                — Stage 3: отчёт
  api/                   — Backend API (FastAPI)
  scripts/               — Утилиты
  schemas/               — JSON-схемы
```

- [Подробнее об app6 →](app6/README.md)
- [3DDFA_V3 документация →](3ddfa_v3/README.md)
- [Целевой UI v5 и стек →](ui-v5/README.md)
- [Правила для агентов →](AGENTS.md)
- [25-факторный implementation skill →](SKILL.md)
