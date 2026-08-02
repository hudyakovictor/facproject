import { useSyncExternalStore } from "react";

/** Пользователь просит ограничить анимации (`prefers-reduced-motion: reduce`).
 *
 * CSS-правило `animation: none` в `index.css` останавливает CSS-анимации, но
 * НЕ действует на SVG SMIL (`<animate>`): это независимый механизм, который
 * браузер не связывает со свойством `animation`. Пульсирующие маркеры
 * аномалий продолжали мигать у пользователей с вестибулярными нарушениями —
 * нарушение WCAG 2.3.3 (Animation from Interactions).
 *
 * Хук позволяет компонентам не рендерить `<animate>` вовсе.
 */
const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => undefined;
  const media = window.matchMedia(QUERY);
  // Safari < 14 не поддерживает addEventListener на MediaQueryList.
  if (media.addEventListener) {
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }
  media.addListener(onChange);
  return () => media.removeListener(onChange);
}

function getSnapshot(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(QUERY).matches;
}

/** SSR/тесты без matchMedia: анимации разрешены по умолчанию. */
function getServerSnapshot(): boolean {
  return false;
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
