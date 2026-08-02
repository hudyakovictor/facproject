/** Легаси-шкала тепловой карты БЕЗ зависимости от three.js.
 *
 * `heatColor` и `DEFAULT_HEATMAP_STOPS` жили в `MeshViewer.tsx`, поэтому
 * любой импорт этих констант (легенда, настройки, таблицы) затягивал в бандл
 * весь three.js — 471 KB, даже если пользователь не открывает 3D.
 *
 * Здесь та же математика на простом RGB-типе. `MeshViewer` переиспользует её
 * и оборачивает результат в `THREE.Color`, так что поведение не меняется.
 */
export interface HeatStops {
  blueCyan: number; cyanGreen: number; greenRed: number;
  saturatedRed: number; maxReference: number;
}

export const DEFAULT_HEATMAP_STOPS: HeatStops = {
  blueCyan: 0.25, cyanGreen: 0.5, greenRed: 0.75, saturatedRed: 1.0, maxReference: 0.12,
};

export interface HeatRgb { r: number; g: number; b: number }

const PALETTE: [number, HeatRgb][] = [
  [0, { r: 0x1d / 255, g: 0x4e / 255, b: 0xd8 / 255 }],   // синий
  [0, { r: 0x22 / 255, g: 0xd3 / 255, b: 0xee / 255 }],   // голубой
  [0, { r: 0x4a / 255, g: 0xde / 255, b: 0x80 / 255 }],   // зелёный
  [0, { r: 0xef / 255, g: 0x44 / 255, b: 0x44 / 255 }],   // красный
  [0, { r: 0x7f / 255, g: 0x1d / 255, b: 0x1d / 255 }],   // тёмно-красный
];

/** Кусочно-линейная шкала: синий → голубой → зелёный → красный → тёмно-красный. */
export function heatRgb(t: number, stops: HeatStops): HeatRgb {
  const clamped = Math.min(1, Math.max(0, t));
  const positions = [0, stops.blueCyan, stops.cyanGreen, stops.greenRed, stops.saturatedRed];
  for (let i = 1; i < PALETTE.length; i++) {
    const prevT = positions[i - 1], curT = positions[i];
    if (clamped <= curT || i === PALETTE.length - 1) {
      const span = Math.max(1e-6, curT - prevT);
      const local = Math.min(1, Math.max(0, (clamped - prevT) / span));
      const a = PALETTE[i - 1][1], b = PALETTE[i][1];
      return {
        r: a.r + (b.r - a.r) * local,
        g: a.g + (b.g - a.g) * local,
        b: a.b + (b.b - a.b) * local,
      };
    }
  }
  return PALETTE[PALETTE.length - 1][1];
}

/** `#rrggbb` для CSS-градиентов и SVG. */
export function heatHex(t: number, stops: HeatStops): string {
  const { r, g, b } = heatRgb(t, stops);
  const ch = (v: number) => Math.max(0, Math.min(255, Math.round(v * 255)))
    .toString(16).padStart(2, "0");
  return `#${ch(r)}${ch(g)}${ch(b)}`;
}
