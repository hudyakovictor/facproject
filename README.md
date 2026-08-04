# DEEPUTIN — Face Analysis Pipeline

Проект состоит из трёх основных компонентов:
- **`3ddfa_v3/`** — 3DDFA_V3: 3D реконструкция лица (форк [wang-zidu/3DDFA-V3](https://github.com/wang-zidu/3DDFA-V3))
- **`app6/`** — Основной пайплайн анализа: Stage 1 (извлечение), Stage 2 (парный анализ), Stage 3 (отчёт)
- **`ui/`** — Веб-интерфейс (Vite + React + TypeScript)

**Важно:** Все команды запуска — через `/Users/victorkhudyakov/work/.venv/bin/python`

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
| `3ddfa_v3/atlas/` | ✅ Данные | UV-atlas (схемы, политики, зоны) — **основное место** |

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

[Подробнее →](app6/README.md)
[3DDFA_V3 документация →](3ddfa_v3/README.md)
[UI документация →](ui/README.md)
