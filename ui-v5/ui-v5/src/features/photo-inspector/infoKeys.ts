/**
 * Разбор `info.json` кадра в плоский список ключей с категориями (§10.4, вкладка Raw).
 *
 * Stage 1 сохраняет на кадр порядка 156 листовых значений, вложенных на три-четыре
 * уровня. Интерфейс до сих пор показывал восемь. Показать «весь JSON как есть»
 * было бы честно, но бесполезно: эксперту нужно найти конкретный ключ и понять,
 * к какой части исследования он относится.
 *
 * Категории — те же буквы, что в `app6/api/key_catalog.py::CATEGORY_TITLES`.
 * Расходиться им нельзя: одно и то же поле не должно называться по-разному в
 * инспекторе кадра и в таблице метрик пары.
 *
 * 🚨 WARNING: `null` сохраняется как `null` и рисуется как «н/д». Ноль вместо
 * пропуска не подставляется нигде — это прямой запрет `app6/AGENTS.md`.
 */

/** Категория ключа. Буквы совпадают с backend, чтобы подписи не разъезжались. */
export type KeyCategory = "C" | "D" | "E" | "F" | "G" | "H";

export const CATEGORY_TITLES: Record<KeyCategory, string> = {
  C: "Качество и применимость",
  D: "Точки и дескрипторы",
  E: "Текстура",
  F: "Хронология",
  G: "Провенанс",
  H: "Артефакты кадра",
};

/** Порядок разделов на вкладке Raw: от происхождения кадра к производным. */
export const CATEGORY_ORDER: KeyCategory[] = ["G", "F", "C", "D", "E", "H"];

export interface InfoLeaf {
  /** Полный путь через точку: `pose.canonical_yaw`. */
  path: string;
  /** Значение как есть. `null` означает отсутствие, а не ноль. */
  value: string | number | boolean | null;
  category: KeyCategory;
  /** Тип для выравнивания и форматирования в таблице. */
  kind: "number" | "string" | "boolean" | "null";
}

/**
 * Правила категоризации по префиксу пути. Порядок важен: более длинные и
 * специфичные префиксы проверяются раньше общих.
 */
const PREFIX_RULES: ReadonlyArray<readonly [string, KeyCategory]> = [
  ["date_provenance", "G"],
  ["source_provenance", "G"],
  ["source_digest", "G"],
  ["source_filename", "G"],
  ["source_relative_path", "G"],
  ["perceptual_dhash", "G"],
  ["near_duplicate_of", "G"],
  ["code_hash", "G"],
  ["config_hash", "G"],
  ["model_hash", "G"],
  ["schema_version", "G"],
  ["extraction_timestamp", "G"],
  ["photo_id", "G"],

  ["chronology", "F"],
  ["same_date_sequence", "F"],
  ["date", "F"],

  ["quality_inputs", "C"],
  ["quality_summary", "C"],
  ["skin_quality", "C"],
  ["skin_authenticity", "C"],
  ["reprojection", "C"],
  ["validation", "C"],
  ["pose", "C"],
  ["camera", "C"],
  ["normalization", "C"],

  ["landmark_contract", "D"],
  ["crop", "D"],

  ["skin", "E"],
  ["texture", "E"],
  ["uv", "E"],

  ["files", "H"],
  ["mask", "H"],
  ["image", "H"],
];

/** Категория ключа по его пути. Неизвестное относим к артефактам кадра. */
export function categorizeKey(path: string): KeyCategory {
  for (const [prefix, category] of PREFIX_RULES) {
    if (path === prefix || path.startsWith(`${prefix}.`)) return category;
  }
  return "H";
}

/**
 * Рекурсивный обход `info.json` до листьев.
 *
 * Массивы разворачиваются по индексу (`bbox_original.0`), но только если они
 * коротки: список из тысячи вершин в таблице ключей нечитаем и бесполезен,
 * поэтому длинные массивы сворачиваются в одну строку с указанием длины —
 * пользователь видит, что данные есть, и сколько их.
 */
const MAX_ARRAY_ITEMS = 8;

export function flattenInfo(
  source: Record<string, unknown>,
  prefix = "",
): InfoLeaf[] {
  const out: InfoLeaf[] = [];
  for (const [key, raw] of Object.entries(source)) {
    const path = prefix ? `${prefix}.${key}` : key;
    pushValue(out, path, raw);
  }
  return out;
}

function pushValue(out: InfoLeaf[], path: string, raw: unknown): void {
  if (raw === null || raw === undefined) {
    out.push({ path, value: null, category: categorizeKey(path), kind: "null" });
    return;
  }
  if (Array.isArray(raw)) {
    if (raw.length === 0) {
      out.push({
        path,
        value: "пустой список",
        category: categorizeKey(path),
        kind: "string",
      });
      return;
    }
    if (raw.length > MAX_ARRAY_ITEMS) {
      out.push({
        path,
        value: `список из ${raw.length} значений`,
        category: categorizeKey(path),
        kind: "string",
      });
      return;
    }
    raw.forEach((item, index) => pushValue(out, `${path}.${index}`, item));
    return;
  }
  if (typeof raw === "object") {
    const entries = Object.entries(raw as Record<string, unknown>);
    if (entries.length === 0) {
      out.push({
        path,
        value: "пустой объект",
        category: categorizeKey(path),
        kind: "string",
      });
      return;
    }
    for (const [key, value] of entries) pushValue(out, `${path}.${key}`, value);
    return;
  }
  const kind =
    typeof raw === "number" ? "number" : typeof raw === "boolean" ? "boolean" : "string";
  out.push({
    path,
    value: raw as string | number | boolean,
    category: categorizeKey(path),
    kind,
  });
}

/** Группировка листьев по категориям в порядке `CATEGORY_ORDER`. */
export function groupByCategory(
  leaves: InfoLeaf[],
): Array<{ category: KeyCategory; title: string; leaves: InfoLeaf[] }> {
  const groups = new Map<KeyCategory, InfoLeaf[]>();
  for (const leaf of leaves) {
    const bucket = groups.get(leaf.category);
    if (bucket) bucket.push(leaf);
    else groups.set(leaf.category, [leaf]);
  }
  return CATEGORY_ORDER.filter((category) => groups.has(category)).map((category) => ({
    category,
    title: CATEGORY_TITLES[category],
    leaves: (groups.get(category) ?? []).sort((a, b) => a.path.localeCompare(b.path)),
  }));
}

/**
 * Отображение значения. Длинные хеши сокращаются в середине: полный
 * шестидесятичетырёхсимвольный дайджест ломает вёрстку, а первых восьми
 * символов достаточно для сверки глазом. Полное значение остаётся в `title`.
 */
export function formatLeafValue(leaf: InfoLeaf): string {
  if (leaf.value === null) return "н/д";
  if (typeof leaf.value === "boolean") return leaf.value ? "да" : "нет";
  if (typeof leaf.value === "number") {
    if (Number.isInteger(leaf.value)) return String(leaf.value);
    return leaf.value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }
  return leaf.value;
}

export function shortenHash(value: string, keep = 8): string {
  if (value.length <= keep * 2 + 1) return value;
  return `${value.slice(0, keep)}…${value.slice(-keep)}`;
}
