# DEEPUTIN UI v3

Новая тёмная forensic-станция (русский UI).

## Запуск

```bash
cd deeputin-ui-v3
npm install
npm run dev
```

Прокси `/api` → `http://127.0.0.1:8600`.

Опционально: `VITE_API_BASE`.

## Разделы

- Обзор, Хронология, Галерея, Инспектор
- Пары, Калибровка, Сводка прогона, Отчёт
- **Управление анализом**: extract (лимит/все), recompute, clear, jobs
- Настройки

## Исправления vs старый UI

- Реальные Stage 1 изображения вместо demo SVG
- artifact unavailable states
- Stage 1 keys в инспекторе
- Small-sample warning
- Раздел управления анализом
- JSON export без alert()
- not_a_verdict labels


## Дизайн v3 (без npm install)

Обновлены:
- `src/styles/global.css` — новая тёмная дизайн-система
- `src/components/Shell.tsx` — чище shell/навигация

Запуск у себя:
```bash
cd deeputin-ui-v3
npm install
npm run dev
```
