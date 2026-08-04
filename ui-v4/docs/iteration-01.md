# Итерация 01 — runtime paths и инвентаризация

## Статус

Завершено. Интерактивный `backend/app6` является канонической кодовой базой UI.

## Каноническая раскладка

- Storage: `/Volumes/SDCARD/storage`
- Stage 1: `/Volumes/SDCARD/storage/stage1`
- Stage 2: `/Volumes/SDCARD/storage/stage2`
- Stage 3: `/Volumes/SDCARD/storage/stage3`
- Calibration: `/Volumes/SDCARD/calibration`
- Registry: `/Volumes/SDCARD/storage/registry`

Все пути переопределяются переменными окружения. Чтение конфигурации не создаёт каталоги и не изменяет Stage 1/calibration.

## Реализовано

- единый `RuntimePaths` для API, settings, health, jobs и reports;
- read-only inventory Stage 1 и calibration;
- проверка `main_timeline.csv`, manifests, photo IDs, pose bins и per-photo artifacts;
- подсчёты по годам и девяти ракурсам;
- SHA-256 индекса и manifests;
- атомарная регистрация активного dataset в `storage/registry/active_dataset.json`;
- UI-панель Stage 1/calibration в Data Manager;
- явные состояния `ready`, `limited`, `blocked/unavailable`.

## API

- `GET /api/v1/runtime/paths`
- `GET /api/v1/datasets/inventory`
- `POST /api/v1/datasets/activate`

## Переменные окружения

- `DEEPUTIN_STORAGE_ROOT`
- `DEEPUTIN_STAGE1_ROOT`
- `DEEPUTIN_STAGE2_ROOT`
- `DEEPUTIN_STAGE3_ROOT`
- `DEEPUTIN_CALIBRATION_ROOT`
- `DEEPUTIN_UPLOADS_ROOT`
- `DEEPUTIN_REGISTRY_ROOT`
- `DEEPUTIN_SETTINGS_PATH`

## Проверка

```bash
cd backend
python3 -m compileall -q app6
python3 -m unittest app6.test_module.test_iteration1_runtime_inventory -v
cd ..
npm run typecheck
```
