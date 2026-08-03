import { t } from "../i18n";
import { useReducedMotion } from "../useReducedMotion";

/** Индикатор загрузки: визуальный, а не только текстовый.
 *
 * В семи компонентах состояние загрузки показывалось строкой «Загрузка…» —
 * на тёмном интерфейсе она теряется, и отличить «грузится» от «пусто»
 * невозможно.
 *
 * Уважает `prefers-reduced-motion`: вместо бегущей анимации показывается
 * статичная полоса (WCAG 2.3.3).
 */
export function Spinner({ label }: { label?: string }) {
  const reduced = useReducedMotion();
  return (
    <div role="status" aria-live="polite"
      className="flex items-center gap-2 font-mono text-[10px] text-text-muted">
      <span
        aria-hidden="true"
        className={`inline-block w-3 h-3 border border-info border-t-transparent rounded-full ${reduced ? "" : "animate-spin"}`}
      />
      {label ?? `${t.loading}…`}
    </div>
  );
}

/** Скелет блока: заполняет место будущего содержимого, чтобы верстка не
 * «прыгала» после загрузки. */
export function Skeleton({ lines = 3, height = 12 }: { lines?: number; height?: number }) {
  const reduced = useReducedMotion();
  return (
    <div role="status" aria-live="polite" aria-label={`${t.loading}…`} className="space-y-1.5">
      {Array.from({ length: lines }, (_, i) => (
        <div key={i}
          className={`bg-surface-2 ${reduced ? "" : "animate-pulse"}`}
          style={{ height, width: `${100 - (i % 3) * 12}%` }} />
      ))}
    </div>
  );
}
