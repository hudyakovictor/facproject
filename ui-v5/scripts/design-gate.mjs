/**
 * Гейт дизайн-системы (Gate Ф3).
 *
 * Миграция на токены бессмысленна без защиты: следующий добавленный экран
 * снова принесёт `bg-[#0b1117]` и `text-slate-400`, и через несколько правок
 * дизайн-система опять станет экспонатом. Проверки намеренно грубые и
 * текстовые — они должны выполняться за секунды и не требовать сборки.
 *
 * Запуск: node scripts/design-gate.mjs
 */
import { readFileSync, globSync } from "node:fs";

const files = globSync("src/**/*.tsx").filter((f) => !f.endsWith(".test.tsx"));


/** Витрина дизайн-системы вправе показывать значения токенов буквально. */
const HEX_EXEMPT = new Set(["src/features/design-system/DesignSystemPage.tsx"]);

const violations = [];

/** Классы удалённой палитры Tailwind: их больше не существует в конфиге. */
const DEAD_PALETTE =
  /\b(?:bg|text|border|ring|from|to|via|accent|fill|stroke|divide|outline|shadow|caret|decoration)-(?:slate|gray|zinc|neutral|stone|orange|yellow|lime|emerald|teal|sky|indigo|purple|fuchsia|pink|rose)-\d{2,3}\b/g;

/** Хардкод-цвет в произвольном значении Tailwind. */
const ARBITRARY_HEX =
  /\b(?:bg|text|border|ring|from|to|via|fill|stroke|divide|outline|shadow|accent|caret|decoration)-\[#[0-9a-fA-F]{3,8}\]/g;

/** Магическая высота рабочей области вместо токена. */
const MAGIC_VIEWPORT = /calc\(100vh-\d+px\)/g;

function record(file, rule, matches) {
  const unique = [...new Set(matches)];
  if (unique.length) violations.push({ file, rule, samples: unique.slice(0, 6), count: matches.length });
}

for (const file of files) {
  const source = readFileSync(file, "utf8");

  record(file, "удалённая палитра Tailwind", source.match(DEAD_PALETTE) ?? []);
  record(file, "магическая высота вместо h-workspace", source.match(MAGIC_VIEWPORT) ?? []);

  if (!HEX_EXEMPT.has(file)) {
    record(file, "хардкод-цвет вместо токена", source.match(ARBITRARY_HEX) ?? []);
  }
}

/**
 * Ссылка на несуществующую CSS-переменную.
 *
 * Опечатка вроде `var(--violet-500)` при отсутствующем токене не ломает ни
 * сборку, ни типы: свойство просто не применяется, и граница становится
 * прозрачной. Такую ошибку невозможно заметить в отзыве кода и легко
 * пропустить на экране, поэтому её ищет гейт.
 *
 * Значение с запасным вариантом — `var(--x, fallback)` — законно: оно
 * рассчитано на то, что переменная задана не всегда.
 */
const tokenSources = ["src/styles/tokens.css", "src/styles/global.css"];
const defined = new Set();
for (const file of tokenSources) {
  for (const match of readFileSync(file, "utf8").matchAll(/(--[a-z0-9-]+)\s*:/g)) {
    defined.add(match[1]);
  }
}

// Переменные, которые задаются инлайн из TSX (style={{ "--quality": ... }}).
const inlineDefined = new Set();
for (const file of files) {
  for (const match of readFileSync(file, "utf8").matchAll(/"(--[a-z0-9-]+)"\s*:/g)) {
    inlineDefined.add(match[1]);
  }
}

const varFiles = [...globSync("src/**/*.css"), ...files];
for (const file of varFiles) {
  if (tokenSources.includes(file)) continue;
  const source = readFileSync(file, "utf8");
  // Переменная может объявляться локально в том же файле (например, чтобы
  // модификатор класса менял цвет кольца) или задаваться инлайн через style.
  const local = new Set(
    [...source.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((match) => match[1]),
  );
  const unknown = [];
  for (const match of source.matchAll(/var\((--[a-z0-9-]+)\s*(,?)/g)) {
    if (local.has(match[1]) || inlineDefined.has(match[1])) continue;
    // `--x` внутри resolveToken() подставляется во время выполнения.
    if (match[1] === "--x") continue;
    if (match[2] === ",") continue;
    if (!defined.has(match[1])) unknown.push(match[1]);
  }
  record(file, "неизвестная CSS-переменная", unknown);
}

if (violations.length === 0) {
  console.log(`ГЕЙТ ДИЗАЙН-СИСТЕМЫ · ${files.length} файлов · нарушений нет`);
  process.exit(0);
}

console.error("ГЕЙТ ДИЗАЙН-СИСТЕМЫ · НАРУШЕНИЯ:\n");
for (const violation of violations) {
  console.error(`  ${violation.file}`);
  console.error(`    ${violation.rule} · ${violation.count}: ${violation.samples.join(", ")}`);
}
console.error(
  `\nВсего: ${violations.reduce((sum, v) => sum + v.count, 0)} совпадений в ${violations.length} проверках.`,
);
console.error("Используйте токены дизайн-системы: surface-*, ink-*, line-*, cyan/amber/green/red/violet.");
process.exit(1);
