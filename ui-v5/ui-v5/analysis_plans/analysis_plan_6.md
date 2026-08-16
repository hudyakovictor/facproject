# План анализа и исправления UI v5 (анализ 6/50)

## Анализ 6: TypeScript проверка и сборка

### Проблема: verify не зелёный (было 11 failed, стало 0 failed)
- Ранее падали: clustering, RouterProvider resilience, null/zero, timeline filters и menus
- После исправлений: все 229 тестов проходят, typecheck чистый, lint 0 ошибок, design-gate пройден

### Что было сделано:
1. **P0** - Исправить `_stage2_root()` в server.py для поиска Stage 2 в `/Volumes/SDCARD/storage/stage2_resumable_20260816`
2. **P2** - Обновить `get_photo_landmarks()` для чтения из JSON fallback когда CSV файлы недоступны
3. **P1** - Убрать `.catch()` из Zod схем в `shared/api/schemas.ts` (осталось 11 изначально 50+)
4. **P1** - Обновить health endpoint для включения полной диагностики данных

### Проверка:
- `npm run verify` = typecheck + lint + design-gate + mock-audit проходят
- `npm run dev` = vite работает с реальными данными
- 229 Vitest тестов зелёные

### Приоритет: P3 (тесты и сборка)

### Критерии завершения:
- `npm run verify` проходит без ошибок
- Все тесты проходят
- Бэкенд корректно работает с реальным storage
- UI может отображать реальные данные из Stage 2