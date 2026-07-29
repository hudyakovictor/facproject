/** Модель настраиваемого градиента тепловой карты.
 *
 * Прежняя реализация (`heatColor` в MeshViewer) жёстко задавала пять цветов и
 * линейно интерполировала между ними: настраивались только позиции остановок.
 * Для forensic-задачи этого мало — нужен РАЗНЫЙ характер перехода на разных
 * участках:
 *
 *   * в зоне допустимой для одного человека изменчивости переход плавный
 *     (синий → голубой): мелкие колебания не должны бросаться в глаза;
 *   * на границе аномальных различий переход РЕЗКИЙ: значение либо ниже
 *     порога, либо выше, и это должно быть видно мгновенно;
 *   * за порогом цвет может «удерживаться» (красный → тёмно-красный или тот
 *     же красный), чтобы дальнейший рост не размывал сигнал.
 *
 * Резкость задаётся на КАЖДЫЙ сегмент отдельно параметром `sharpness ∈ [0,1]`:
 * 0 — линейный переход по всей ширине сегмента, 1 — ступенька в его середине.
 */

export interface GradientStop {
  /** Позиция остановки в нормализованной шкале [0,1]. */
  position: number;
  /** Цвет в формате `#rrggbb`. */
  color: string;
  /** Резкость перехода ОТ этой остановки к следующей: 0 — плавно, 1 — ступенька. */
  sharpness: number;
  /** Подпись остановки для легенды (необязательна). */
  label?: string;
}

export interface GradientModel {
  stops: GradientStop[];
  /** Значение метрики, соответствующее position=1. Задаёт числовую шкалу. */
  maxReference: number;
}

/** Пресет по умолчанию: синий → голубой → жёлтый → красный → тёмно-красный.
 *
 * Резкость подобрана под смысл зон: плавно внутри нормы, резко на границе
 * аномалии, удержание за ней. */
export const DEFAULT_GRADIENT: GradientModel = {
  maxReference: 0.12,
  stops: [
    { position: 0.00, color: "#1d4ed8", sharpness: 0.00, label: "норма" },
    { position: 0.25, color: "#22d3ee", sharpness: 0.15, label: "верх нормы" },
    { position: 0.50, color: "#facc15", sharpness: 0.55, label: "внимание" },
    { position: 0.75, color: "#ef4444", sharpness: 0.85, label: "аномалия" },
    { position: 1.00, color: "#7f1d1d", sharpness: 0.00, label: "предел" },
  ],
};

/** Пресеты для быстрого старта. */
export const GRADIENT_PRESETS: Record<string, { labelKey: string; model: GradientModel }> = {
  forensic: { labelKey: "gradPresetForensic", model: DEFAULT_GRADIENT },
  linear: {
    labelKey: "gradPresetLinear",
    model: {
      maxReference: 0.12,
      stops: [
        { position: 0.00, color: "#1d4ed8", sharpness: 0 },
        { position: 0.25, color: "#22d3ee", sharpness: 0 },
        { position: 0.50, color: "#facc15", sharpness: 0 },
        { position: 0.75, color: "#ef4444", sharpness: 0 },
        { position: 1.00, color: "#7f1d1d", sharpness: 0 },
      ],
    },
  },
  hardThreshold: {
    labelKey: "gradPresetHard",
    model: {
      maxReference: 0.12,
      stops: [
        { position: 0.00, color: "#1d4ed8", sharpness: 0.1 },
        { position: 0.45, color: "#22d3ee", sharpness: 1.0 },
        { position: 0.55, color: "#ef4444", sharpness: 1.0 },
        { position: 1.00, color: "#7f1d1d", sharpness: 0 },
      ],
    },
  },
};

export interface Rgb { r: number; g: number; b: number }

/** Разбор `#rrggbb` в компоненты 0..1. Некорректный цвет → серый,
 * чтобы ошибка настройки не роняла рендер 35 709 вершин. */
export function parseHex(hex: string): Rgb {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return { r: 0.5, g: 0.5, b: 0.5 };
  const value = parseInt(match[1], 16);
  return {
    r: ((value >> 16) & 255) / 255,
    g: ((value >> 8) & 255) / 255,
    b: (value & 255) / 255,
  };
}

export function toHex({ r, g, b }: Rgb): string {
  const channel = (v: number) =>
    Math.max(0, Math.min(255, Math.round(v * 255))).toString(16).padStart(2, "0");
  return `#${channel(r)}${channel(g)}${channel(b)}`;
}

/** Передаточная функция резкости.
 *
 * `local` — доля пройденного сегмента [0,1]. При `sharpness = 0` возвращает
 * `local` (линейно). При росте sharpness переход сжимается к середине
 * сегмента: ширина активной полосы = `1 - sharpness`. При sharpness → 1
 * получается ступенька.
 */
export function applySharpness(local: number, sharpness: number): number {
  const s = Math.max(0, Math.min(1, sharpness));
  if (s <= 0) return local;
  const width = Math.max(1e-6, 1 - s);
  const start = (1 - width) / 2;
  return Math.max(0, Math.min(1, (local - start) / width));
}

/** Отсортированные валидные остановки. Пустой градиент недопустим. */
function normalizedStops(model: GradientModel): GradientStop[] {
  const stops = [...model.stops]
    .filter(s => Number.isFinite(s.position))
    .sort((a, b) => a.position - b.position);
  if (!stops.length) return DEFAULT_GRADIENT.stops;
  return stops;
}

/** 🎨 Вычислить цвет для нормализованного значения `t ∈ [0,1]`. */
export function evaluateGradient(model: GradientModel, t: number): Rgb {
  const stops = normalizedStops(model);
  const clamped = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0));

  if (clamped <= stops[0].position) return parseHex(stops[0].color);
  const last = stops[stops.length - 1];
  if (clamped >= last.position) return parseHex(last.color);

  for (let i = 1; i < stops.length; i++) {
    const prev = stops[i - 1];
    const cur = stops[i];
    if (clamped > cur.position) continue;
    const span = cur.position - prev.position;
    // Нулевая ширина сегмента = мгновенный скачок цвета.
    if (span <= 1e-9) return parseHex(cur.color);
    const local = (clamped - prev.position) / span;
    const eased = applySharpness(local, prev.sharpness);
    const a = parseHex(prev.color);
    const b = parseHex(cur.color);
    return {
      r: a.r + (b.r - a.r) * eased,
      g: a.g + (b.g - a.g) * eased,
      b: a.b + (b.b - a.b) * eased,
    };
  }
  return parseHex(last.color);
}

/** CSS-градиент для превью. Резкие участки требуют частой дискретизации,
 * поэтому строится по выборке, а не по остановкам. */
export function gradientToCss(model: GradientModel, steps = 96): string {
  const parts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    parts.push(`${toHex(evaluateGradient(model, t))} ${(t * 100).toFixed(2)}%`);
  }
  return `linear-gradient(to right, ${parts.join(", ")})`;
}

/** Значение метрики для позиции шкалы. */
export function valueAt(model: GradientModel, position: number): number {
  return position * model.maxReference;
}

/** Позиция шкалы для значения метрики (для отметок порогов). */
export function positionOf(model: GradientModel, value: number): number {
  const max = Math.max(1e-9, model.maxReference);
  return Math.max(0, Math.min(1, value / max));
}

/** 🚧 Привести модель к корректному виду: позиции в [0,1], возрастающие,
 * первая = 0, последняя = 1. Возвращает НОВЫЙ объект. */
export function sanitizeGradient(model: GradientModel): GradientModel {
  const stops = normalizedStops(model).map(s => ({
    ...s,
    position: Math.max(0, Math.min(1, s.position)),
    sharpness: Math.max(0, Math.min(1, Number.isFinite(s.sharpness) ? s.sharpness : 0)),
  }));
  // Гарантируем покрытие всей шкалы: иначе края остаются неопределёнными.
  if (stops[0].position > 0) stops.unshift({ ...stops[0], position: 0 });
  if (stops[stops.length - 1].position < 1) {
    stops.push({ ...stops[stops.length - 1], position: 1 });
  }
  return {
    maxReference: Math.max(1e-6, model.maxReference),
    stops,
  };
}

/** Совместимость со старым форматом настроек (4 позиции + maxReference). */
export function fromLegacyStops(legacy: {
  blueCyan: number; cyanGreen: number; greenRed: number;
  saturatedRed: number; maxReference: number;
}): GradientModel {
  return sanitizeGradient({
    maxReference: legacy.maxReference,
    stops: [
      { position: 0, color: "#1d4ed8", sharpness: 0 },
      { position: legacy.blueCyan, color: "#22d3ee", sharpness: 0 },
      { position: legacy.cyanGreen, color: "#4ade80", sharpness: 0 },
      { position: legacy.greenRed, color: "#ef4444", sharpness: 0 },
      { position: legacy.saturatedRed, color: "#7f1d1d", sharpness: 0 },
    ],
  });
}
