import type { ResearchPhoto } from "../../shared/researchApi";

/**
 * Временной вьюпорт таймлайна: перевод «время ↔ пиксель».
 *
 * Вынесен из компонента, потому что от него зависит корректность всей шкалы, и
 * его нужно проверять тестами отдельно от рендера. Прежний код держал масштаб
 * в `zoom` и растягивал SVG через `preserveAspectRatio="none"`: увеличение
 * растягивало картинку вместо раскрытия деталей, а толщина линий и радиусы
 * точек искажались вместе с ней.
 */

export interface Viewport {
  /** Левая граница видимого диапазона, epoch ms. */
  start: number;
  /** Правая граница видимого диапазона, epoch ms. */
  end: number;
}

export interface TimeBounds {
  min: number;
  max: number;
}

/** Минимальная ширина окна — сутки: дальше приближать бессмысленно. */
const MIN_SPAN_MS = 86_400_000;

export function boundsOf(photos: readonly ResearchPhoto[]): TimeBounds | null {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  for (const photo of photos) {
    const t = timeOf(photo);
    if (t == null) continue;
    if (t < min) min = t;
    if (t > max) max = t;
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
  // Один кадр — не нулевой диапазон, иначе деление на ноль в масштабе.
  return max - min < MIN_SPAN_MS ? { min, max: min + MIN_SPAN_MS } : { min, max };
}

/**
 * Время кадра в epoch ms.
 *
 * Поле `t` у backend неоднозначно: `ui_fields.normalized_t` возвращает долю
 * [0,1], а не метку времени. Поэтому приоритет у `date`, а `t` используется
 * только когда он похож на настоящий timestamp.
 */
export function timeOf(photo: Pick<ResearchPhoto, "date" | "t">): number | null {
  if (photo.date) {
    const parsed = Date.parse(photo.date);
    if (Number.isFinite(parsed)) return parsed;
  }
  if (typeof photo.t === "number" && Number.isFinite(photo.t) && Math.abs(photo.t) > 1e6) {
    return photo.t;
  }
  return null;
}

export const spanOf = (viewport: Viewport) => Math.max(viewport.end - viewport.start, 1);

/** Время → доля ширины [0,1]. Значения вне вьюпорта не обрезаются. */
export const timeToRatio = (viewport: Viewport, time: number) =>
  (time - viewport.start) / spanOf(viewport);

/** Время → координата X в пикселях. */
export const timeToX = (viewport: Viewport, time: number, width: number) =>
  timeToRatio(viewport, time) * width;

/** Координата X → время. Нужен для зума от курсора и перекрестия. */
export const xToTime = (viewport: Viewport, x: number, width: number) =>
  viewport.start + (x / Math.max(width, 1)) * spanOf(viewport);

/** Ограничение вьюпорта пределами данных с сохранением ширины окна. */
export function clampViewport(viewport: Viewport, bounds: TimeBounds): Viewport {
  const total = bounds.max - bounds.min;
  const span = Math.min(Math.max(spanOf(viewport), MIN_SPAN_MS), total);

  let start = viewport.start;
  if (start < bounds.min) start = bounds.min;
  if (start + span > bounds.max) start = bounds.max - span;
  return { start, end: start + span };
}

/**
 * Зум относительно точки под курсором.
 *
 * Точка `anchorTime` обязана остаться под тем же пикселем — иначе при каждом
 * повороте колеса содержимое уезжает и пользователь теряет место, которое
 * рассматривал. Это и есть отличие «cursor-anchored zoom» от простого
 * изменения масштаба.
 */
export function zoomAt(
  viewport: Viewport,
  bounds: TimeBounds,
  anchorTime: number,
  factor: number,
): Viewport {
  const span = spanOf(viewport);
  const total = bounds.max - bounds.min;
  const nextSpan = Math.min(Math.max(span * factor, MIN_SPAN_MS), total);
  // Доля, на которой курсор стоит внутри окна, сохраняется.
  const anchorRatio = (anchorTime - viewport.start) / span;
  const start = anchorTime - anchorRatio * nextSpan;
  return clampViewport({ start, end: start + nextSpan }, bounds);
}

/** Сдвиг на долю ширины окна. */
export function panBy(viewport: Viewport, bounds: TimeBounds, ratio: number): Viewport {
  const delta = spanOf(viewport) * ratio;
  return clampViewport({ start: viewport.start + delta, end: viewport.end + delta }, bounds);
}

export const fitViewport = (bounds: TimeBounds): Viewport => ({
  start: bounds.min,
  end: bounds.max,
});

/** Во сколько раз окно уже полного диапазона. */
export const zoomLevel = (viewport: Viewport, bounds: TimeBounds) =>
  (bounds.max - bounds.min) / spanOf(viewport);

export interface Tick {
  time: number;
  label: string;
  /** Крупные деления подписываются и рисуются ярче. */
  major: boolean;
}

const YEAR = 365.25 * 86_400_000;

/**
 * Деления шкалы, подобранные под текущий масштаб.
 *
 * Годы при обзоре всего архива, кварталы и месяцы при приближении — §8.2 ТЗ
 * требует линейку «год + квартал». Фиксированный шаг по годам, как было
 * раньше, при зуме в один месяц не давал ни одной подписи.
 */
export function ticksFor(viewport: Viewport): Tick[] {
  const span = spanOf(viewport);
  const ticks: Tick[] = [];
  const startDate = new Date(viewport.start);

  if (span > 12 * YEAR) {
    const step = span > 40 * YEAR ? 10 : 5;
    let year = Math.floor(startDate.getUTCFullYear() / step) * step;
    while (Date.UTC(year, 0, 1) <= viewport.end) {
      const time = Date.UTC(year, 0, 1);
      if (time >= viewport.start) ticks.push({ time, label: String(year), major: true });
      year += step;
    }
    return ticks;
  }

  if (span > 2 * YEAR) {
    let year = startDate.getUTCFullYear();
    while (Date.UTC(year, 0, 1) <= viewport.end) {
      const time = Date.UTC(year, 0, 1);
      if (time >= viewport.start) ticks.push({ time, label: String(year), major: true });
      year += 1;
    }
    return ticks;
  }

  if (span > 120 * 86_400_000) {
    let year = startDate.getUTCFullYear();
    let quarter = Math.floor(startDate.getUTCMonth() / 3);
    while (Date.UTC(year, quarter * 3, 1) <= viewport.end) {
      const time = Date.UTC(year, quarter * 3, 1);
      if (time >= viewport.start) {
        ticks.push({
          time,
          label: quarter === 0 ? String(year) : `Q${quarter + 1}`,
          major: quarter === 0,
        });
      }
      quarter += 1;
      if (quarter > 3) {
        quarter = 0;
        year += 1;
      }
    }
    return ticks;
  }

  const MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  let year = startDate.getUTCFullYear();
  let month = startDate.getUTCMonth();
  while (Date.UTC(year, month, 1) <= viewport.end) {
    const time = Date.UTC(year, month, 1);
    if (time >= viewport.start) {
      ticks.push({
        time,
        label: month === 0 ? String(year) : MONTHS[month],
        major: month === 0,
      });
    }
    month += 1;
    if (month > 11) {
      month = 0;
      year += 1;
    }
  }
  return ticks;
}
