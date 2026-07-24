# Iteration 10 — Calibration Integrity Core

## Итоговая готовность: 74/100

## Что было сделано

По правилу 20/80 из всей Iteration 13 плана (Calibration/Metrics/Pose/Artifacts, 6% веса) выбран не самый заметный, а самый архитектурно сложный и научно рискозначимый срез: гарантия, что калибровочные данные с несовместимой происхождением (provenance) никогда не смешиваются и что запрещённые табличные поля физически не могут попасть в утверждённый калибровочный бандл.

1. **Новый модуль `ui/backend/dpo/calibration.py` — `CalibrationRegistry`.**
   - Калибровочный **Run Group** объединяет четыре роли: `main_extraction`, `calibration_extraction`, `calibration_build`, `main_analysis`.
   - Каждая роль регистрируется со своими `dataset_hash`, `code_hash`, `model_hash`, `config_hash`.
   - **Hash-consistency guard**: при регистрации новой роли её хэши сравниваются со всеми уже зарегистрированными ролями. Любое рассогласование по любому из четырёх измерений отклоняется сразу (`HashMismatchError`), без добавления участника — то есть смешивание никогда не проходит «по умолчанию», это fail-closed поведение. Ошибка называет точное измерение (`dataset_hash`/`code_hash`/`model_hash`/`config_hash`) и обе конфликтующие роли.
   - **Состояние**: `draft → candidate → approved/rejected`. `candidate` наступает автоматически, когда присутствуют все четыре роли и они согласованы. `approved`/`rejected` — терминальные и неизменяемые состояния; попытка изменить их выбрасывает `RunGroupStateError`.
   - **Approve** требует явного `approved_by` и фиксирует `bundle_hash` — SHA-256 по всем ролям и их хэшам. `verify_bundle_integrity` пересчитывает этот хэш от текущих сохранённых данных и сравнивает с зафиксированным — так можно обнаружить, что запись подменили после утверждения (проверено тестом с намеренной порчей файла).
   - **Trusted table attachment**: доверенная калибровочная таблица (уже прошедшая существующий классификатор `datasets.classify_field`) прикрепляется к Run Group только после **второй, независимой** проверки — `assert_trusted_only`. Она повторно ищет landmark/keypoint/mesh/vertex/coordinate поля в каждой строке и отклоняет прикрепление (`ForbiddenFieldError`), если хоть одно найдено — это защита от регрессии основного классификатора, а не дублирование той же логики.
   - Персистентность — JSON-файлы под `control_root/calibration_runs`, атомарная запись (tmp + replace), тот же паттерн, что у `LayoutStore`/`SnapshotStore`/`BackupManager`.
   - Модуль никогда не пишет в `app6` или dataset-корни — только в свой собственный control-plane каталог (проверено тестом).

2. **Семь новых REST-маршрутов в `main.py`**: `POST/GET /api/calibration/run-groups`, `GET /api/calibration/run-groups/{id}`, `POST .../members`, `POST .../table`, `POST .../approve`, `POST .../reject`, `GET .../verify`. Используют существующий `DatasetRegistry` для парсинга таблицы.

3. **11 новых тестов** в `ui/backend/tests/test_calibration.py`: согласованные хэши по всем ролям → `candidate`; рассогласование по каждому из четырёх измерений → отказ без слияния; неизвестная роль → отказ; изменение утверждённого/отклонённого Run Group → отказ; approve без всех ролей → отказ; approve фиксирует `bundle_hash`, порча файла после approve обнаруживается `verify_bundle_integrity`; reject после approve запрещён; прикрепление таблицы через реальный `DatasetRegistry.parse_calibration_table`; прикрепление таблицы со «просочившимся» координатным полем отклоняется; реестр не пишет за пределы своего корня.

## QA

- Backend regression: **72/72** (61 прежних + 11 новых), без warnings-as-errors нарушений.
- app6 regression: **65/65**, без изменений — модуль `calibration.py` не касается `app6`.
- `git diff --check`: чисто, конфликтов нет.
- `git status`: изменения только в `ui/backend/dpo/main.py`, `ui/backend/dpo/calibration.py` (new), `ui/backend/tests/test_calibration.py` (new) плюс документация.

## Честные ограничения

- **Проверено только синтетическими фикстурами.** Реального калибровочного датасета (7 человек, SDCARD) в этой песочнице нет — таблица и хэши в тестах придуманы для проверки контракта, а не подтверждают точность реальной калибровки.
- **Нет UI.** Run Group, approve/reject и bundle-hash доступны только через API/модуль, не через Calibration overlay в интерфейсе.
- **Нет автоматизации fresh extraction.** Модуль не запускает и не оркестрирует сами Stage 1 extraction прогоны — он только регистрирует их хэши постфактум и не даёт их смешать. Автоматическая привязка «main extraction + calibration extraction всегда запускаются вместе» — из плана Iteration 13 — не реализована.
- **Metric Explorer, Pose Lab, LOO sensitivity, dataset train/holdout split, sparse-cell/pose-coverage отчётность, Artifact previews** — полностью не реализованы, сознательно оставлены в backlog как отдельные, менее рискованные для научной достоверности задачи.
- Не проверено через живой HTTP-вызов или UI — только через unittest на модуль.

## Git

- Ветка `main`, коммит будет создан после этого отчёта.
- Push на `github.com` ожидаемо не пройдёт из-за отсутствия DNS в этой песочнице (повторяющееся, известное ограничение среды) — доставка через git bundle.
