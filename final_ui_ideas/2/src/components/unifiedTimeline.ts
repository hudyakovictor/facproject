/**
 * Константы единого таймлайна.
 * Все зоны (tracks / filmstrip / verdict / ruler) используют одинаковую сетку,
 * чтобы точка метрики и превью фото были строго по одной вертикали.
 *
 * Архитектура — как в Adobe Premiere: один timeline, много дорожек.
 */

export const TILE_SIZE = 50;
export const TILE_GAP = 2;
export const TILE_STEP = TILE_SIZE + TILE_GAP; // 52px — шаг одного фото
export const TILE_CENTER = TILE_SIZE / 2; // 25px — центр плитки

/**
 * Позиция центра i-го фото на таймлайне.
 */
export function tileCenterX(index: number): number {
  return index * TILE_STEP + TILE_CENTER;
}

/**
 * Общая ширина таймлайна для N фото.
 */
export function timelineWidth(photoCount: number): number {
  return photoCount * TILE_STEP;
}
