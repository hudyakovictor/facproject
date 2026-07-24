# UI Iteration 1 — Foundation, external storage and project boundaries

## Статус

**Завершено. Общая готовность UI: 7/100 (7%).**

Процент относится к реализации всего UI по взвешенному плану из 17 итераций. Документация и архитектурная идея не считаются готовым функционалом автоматически.

## Реализовано

### Backend core

- Типизированная YAML/env-конфигурация.
- Относительные пути разрешаются от `ui/`.
- Неуказанный calibration root не угадывается.
- Запрещён local fallback тяжёлых данных.
- Защита от пересечения `app6`, datasets и heavy output.
- Storage Manager для `/Volumes/SDCARD/uidata`.
- Проверки mount, identity, write access, free space и interruption.
- Создание только разрешённых heavy directories.
- Dataset Registry без копирования фотографий.
- Fingerprint по относительному пути, размеру и mtime.
- Trust policy калибровочной таблицы.
- Координаты landmarks/keypoints/mesh исключаются.
- Pair bindings и yaw/pitch/roll сохраняются.
- Компактная SQLite WAL control database.
- CLI `health` и `init-storage`.
- FastAPI adapter `/api/health` и `/api/project`.

### Frontend foundation

- React/TypeScript/Vite shell.
- Journalist-first overview.
- Состояние app6, SDCARD, main и calibration datasets.
- Понятные описания ошибок хранения.
- Явная отметка read-only режима app6.
- Responsive и reduced-motion основы.

### Тесты

Проверяются:

- resolution путей;
- отсутствие догадок о calibration root;
- запрет local fallback;
- source/output overlap;
- storage initialization;
- wrong-volume fail-closed;
- disconnect recovery;
- запрет координат из таблицы;
- pair/angle-only trust;
- photo registry без копирования;
- SQLite WAL migration;
- агрегированный project health.

## Ограничения среды

В текущем sandbox отсутствуют FastAPI, Uvicorn, Vite и npm-пакеты frontend. Они объявлены в `pyproject.toml`/`package.json`. Framework-independent backend core и unittest suite запускаются без них. Полный API/browser smoke выполняется после установки зависимостей на рабочей машине.

## Exit criteria

- [x] Backend core запускается документированной командой.
- [x] Health показывает app6/storage/datasets/database.
- [x] UI не пишет в app6.
- [x] Heavy output не имеет local fallback.
- [x] Storage failure блокирует heavy run.
- [x] Main и calibration datasets регистрируются без копирования фото.
- [x] Координаты из calibration table исключены.
- [x] Frontend shell реализован.
- [x] Unit tests проходят: 14/14 UI backend.
- [x] App6 regression проходит: 65/65.
- [x] React/TypeScript source syntax проходит: 4/4 файла.
- [x] YAML/JSON configuration parse проходит.

## Следующая итерация

Iteration 2: read-only AST Indexer — модули, функции, сигнатуры, docstrings, source locations, static edges и incremental reindex.
