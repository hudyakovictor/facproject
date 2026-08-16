import type { ResearchPhoto } from "../../shared/researchApi";
import { isFinding } from "../../shared/findings";
import { timeToRatio, type Viewport } from "./viewport";

/**
 * Отбор превью для строки фотографий.
 *
 * Раньше стояло `filtered.filter((_, i) => i % ceil(len / 160) === 0)` —
 * произвольное прореживание по позиции в массиве (A24/A25). Оно давало два
 * дефекта: показанный кадр не имел отношения к своему участку шкалы, и
 * находка могла исчезнуть только потому, что её индекс не делился нацело.
 *
 * Здесь шкала делится на бакеты шириной с превью, и в каждом выбирается один
 * представитель. Приоритет: находка важнее обычного кадра (её нельзя терять
 * при прореживании), среди равных — лучшее качество, при отсутствии качества —
 * ближайший к центру бакета.
 */

export interface RepresentativeOptions {
  viewport: Viewport;
  /** Ширина области в пикселях. */
  width: number;
  /** Шаг сетки в пикселях: ширина превью с зазором. */
  slotWidth: number;
  /** Кадры, которые обязаны присутствовать (A/B, выбранный). */
  pinned?: readonly (string | null | undefined)[];
}

interface Candidate {
  photo: ResearchPhoto;
  time: number;
  slot: number;
}

/** Кадр лучше текущего представителя бакета? */
function better(candidate: ResearchPhoto, current: ResearchPhoto, centerDelta: number, currentDelta: number): boolean {
  // Находка вытесняет обычный кадр: пропущенная находка — потеря информации,
  // пропущенный рядовой кадр — только потеря плотности.
  const candidateFinding = isFinding(candidate);
  const currentFinding = isFinding(current);
  if (candidateFinding !== currentFinding) return candidateFinding;

  // Затем — качество. null не считается нулём: кадр без оценки не должен
  // проигрывать кадру с честной оценкой 0.0, но и вытеснять его не должен.
  const a = candidate.quality;
  const b = current.quality;
  if (a != null && b != null && a !== b) return a > b;
  if (a != null && b == null) return true;
  if (a == null && b != null) return false;

  return centerDelta < currentDelta;
}

export function pickRepresentatives(
  photos: readonly ResearchPhoto[],
  times: ReadonlyMap<string, number>,
  { viewport, width, slotWidth, pinned = [] }: RepresentativeOptions,
): ResearchPhoto[] {
  if (width <= 0 || slotWidth <= 0) return [];

  const slotCount = Math.max(1, Math.floor(width / slotWidth));
  const chosen = new Map<number, Candidate>();
  const deltas = new Map<number, number>();

  for (const photo of photos) {
    const time = times.get(photo.id);
    if (time == null) continue;

    const ratio = timeToRatio(viewport, time);
    if (ratio < 0 || ratio > 1) continue;

    const slot = Math.min(slotCount - 1, Math.floor(ratio * slotCount));
    const slotCenter = (slot + 0.5) / slotCount;
    const delta = Math.abs(ratio - slotCenter);

    const current = chosen.get(slot);
    if (!current || better(photo, current.photo, delta, deltas.get(slot) ?? Infinity)) {
      chosen.set(slot, { photo, time, slot });
      deltas.set(slot, delta);
    }
  }

  const result = [...chosen.values()].sort((a, b) => a.time - b.time).map((item) => item.photo);

  /*
   * Закреплённые кадры добавляются независимо от прореживания: если A или B
   * исчезнет с экрана, пользователь решит, что выбор сбросился.
   */
  const present = new Set(result.map((photo) => photo.id));
  for (const id of pinned) {
    if (!id || present.has(id)) continue;
    const photo = photos.find((item) => item.id === id);
    const time = photo ? times.get(photo.id) : undefined;
    if (!photo || time == null) continue;
    const ratio = timeToRatio(viewport, time);
    if (ratio < 0 || ratio > 1) continue;
    result.push(photo);
    present.add(id);
  }

  return result.sort((a, b) => (times.get(a.id) ?? 0) - (times.get(b.id) ?? 0));
}
