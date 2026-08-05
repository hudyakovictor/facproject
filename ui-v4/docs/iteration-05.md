# Итерация 05 — запуск Stage 2 → Stage 3 по профилю

## Статус

Завершена реализация и статическая проверка. Тяжёлый расчёт основного датасета намеренно не запускался без выбранного и замороженного пользователем профиля.

## Цель

Запускать расчёт только по явно подготовленной выборке, сохранять связь результата с профилем и не изменять готовые Stage 1 и calibration.

## Реализовано

### Профиль как обязательный вход

- расчёт доступен только при наличии замороженного `selection_manifest.json`;
- пустая выборка и незамороженный manifest отклоняются до запуска;
- неизвестные идентификаторы фотографий отклоняются Stage 2;
- Stage 2 загружает готовый Stage 1, затем оставляет только `included_ids`;
- digest manifest входит в конфигурацию и итоговый manifest Stage 2.

### Единый analysis run

- один job последовательно выполняет Stage 2 и Stage 3;
- результаты каждого запуска изолированы в отдельном каталоге `storage/analysis_runs/<run_id>/`;
- перед расчётом сохраняется snapshot замороженной выборки;
- Stage 3 запускается только после успешной validation Stage 2;
- итоговый `run_summary.json` связывает профиль, выборку и результаты обоих этапов;
- Stage 1 и calibration используются только для чтения.

### API

- `POST /api/v1/profiles/{profile_id}/analysis-runs`;
- требуется явное `confirm_frozen_selection=true`;
- ответ содержит job id, run id и количество включённых фотографий;
- состояние выполнения доступно через существующий `/api/v1/jobs`.

### UI

- в Analysis Profiles добавлена кнопка **Рассчитать Stage 2 + Stage 3**;
- кнопка доступна только после заморозки выборки;
- после запуска показываются идентификатор задания и размер выборки;
- прогресс и журнал видны в Data Manager.

## Gates

- [x] Stage 1 не переизвлекается
- [x] calibration не переизвлекается и не изменяется
- [x] запуск без замороженного профиля невозможен
- [x] Stage 2 получает только включённые фотографии
- [x] Stage 3 не запускается при невалидном Stage 2
- [x] каждый запуск хранит snapshot выборки
- [x] frontend typecheck и production build проходят
- [x] регрессия итераций 1–4 проходит

## Проверка

```bash
cd backend
PYTHONPATH=. /Users/victorkhudyakov/work/.venv/bin/python -m unittest \
  app6.test_module.test_iteration1_runtime_inventory \
  app6.test_module.test_iteration2_dataset_timeline \
  app6.test_module.test_iteration3_selection_filters \
  app6.test_module.test_iteration4_analysis_profiles -v

cd ..
npm run typecheck
npm run build
```

## Следующая итерация

Итерация 06: preflight выбранного профиля, расчётная оценка количества пар и времени, подробный мониторинг фаз, безопасная отмена между фазами и переключение интерфейса на завершённый run.
