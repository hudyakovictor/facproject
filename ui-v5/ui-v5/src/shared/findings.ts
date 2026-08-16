import type { ResearchPhoto } from "./researchApi";

/**
 * Технические маркеры, которые backend кладёт в `flags[]` для описания режима
 * работы, а не для указания на находку в данных.
 *
 * `stage1_timeline.py` проставляет `STAGE1_INVENTORY_ONLY` каждой без исключения
 * строке. Если считать находкой любой непустой `flags[]`, то в режиме Stage 1
 * находками окажутся все 1909 фотографий, и счётчик перестанет что-либо значить.
 */
export const TECHNICAL_FLAGS: ReadonlySet<string> = new Set([
  "STAGE1_INVENTORY_ONLY",
]);

/** Статусы Stage 2, которые сами по себе означают находку. */
export const FINDING_STATUS_KEYS: ReadonlySet<string> = new Set([
  "coherent_jump_candidate",
  "persistent_geometric_change",
  "insufficient_calibration",
]);

/** Флаги фотографии за вычетом технических маркеров режима. */
export function substantiveFlags(photo: ResearchPhoto): string[] {
  return photo.flags.filter((flag) => !TECHNICAL_FLAGS.has(flag));
}

/**
 * Является ли фотография находкой, требующей внимания эксперта.
 *
 * Красный цвет = приоритет проверки, а не «другой человек» (правило 11
 * AGENTS.md). Технические маркеры режима сюда не входят.
 */
export function isFinding(photo: ResearchPhoto): boolean {
  if (substantiveFlags(photo).length > 0) return true;
  const counts = photo.stage2StatusCounts ?? {};
  return Object.entries(counts).some(
    ([key, value]) => value > 0 && FINDING_STATUS_KEYS.has(key),
  );
}

export function countFindings(photos: readonly ResearchPhoto[]): number {
  return photos.reduce((total, photo) => total + (isFinding(photo) ? 1 : 0), 0);
}
