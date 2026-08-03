/** Подписи и раскраска ключей пайплайна для универсальных таблиц.
 *
 * Проблема, которую решает модуль: 289 невидимых ключей — это 289 подписей
 * × 2 языка = +26% к словарю `i18n.ts` (1092 ключа). Заводить их поимённо
 * означало бы удвоить стоимость каждого нового ключа Stage 2.
 *
 * Решение: подписи **выводятся из имени колонки** (снятие общего префикса
 * подгруппы + замена `_` на пробел), а переводятся только названия
 * категорий и подгрупп — их 9 и ~45. Новая колонка Stage 2 появится на
 * экране без правки словаря.
 *
 * 🚨 Правило проекта: `null` — это «нет данных», а не ноль. Отображается
 * как `—` (`format.NO_DATA`), см. `app6/AGENTS.md`.
 */
import { NO_DATA } from "./format";
import { getLanguage } from "./i18n";
import type { KeyValue } from "./api";

/** Порядок категорий в интерфейсе: от «без этого вывод неверен» к справочному. */
export const CATEGORY_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I"] as const;

/** Названия подгрупп. Латинские идентификаторы приходят из бэкенда
 * (`key_catalog._PREFIX_RULES`) и являются контрактом, а не текстом. */
const GROUP_TITLES: Record<string, { ru: string; en: string }> = {
  // A
  header: { ru: "Итог пары", en: "Pair outcome" },
  multiple_testing: { ru: "Множественные сравнения (FDR)", en: "Multiple testing (FDR)" },
  corroboration: { ru: "Корроборация по ракурсам", en: "Cross-bin corroboration" },
  primary: { ru: "Основная метрика и калибровка", en: "Primary metric and calibration" },
  limits: { ru: "Ограничения вывода", en: "Inference limits" },
  pose_leakage: { ru: "Утечка позы", en: "Pose leakage" },
  sensitivity: { ru: "Устойчивость калибровки", en: "Calibration sensitivity" },
  // B
  status: { ru: "Статус канала", en: "Channel status" },
  point_to_point: { ru: "Точка–точка", en: "Point-to-point" },
  point_to_plane: { ru: "Точка–плоскость", en: "Point-to-plane" },
  calibration: { ru: "Калибровка", en: "Calibration" },
  alignment: { ru: "Выравнивание", en: "Alignment" },
  coverage: { ru: "Покрытие", en: "Coverage" },
  zones: { ru: "Зоны", en: "Zones" },
  space: { ru: "Пространство сравнения", en: "Comparison space" },
  artifact: { ru: "Артефакт", en: "Artifact" },
  // C
  frame_quality: { ru: "Качество кадров", en: "Frame quality" },
  zone_coverage: { ru: "Зонное покрытие", en: "Zone coverage" },
  expression: { ru: "Мимика", en: "Expression" },
  applicability: { ru: "Применимость метрик", en: "Metric applicability" },
  frame_inputs: { ru: "Параметры кадра", en: "Frame parameters" },
  frame_summary: { ru: "Сводка качества", en: "Quality summary" },
  pose: { ru: "Поза", en: "Pose" },
  // D
  point_motion: { ru: "Движение точек", en: "Point motion" },
  descriptors: { ru: "Дескрипторы формы", en: "Shape descriptors" },
  anchors: { ru: "Опорные точки", en: "Anchors" },
  residual_transform: { ru: "Остаточное преобразование", en: "Residual transform" },
  contract: { ru: "Контракт разметки", en: "Landmark contract" },
  // E
  channels: { ru: "Текстурные каналы", en: "Texture channels" },
  structure: { ru: "Структура кожи", en: "Skin structure" },
  provenance: { ru: "Провенанс", en: "Provenance" },
  // F
  rate: { ru: "Темп изменений", en: "Rate of change" },
  identity_vs_expression: { ru: "Идентичность и мимика", en: "Identity vs expression" },
  leads: { ru: "Лиды", en: "Leads" },
  date: { ru: "Дата", en: "Date" },
  events: { ru: "События", en: "Events" },
  // G
  source: { ru: "Источник", en: "Source" },
  pair_identity: { ru: "Идентификация пары", en: "Pair identity" },
  reproducibility: { ru: "Воспроизводимость", en: "Reproducibility" },
  integrity: { ru: "Целостность", en: "Integrity" },
  camera: { ru: "Камера", en: "Camera" },
  normalization: { ru: "Нормализация", en: "Normalization" },
  crop: { ru: "Кроп", en: "Crop" },
  image: { ru: "Изображение", en: "Image" },
  // H
  mask: { ru: "Маски", en: "Masks" },
  uv: { ru: "UV-развёртка", en: "UV unwrap" },
  files: { ru: "Файлы артефактов", en: "Artifact files" },
  reprojection: { ru: "Репроекция", en: "Reprojection" },
  other: { ru: "Прочее", en: "Other" },
  // I
  summary: { ru: "Сводка прогона", en: "Run summary" },
};

/** Человекочитаемое название подгруппы. */
export function groupTitle(id: string): string {
  const entry = GROUP_TITLES[id];
  if (!entry) return id.replace(/_/g, " ");
  return getLanguage() === "en" ? entry.en : entry.ru;
}

/** Общий префикс группы колонок, который можно снять из подписей.
 *
 * Для группы `mesh_point_to_plane_*` подписи «rmse / median / p95» читаются
 * лучше, чем «mesh point to plane rmse» четыре раза подряд. Префикс
 * снимается только если он общий для ВСЕХ ключей группы и после снятия ни
 * одна подпись не становится пустой. */
export function commonPrefix(keys: string[]): string {
  if (keys.length < 2) return "";
  const parts = keys.map(k => k.split("_"));
  let shared = 0;
  const limit = Math.min(...parts.map(p => p.length)) - 1;
  while (shared < limit && parts.every(p => p[shared] === parts[0][shared])) shared++;
  if (shared === 0) return "";
  return parts[0].slice(0, shared).join("_") + "_";
}

/** Подпись ключа: снимается общий префикс, `_` → пробел. */
export function keyLabel(key: string, prefix = ""): string {
  const bare = prefix && key.startsWith(prefix) ? key.slice(prefix.length) : key;
  return (bare || key).replace(/_/g, " ");
}

/** Строковые статусы, означающие проблему. Раскраска ТОЛЬКО по явному
 * статусу из пайплайна — интерфейс не выводит собственных суждений. */
const BAD_STATUS = /(^|_)(limited|failed|error|exceeded|flagged|leak|unsupported|inapplicable|insufficient|missing|not_measurable|conflict)/;
const WARN_STATUS = /(^|_)(uncertain|elevated|partial|degraded|uncalibrated|fallback|warning|candidate|dominated)/;
const GOOD_STATUS = /(^|_)(ok|pass|complete|measured|calibrated|within|supported|nominal|matched|corroborated)/;

export type KeyTone = "bad" | "warn" | "good" | "neutral";

/** Тон значения по его собственному содержанию.
 *
 * Булев ключ трактуется по имени: `*_limited: true` — плохо, `*_supported:
 * true` — хорошо. Числа не раскрашиваются никогда: пороги задаёт пайплайн,
 * а не интерфейс. */
export function keyTone(key: string, value: KeyValue): KeyTone {
  if (value === null) return "neutral";
  if (typeof value === "boolean") {
    const negative = BAD_STATUS.test(key);
    if (negative) return value ? "bad" : "good";
    if (GOOD_STATUS.test(key) || /supported|significant/.test(key)) return value ? "good" : "warn";
    return "neutral";
  }
  if (typeof value === "string") {
    const low = value.toLowerCase();
    if (BAD_STATUS.test(low)) return "bad";
    if (WARN_STATUS.test(low)) return "warn";
    if (GOOD_STATUS.test(low)) return "good";
  }
  return "neutral";
}

export const TONE_COLORS: Record<KeyTone, string | undefined> = {
  bad: "#dd6974",
  warn: "#e8af34",
  good: "#6daa45",
  neutral: undefined,
};

/** Отображаемое значение. Длинные хэши усекаются с сохранением начала —
 * полное значение остаётся в `title` ячейки. */
export function formatKeyValue(value: KeyValue, digits = 4): string {
  if (value === null) return NO_DATA;
  if (typeof value === "boolean") return value ? "да" : "нет";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return NO_DATA;
    if (Number.isInteger(value)) return String(value);
    const abs = Math.abs(value);
    // Очень мелкие значения (q-value, p-value) в фиксированной точности
    // превратились бы в «0.0000» — это неотличимо от нуля.
    if (abs > 0 && abs < 1e-3) return value.toExponential(2);
    return value.toFixed(digits);
  }
  return value;
}

/** Значение помещается в одну строку таблицы (иначе — блок под ключом). */
export function isLongValue(value: KeyValue): boolean {
  return typeof value === "string" && value.length > 44;
}

/** Доля заполненных ключей группы — честный индикатор охвата. */
export function filledCount(values: Record<string, KeyValue>): number {
  return Object.values(values).filter(v => v !== null).length;
}

/** Уплощение вложенной структуры Stage 1 `info.json` в «путь → значение».
 *
 * Глубина `info.json` до трёх уровней (`crop.letterbox.offset_x`), а массивы
 * (`principal_point`, `channel_names`) остаются значениями и сериализуются
 * как есть — интерфейс не должен их интерпретировать. */
export function flattenKeys(node: unknown, prefix = ""): Record<string, KeyValue> {
  const out: Record<string, KeyValue> = {};
  if (node === null || node === undefined) {
    if (prefix) out[prefix] = null;
    return out;
  }
  if (Array.isArray(node)) {
    out[prefix] = node.length ? node.map(v => String(v)).join(", ") : null;
    return out;
  }
  if (typeof node === "object") {
    for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
      Object.assign(out, flattenKeys(value, prefix ? `${prefix}.${key}` : key));
    }
    return out;
  }
  if (typeof node === "number" && !Number.isFinite(node)) {
    out[prefix] = null;
    return out;
  }
  out[prefix] = node as KeyValue;
  return out;
}
