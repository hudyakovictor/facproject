# План анализа и исправления UI v5 (анализ 1/50)

## Ключевые проблемы (P0-P3)

### P0 - Хранение данных
1. **Проблема**: Бэкенд не выбирает правильный Stage 2 run из `/Volumes/SDCARD/storage`
   - `server.py:137-140` ищет `PROJECT_ROOT/calibration_dataset`, а данные в storage
   - `_stage2_root()` не находит `analysis_manifest.json` в `stage2_resumable_20260816`
2. **Решение**: 
   - Исправить `_stage2_root()` в `server.py` для поиска в `/Volumes/SDCARD/storage/stage2_resumable_20260816`
   - Добавить проверку наличия `analysis_manifest.json` в Stage 2

### P1 - API-контракты
1. **Проблема**: Zod схемы не блокируют неверные ответы (`.catch()` скрывает ошибки)
   - `shared/api/schemas.ts:115+` превращает ошибки в null/default
2. **Решение**:
   - Убрать `.catch()` из Zod схем
   - Добавить валидацию на сервере (pydantic)
   - Сделать ошибки 400/422 вместо null

### P2 - Визуализация
1. **Проблема**: Canvas counts нестабильны (4/12 vs 6/18)
   - `timelineMenus.test.tsx` ожидает 4/12 canvas, получает 6/18
2. **Решение**:
   - Объединить x-mapping для selection, pair endpoints, tooltip и year ruler
   - Добавить unit-тесты для виртуализации

### P3 - Тесты и сборка
1. **Проблема**: 11 failed Vitest, verify не зелёный
   - Падают: clustering, RouterProvider resilience, null/zero, timeline filters
2. **Решение**:
   - Исправить 11 failing тестов
   - Добавить проверку виртуального хранения (virtualizer invariants)

## Приоритеты выполнения

1. **P0.1** - Исправить выбор Stage 2 данных (server.py)
2. **P0.2** - Проверить доступ к артефактам из реального storage
3. **P1** - Исправить Zod схемы и API-контракты
4. **P2** - Исправить визуализацию canvas counts и virtualization
5. **P3** - Исправить failing тесты (11 шт.)

## Следующие шаги

1. Проверить, что бэкенд корректно работает с `/Volumes/SDCARD/storage`
2. Настроить правильный выбор Stage 2 в server.py
3. Проверить API-эндпоинты с реальными данными
4. Запустить UI и проверить визуализацию