/**
 * Токены для мест, где цвет нужен как значение, а не как класс.
 *
 * Canvas, SVG `stroke` и инлайновый `style` не понимают классы Tailwind, и
 * именно там оставались последние хардкод-цвета. Возвращать литерал нельзя:
 * тогда светлая тема и compact-плотность снова разошлись бы с остальным
 * интерфейсом. Поэтому здесь — ссылки на CSS-переменные, а для Canvas 2D,
 * который переменных не понимает, есть `resolveToken`.
 */

/** Ссылка на CSS-переменную для использования в SVG и style. */
export const token = (name: string) => `var(${name})`;

/**
 * Цвета дорожек метрик.
 *
 * Порядок фиксирован: одна и та же метрика на любом экране должна иметь один
 * и тот же цвет, иначе цвет перестаёт что-либо значить. Правило 11 AGENTS.md
 * запрещает трактовать цвет как вывод о личности — здесь он лишь различает
 * дорожки между собой.
 */
export const METRIC_COLORS: Record<string, string> = {
  yaw: token("--cyan-400"),
  quality: token("--green-400"),
  pitch: token("--violet-400"),
  roll: token("--amber-400"),
  boneScore: token("--blue-400"),
  confidence: token("--cyan-300"),
};

/**
 * Палитра для различения категорий (бинов ракурса, серий).
 *
 * Это именно различение, а не шкала: соседние цвета не означают близость
 * значений, а красный не означает «плохо».
 */
export const CATEGORY_COLORS: readonly string[] = [
  token("--cyan-400"),
  token("--green-400"),
  token("--amber-400"),
  token("--violet-400"),
  token("--blue-400"),
  token("--red-400"),
];

/**
 * Вычисленное значение переменной — для Canvas 2D, который принимает только
 * конкретный цвет. Читается из документа, поэтому следует активной теме.
 */
export function resolveToken(name: string, fallback = "#000000"): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}
