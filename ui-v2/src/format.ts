/** Безопасное форматирование метрик, которых может не быть.
 *
 * Research-режим Stage 2 не вычисляет часть каналов; после нормализации в
 * `api.validatePhoto` они приходят как `NaN`. Прямой вызов `.toFixed()` на
 * таком значении даёт строку "NaN" — визуально это выглядит как поломка,
 * а не как «канал не измерен».
 *
 * Правило проекта (`app6/AGENTS.md`): отсутствующие данные показываются как
 * «нет данных», а НЕ нулём и не пустотой.
 */

/** Прочерк для отсутствующего измерения. Единый символ по всему интерфейсу. */
export const NO_DATA = "—";

/** Число с фиксированной точностью либо «—». */
export function fmt(value: number | null | undefined, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(digits)
    : NO_DATA;
}

/** Проценты (0..1 → «42.0%») либо «—». */
export function fmtPercent(value: number | null | undefined, digits = 1): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${(value * 100).toFixed(digits)}%`
    : NO_DATA;
}

/** Значение измерено и пригодно к сравнению. */
export function hasValue(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}
