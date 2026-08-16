# DEEPUTIN API — судебно-медицинская рабочая станция

Реализует `/api/v1/*`, описанный в `ui/API_CONTRACT.md` и разделе
"Судебно-медицинская рабочая станция" `docs/техническое задание проекта/aboutplatform.txt`.

## Установка и запуск

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r app6/api/requirements.txt
uvicorn app6.api.server:app --reload --port 8000
# или
./RUN_PROJECT.sh api
```

Открыть `http://localhost:8000/docs` для интерактивной спецификации (Swagger UI).

## Режимы данных

API всегда явно указывает `source_mode` в ответе:

- **`research`** — `DEEPUTIN_STAGE1_ROOT` и/или `DEEPUTIN_STAGE2_ROOT`
  указывают на каталоги с реальным выводом пайплайна. Тогда `/api/v1/timeline`
  и связанные эндпоинты строятся из настоящих записей Stage 1/2.

Если вывод отсутствует, API отвечает ошибкой с объяснением, а не подменяет
данные синтетикой.

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `DEEPUTIN_STAGE1_ROOT` | Каталог вывода Stage 1 (`main_timeline.csv`) |
| `DEEPUTIN_STAGE2_ROOT` | Каталог вывода Stage 2 (`analysis_manifest.json`) |
| `DEEPUTIN_CALIBRATION_ROOT` | По умолчанию `calibration_dataset/` |
| `DEEPUTIN_UPLOADS_ROOT` | По умолчанию `runs/api_uploads/` |

## Основные эндпоинты

- `GET /api/v1/timeline` — хронология для главного таймлайна UI.
- `GET /api/v1/photos`, `GET /api/v1/photos/{id}`, `POST /api/v1/photos/upload`,
  `DELETE /api/v1/photos/{id}` — управление фотографиями.
- `GET /api/v1/photos/{id}/mesh` — **полный BFM-меш** фото: 35 709 вершин,
  70 789 треугольников (реальная топология `3ddfa_v3/assets/face_model.tar.gz`,
  без запуска нейросети — линейная реконструкция формы из уже известного
  `alpha_id`). HTTP 503, если BFM-геометрия недоступна в окружении.
- `POST /api/v1/compare` — реальное геометрическое сравнение двух записей
  (Kabsch-выравнивание + per-point residual для тепловой карты, 134
  landmarks), без повторного 3DDFA inference.
- `POST /api/v1/compare/full_mesh` — то же самое на **полной BFM-топологии**
  (identity-only, alpha_exp=0): `vertices_a`, `vertices_b_aligned` (для
  линейного морфинга A→B на фронтенде), per-vertex residuals, подлинные
  треугольники.
- `GET /api/v1/calibration/health` — здоровье калибровочной базы (реальные
  943 записи `calibration_dataset/all_calibration_index.csv`, 7 персон × 9
  ракурсов), категории уверенности `invalid/low/medium/high`.
- `GET /api/v1/calibration/match` (`photo_id` или `yaw`/`pitch`/`roll`) —
  подобрать ближайшие калибровочные кадры по углам позы для вычитания
  углового шума (ранжирование по метаданным индекса).
- `POST /api/v1/jobs` (`kind: extract | recompute_metrics`),
  `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `POST /api/v1/jobs/{id}/cancel`
  — пакетные задания. Если веса 3DDFA_V3 отсутствуют, задание получает
  честный терминальный статус `blocked` с причиной, а не имитирует успех.
- `GET /api/v1/system/health` — CPU/RAM/GPU/зависимости/веса моделей,
  доступность BFM-геометрии (`bfm_geometry_available`).
- `GET|PUT /api/v1/settings`, `POST /api/v1/settings/reset` — пороги
  тепловой карты и прочие UI-настройки, персистентно на диске.
- `POST /api/v1/data/clear` — очистить извлечённые данные (`runs/api_stage1`,
  `runs/api_stage2`) без удаления исходных фото с диска.

## Тесты

```bash
python3 -m pytest app6/api/tests -q
```
