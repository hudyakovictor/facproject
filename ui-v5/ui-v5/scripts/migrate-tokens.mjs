/**
 * Разовая миграция экранов на токены дизайн-системы (задача З3.2).
 *
 * Скрипт применяет проверенную таблицу соответствий: хардкод-цвета и классы
 * палитры Tailwind по умолчанию заменяются на семантические токены. Замена
 * механическая сознательно — 269 литералов и ~450 классов правкой вручную
 * гарантированно дали бы расхождения между экранами, а именно они и есть
 * содержание дефекта D10.
 *
 * Соответствия строятся по смыслу, а не по близости оттенка:
 *   slate-300/400/500  → ink-secondary/muted (текст второго плана)
 *   emerald-*          → green-*  (принято / в пределах ожидаемого)
 *   rose-*             → red-*    (кандидат на проверку, НЕ вердикт)
 *   purple/fuchsia     → violet-* (приватное / гипотезы)
 *   #1f2d3d, #263747   → line-default (границы)
 *   #0b1117, #101820   → surface-base / surface-raised
 *
 * Запуск: node scripts/migrate-tokens.mjs
 */
import { readFileSync, writeFileSync, globSync } from "node:fs";

/** Хекс-литералы внутри произвольных значений Tailwind: bg-[#0b1117]. */
const HEX = [
  ["#080d12", "surface-canvas"],
  ["#081016", "surface-canvas"],
  ["#0a1016", "surface-canvas"],
  ["#0b1117", "surface-base"],
  ["#101820", "surface-raised"],
  ["#141e27", "surface-overlay"],
  ["#18232d", "surface-subtle"],
  ["#1c2935", "line-subtle"],
  ["#1f2d3d", "line-default"],
  ["#263747", "line-default"],
  ["#e2e8f0", "ink-primary"],
  ["#cbd5e1", "ink-secondary"],
  ["#155e75", "cyan-600"],
  ["#69cce0", "cyan-400"],
  ["#22d3ee", "cyan-400"],
  ["#34d399", "green-400"],
  ["#66bc7e", "green-400"],
  ["#f59e0b", "amber-400"],
  ["#fbbf24", "amber-400"],
  ["#f2b94b", "amber-400"],
  ["#ef625d", "red-400"],
  ["#fb7185", "red-400"],
  ["#a78bfa", "violet-400"],
  ["#a97bd4", "violet-400"],
  ["#60a5fa", "blue-400"],
];

/** Классы палитры Tailwind по умолчанию → семантические токены. */
const CLASS = [
  // Нейтральные: текст
  [/\btext-white\b/g, "text-ink-primary"],
  [/\btext-slate-100\b/g, "text-ink-primary"],
  [/\btext-slate-200\b/g, "text-ink-primary"],
  [/\btext-slate-300\b/g, "text-ink-secondary"],
  [/\btext-slate-400\b/g, "text-ink-muted"],
  [/\btext-slate-500\b/g, "text-ink-muted"],
  [/\btext-slate-600\b/g, "text-ink-disabled"],

  // Нейтральные: фон и границы
  [/\bbg-white\b/g, "bg-surface-raised"],
  [/\bbg-black\b/g, "bg-surface-canvas"],
  [/\bbg-slate-950\b/g, "bg-surface-base"],
  [/\bbg-slate-900\b/g, "bg-surface-raised"],
  [/\bbg-slate-800\b/g, "bg-surface-subtle"],
  [/\bbg-slate-700\b/g, "bg-surface-hover"],
  [/\bbg-slate-600\b/g, "bg-surface-active"],
  [/\bborder-slate-600\b/g, "border-line-strong"],
  [/\bborder-slate-700\b/g, "border-line-default"],
  [/\bborder-slate-800\b/g, "border-line-subtle"],
  [/\bborder-slate-900\b/g, "border-line-subtle"],
  [/\bdivide-slate-800\b/g, "divide-line-subtle"],

  // emerald → green (принято / в пределах ожидаемого)
  [/\btext-emerald-200\b/g, "text-green-300"],
  [/\btext-emerald-300\b/g, "text-green-300"],
  [/\btext-emerald-400\b/g, "text-green-400"],
  [/\bbg-emerald-950(\/\d+)?\b/g, "bg-green-soft"],
  [/\bbg-emerald-900(\/\d+)?\b/g, "bg-green-soft"],
  [/\bbg-emerald-500\b/g, "bg-green-500"],
  [/\bborder-emerald-800(\/\d+)?\b/g, "border-green-500"],
  [/\bborder-emerald-700(\/\d+)?\b/g, "border-green-500"],
  [/\baccent-emerald-500\b/g, "accent-green-500"],

  // rose → red (кандидат на проверку)
  [/\btext-rose-200\b/g, "text-red-300"],
  [/\btext-rose-300\b/g, "text-red-300"],
  [/\btext-rose-400\b/g, "text-red-400"],
  [/\btext-rose-500\b/g, "text-red-400"],
  [/\bbg-rose-950(\/\d+)?\b/g, "bg-red-soft"],
  [/\bbg-rose-900(\/\d+)?\b/g, "bg-red-soft"],
  [/\bbg-rose-600\b/g, "bg-red-500"],
  [/\bbg-rose-500\b/g, "bg-red-500"],
  [/\bborder-rose-300\b/g, "border-red-300"],
  [/\bborder-rose-600(\/\d+)?\b/g, "border-red-500"],
  [/\bborder-rose-700(\/\d+)?\b/g, "border-red-500"],
  [/\bborder-rose-800(\/\d+)?\b/g, "border-red-500"],
  [/\baccent-rose-500\b/g, "accent-red-500"],

  // amber остаётся amber, но уровни приводятся к трём токенам
  [/\btext-amber-200\b/g, "text-amber-300"],
  [/\btext-amber-400\b/g, "text-amber-400"],
  [/\bbg-amber-950(\/\d+)?\b/g, "bg-amber-soft"],
  [/\bbg-amber-900(\/\d+)?\b/g, "bg-amber-soft"],
  [/\bbg-amber-500\b/g, "bg-amber-500"],
  [/\bborder-amber-700(\/\d+)?\b/g, "border-amber-500"],
  [/\bborder-amber-800(\/\d+)?\b/g, "border-amber-500"],
  [/\bborder-amber-300\b/g, "border-amber-300"],

  // cyan: уровни 700–950 сводятся к токенам
  [/\btext-cyan-200\b/g, "text-cyan-300"],
  [/\bbg-cyan-950(\/\d+)?\b/g, "bg-cyan-soft"],
  [/\bbg-cyan-900(\/\d+)?\b/g, "bg-cyan-soft"],
  [/\bbg-cyan-700\b/g, "bg-cyan-600"],
  [/\bborder-cyan-400\b/g, "border-cyan-400"],
  [/\bborder-cyan-500\b/g, "border-cyan-500"],
  [/\bborder-cyan-700(\/\d+)?\b/g, "border-cyan-600"],
  [/\bborder-cyan-800(\/\d+)?\b/g, "border-cyan-600"],

  // purple/fuchsia → violet (приватное, гипотезы)
  [/\btext-purple-400\b/g, "text-violet-400"],
  [/\btext-fuchsia-300\b/g, "text-violet-300"],
  [/\bbg-purple-500\b/g, "bg-violet-400"],

  // Высота рабочей области: магическое 49px → токен
  [/h-\[calc\(100vh-49px\)\]/g, "h-workspace"],
  [/h-\[calc\(100vh-49px-28px\)\]/g, "h-workspace"],
];

const files = globSync("src/**/*.tsx");
let touched = 0;
let hexCount = 0;
let classCount = 0;

for (const file of files) {
  const before = readFileSync(file, "utf8");
  let after = before;

  for (const [hex, token] of HEX) {
    // Только внутри произвольных значений Tailwind: bg-[#0b1117] → bg-surface-base
    const arbitrary = new RegExp(
      `\\b(bg|text|border|ring|fill|stroke|from|to|via|shadow|outline|decoration|divide|accent|caret)-\\[${hex}\\](\\/\\d+)?`,
      "gi",
    );
    after = after.replace(arbitrary, (_m, prefix) => {
      hexCount += 1;
      return `${prefix}-${token}`;
    });
  }

  for (const [pattern, replacement] of CLASS) {
    after = after.replace(pattern, () => {
      classCount += 1;
      return replacement;
    });
  }

  if (after !== before) {
    writeFileSync(file, after);
    touched += 1;
  }
}

console.log(
  `Файлов изменено: ${touched} · хекс-литералов заменено: ${hexCount} · классов заменено: ${classCount}`,
);
