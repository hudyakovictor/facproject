# Большой план следующей итерации после Timeline V3

## Формат итерации

Следующая передача должна быть не микропатчем на 5 минут, а завершённым вертикальным срезом. Оценочный объём: **5–8 рабочих дней**, с промежуточными контрольными точками. Пока не пройдены acceptance gates, новые разделы приложения не создаются.

## Цель

Превратить V3 из чистого layout в исследовательский инструмент, где один pose-bin можно проверить от исходного кадра до reportable/non-reportable pair evidence без ложных выводов.

---

## Этап 1. Нормативный data contract — 1 день

1. Создать `timeline-data-contract.ts`.
2. Разделить сущности `PhotoObservation`, `PairMeasurement`, `PairEvidence`, `TimelineEvent`.
3. Убрать legacy `anomalyScore`, `hasAnomalies`, `anomalyFlags` из frontend model.
4. Ввести discriminated unions для measurement status.
5. Ввести отдельный evidence state.
6. Описать `null`, `excluded`, `not_measurable`, `not_calibrated`.
7. Добавить runtime validation JSON/CSV.
8. Логировать неизвестные статусы без подмены значений.
9. Добавить version поля data contract.
10. Создать fixtures: reportable candidate, limited pair, null metrics, same-day, duplicate.

**Gate 1:** ни один UI-компонент не определяет evidence state самостоятельно.

## Этап 2. Track registry — 1 день

1. Создать registry всех допустимых дорожек.
2. Для каждой дорожки указать source field, unit, domain, scale, null policy.
3. Разделить evidence, measurement, QC и provenance categories.
4. Установить default tracks: calibrated effect и support.
5. Запретить произвольную custom metric без registry.
6. Добавить direct label, tooltip definition и legend symbol.
7. Реализовать разрыв линии на null.
8. Реализовать robust domain без обрезания выбросов молча.
9. Добавить reference lines calibration median/P95.
10. Добавить off-scale markers.

**Gate 2:** каждый пиксель графика можно связать с backend field и unit.

## Этап 3. Event/role lanes — 1–1.5 дня

1. Формализовать роль A/B/A-B отдельно от события.
2. Реализовать event priority registry.
3. Добавить два ряда событий с автоматическим stacking.
4. Исключить overlap иконок.
5. Объединить same-day frames в локальный stack без изменения общей сетки.
6. Добавить раскрытие stack по click/keyboard.
7. Развести date conflict, duplicate, invalid, candidate, limitation.
8. Добавить иконки, различимые без цвета.
9. Добавить legend popover.
10. Добавить multi-event hover с полным списком.
11. Реализовать keyboard focus и aria-label.
12. Добавить фильтрацию событий без изменения расположения фото.

**Gate 3:** пользователь понимает каждую иконку без открытия кода.

## Этап 4. Pair inspection flow — 1.5 дня

1. Click graph point/event открывает одну и ту же пару.
2. Подсвечивать A и B одновременно без перекраски остальных thumbnails.
3. Автоматически прокручивать оба endpoints в viewport.
4. Показать направление A→B.
5. В popup реализовать gate stack: pose, visibility, alignment, expression, quality, calibration, FDR, persistence.
6. Показать raw и compensated значения рядом.
7. Показать common/calibrated point support.
8. Показать alternative explanations.
9. Показать pair type и роль в multiple testing.
10. Убрать probability/verdict language.
11. Добавить переход к предыдущей/следующей паре.
12. Добавить compact compare A/B внутри popup, но не отдельную страницу.

**Gate 4:** для любой красной/оранжевой точки понятно, почему она candidate и что может её опровергнуть.

## Этап 5. Масштабирование и производительность — 1 день

1. Тест 50/500/1909 кадров.
2. Virtualize DOM без пропусков визуальной последовательности.
3. Не менять X-координаты при фильтрации событий.
4. Стабилизировать cursor-anchored zoom.
5. Добавить zoom limits на основе читаемости thumbnails.
6. Проверить track rendering через Canvas/SVG benchmark.
7. Ограничить hover computations.
8. Lazy-load images с prefetch соседей.
9. Обработать отсутствующий thumbnail.
10. Сохранить pose/zoom/scroll в URL state.
11. Проверить high-DPI и 125/150% browser zoom.
12. Добавить reduced-motion и keyboard pan.

**Gate 5:** 60 fps drag/zoom на целевой машине, без overlap и скачков.

## Этап 6. Визуальная и исследовательская проверка — 1 день

1. 1920×1080: default, zoom-in, zoom-out.
2. 1440×900: те же состояния.
3. 1366×768: минимальная поддерживаемая высота.
4. Candidate pair selected.
5. Limited pair selected.
6. Same-day stack open.
7. Date conflict.
8. Missing/null measurements.
9. Long historical gap.
10. All nine pose bins.
11. Проверка contrast и focus.
12. Проверка терминологии журналистом/аналитиком.

**Gate 6:** приложен визуальный QA-набор без overlap, clipping и ложной семантики.

---

## Приоритет данных

### P0 — обязательно
- photo/date/pose identity;
- pair A/B and pair type;
- measurement status;
- evidence state;
- calibrated effect;
- FDR q/significance;
- visibility/common support;
- critical limitations.

### P1 — после P0
- raw vs compensated;
- alignment residual;
- expression mismatch;
- anatomical zone support;
- persistence/corroboration;
- duplicate/date provenance.

### P2 — diagnostic
- detailed QC trends;
- calibration distributions;
- alternative pair families;
- debug artifacts.

### P3 — скрыто по умолчанию
- skin/texture readiness;
- UV diagnostics;
- raw per-point arrays;
- internal pipeline counters.

## Запреты

- Не возвращать zoom controls в toolbar.
- Не добавлять fit-all для hundreds thumbnails.
- Не создавать calendar-spacing photo mode.
- Не допускать overlap ради показа всего периода.
- Не возвращать pair arcs массово.
- Не показывать дату/score/badge на фото.
- Не смешивать role и event в одном ряду.
- Не вычислять anomaly/evidence в браузере.
- Не превращать null в 0.
- Не использовать красный только из-за большого z.
- Не создавать новые внутренние страницы до Gate 6.

## Что разработчик должен прислать на следующий контроль

1. Полный ZIP без `node_modules`.
2. Build и lint logs.
3. Unit tests data contract/priority/null policy.
4. Performance profile на 526 и 1909 кадров.
5. 12 обязательных screenshots из Этапа 6.
6. Screen recording wheel zoom + drag + pair selection.
7. JSON fixtures candidate/limited/null/same-day.
8. Таблицу всех track registry entries.
9. Список backend fields, которых не хватает.
10. Краткий changelog по каждому acceptance gate.

Только после этого выполняется ревью и принимается решение, можно ли переходить к следующему разделу продукта.
