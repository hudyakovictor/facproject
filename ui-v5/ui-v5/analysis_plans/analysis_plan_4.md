# План анализа и исправления UI v5 (анализ 4/50)

## Анализ 4: Health endpoint и диагностика данных

### Проблема P1: health не диагностирует data source
- `/api/v1/health` возвращает только schema/status/not_a_verdict, без roots, run и counts
- Пользователям нужно видеть: storage_root, stage1_ready, stage2_ready, photo_count, pair_count

### Решение:
1. Обновить health endpoint для включения полной диагностики
2. Добавить поля: storage_root, stage1_ready, stage2_ready, run_id, photo_count, pair_count
3. Добавить calibration_available и stage3_ready статус

### Проверка:
- `/api/v1/health` возвращает полный набор диагностических данных
- Все поля совпадают с реальным состоянием storage

### Приоритет: P1 (health не диагностирует data source)

### Шаги:
1. Найти определение health endpoint в server.py
2. Добавить поля диагностики
3. Проверить API-ответ

### Критерии завершения:
- Health endpoint возвращает storage_root, stage1_ready, stage2_ready, photo_count, pair_count
- Данные совпадают с реальным состоянием /Volumes/SDCARD/storage