# 📌 TODO: ВОССТАНОВИТЬ ПОЛНУЮ ПЕРЕДАЧУ ДАННЫХ STAGE 2 → STAGE 3

**Создано:** 2026-08-27  
**Статус:** ⏸️ Отложено до новой версии Stage 2-3  
**Приоритет:** P0 (критично для нового отчёта)

---

## 📋 КОНТЕКСТ

Старый HTML отчёт будет удалён. Новый отчёт будет создаваться с нуля на основе новой версии Stage 2-3.

**Решено отложить** исправление передачи данных до момента когда будет готова новая версия этапов.

---

## 🚨 ЧТО НУЖНО ИСПРАВИТЬ

### Проблема:
Stage 2 записывает 13 глобальных артефактов, но Stage 3 их не читает.

### Критичные разрывы:

| # | Артефакт | Что содержит | Исправление |
|---|----------|--------------|-------------|
| 1 | `baseline_return.json` | Возвраты A→B→A | Добавить в pair_metrics.csv + Stage 3 читает |
| 2 | `cumulative_drift.json` | Накопленный дрейф | Добавить в pair_metrics.csv + Stage 3 читает |
| 3 | `alpha_chronology.json` | Temporal events | Stage 3 читает |
| 4 | `cross_bin_corroboration.json` | Global corroboration | Stage 3 читает |
| 5 | `pose_leakage_diagnostic.json` | Global pose leakage | Stage 3 читает |
| 6 | `multiple_testing.json` | FDR correction | Stage 3 читает |
| 7 | `evidence_packets.json` | Detailed evidence | Stage 3 читает |

### Усилия:
- Шаг 1: Добавить baseline_return в pair_metrics.csv (1 час)
- Шаг 2: Добавить cumulative_drift_status в pair_metrics.csv (1 час)
- Шаг 3: Stage 3 читает глобальные артефакты (2 часа)
- **Итого: 4 часа**

---

## 📊 ТЕКУЩЕЕ СОСТОЯНИЕ

### Что доходит:
- ✅ Stage 1 → Stage 2: ВСЕ данные доходят
- ✅ Stage 2 per-pair: ~140 полей через pair_metrics.csv
- ❌ Stage 2 global: 13 JSON файлов не читаются Stage 3

### Документация:
- `audit/STAGE2_TO_STAGE3_DATA_TRANSFER_AUDIT.md` — полный анализ

---

## 🎯 КОГДА ВЕРНЁМСЯ

**Триггер:** Готова новая версия Stage 2-3

**Действия:**
1. Прочитать `audit/STAGE2_TO_STAGE3_DATA_TRANSFER_AUDIT.md`
2. Реализовать 3 шага (4 часа)
3. Проверить что все данные доходят до нового отчёта

---

## 💡 ЗАМЕТКИ

### Роль Stage 2:
Stage 2 — **самый ответственный этап** в пайплайне:
- Считает первичные метрики (100 каналов)
- Определяет статусы (within_noise, geometric_change, etc)
- Строит калибровочные модели (noise references)
- Выявляет temporal events (baseline_return, drift)
- Применяет FDR correction (multiple testing)
- Определяет evidence state (что публикуется)

**Stage 3 только агрегирует и визуализирует** то что Stage 2 посчитал.

Если Stage 2 посчитал неправильно — Stage 3 покажет неправильные результаты.

### Почему Stage 2 критичен:
1. **Первичные данные:** Все метрики вычисляются здесь
2. **Калибровка:** Noise models строятся здесь
3. **Статусы:** Evidence determination происходит здесь
4. **Temporal analysis:** Chronology events выявляются здесь
5. **Quality gates:** Что публикуется решается здесь

Stage 1 только извлекает raw data.  
Stage 3 только показывает результаты.  
**Stage 2 считает и решает.**

---

**Создано:** 2026-08-27  
**Следующий шаг:** ⏸️ Ждём новую версию Stage 2-3
