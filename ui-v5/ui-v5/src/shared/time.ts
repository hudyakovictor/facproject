import type { ResearchPhoto } from "./researchApi";

/**
 * Нормализация времени и порядка фотографий.
 *
 * Интерфейс раньше брал границы шкалы как `photos[0].t` и `photos.at(-1).t`,
 * молча полагаясь на то, что backend вернёт отсортированный массив. На
 * неотсортированном ответе заголовок печатал «2024—1999», а шкала строилась
 * зеркально. Кроме того, недатированные кадры через `photo.t ?? firstDate`
 * прижимались к началу шкалы и выглядели как реально снятые в этот момент.
 */

export interface TimeBounds {
  first: number;
  last: number;
  range: number;
}

/** Фотографии с известным временем, отсортированные по возрастанию. */
export function sortPhotosByTime(photos: readonly ResearchPhoto[]): {
  dated: ResearchPhoto[];
  undated: ResearchPhoto[];
} {
  const dated: ResearchPhoto[] = [];
  const undated: ResearchPhoto[] = [];
  for (const photo of photos) {
    if (typeof photo.t === "number" && Number.isFinite(photo.t)) dated.push(photo);
    else undated.push(photo);
  }
  dated.sort((a, b) => (a.t as number) - (b.t as number));
  return { dated, undated };
}

/**
 * Границы временной шкалы. Возвращает null, если ни одна фотография не имеет
 * времени: рисовать шкалу в этом случае не по чему, и вызывающий код обязан
 * показать пустое состояние, а не подставлять произвольный диапазон.
 */
export function timeBounds(photos: readonly ResearchPhoto[]): TimeBounds | null {
  const { dated } = sortPhotosByTime(photos);
  if (dated.length === 0) return null;
  const first = dated[0].t as number;
  const last = dated[dated.length - 1].t as number;
  return { first, last, range: Math.max(last - first, 1) };
}

/** Год из ISO-даты, либо null. */
export function yearOf(photo: ResearchPhoto): string | null {
  return photo.date?.slice(0, 4) ?? null;
}

/** Безопасное форматирование метки времени: не бросает на Infinity/NaN. */
export function formatDate(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "н/д";
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return "н/д";
  return date.toISOString().slice(0, 10);
}

export function formatYear(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return "н/д";
  const date = new Date(ms);
  if (Number.isNaN(date.getTime())) return "н/д";
  return String(date.getUTCFullYear());
}
