// Synthetic but deterministic dataset for DeepUtin Forensic Timeline Suite
// All numbers derived from a seeded PRNG so render is stable.

/** Идентификатор сегмента хронологии.
 *
 * ⚠️ НЕ жёсткий union: backend возвращает собственные идентификаторы
 * (`DEMO_SEGMENT_1..5` в demo-режиме, `STAGE2_RESEARCH` в research), и они
 * НЕ совпадают со встроенным демо-набором. Прежний закрытый union приводил к
 * тому, что фильтр эпох отбрасывал 100% строк из API, и таймлайн молча
 * оставался пустым. Единственный источник истины о сегментах — поле
 * `era_meta` ответа `/api/v1/timeline`; локальные `ERA_*` ниже — только
 * fallback для встроенного демо-набора. */
export type Era = string;

/** Метаданные одного сегмента хронологии. */
export interface EraMeta { label: string; color: string; start: string; end: string; short: string }
export type PoseBucket = "left_profile" | "left_deep" | "left_mid" | "left_light" | "frontal" | "right_light" | "right_mid" | "right_deep" | "right_profile";
export type FuzzyLabel =
  | "STRONGLY_MATCHING"
  | "CONSISTENT"
  | "INSUFFICIENT_DATA"
  | "WEAK_EVIDENCE"
  | "SUSPICIOUS_TEXTURE"
  | "GEOMETRIC_MISMATCH"
  | "IDENTITY_ANOMALY"
  | "TEMPORAL_IMPOSSIBILITY";
export type Hypothesis = "H0" | "H1" | "H2";

export interface Photo {
  id: string;
  date: string; // YYYY-MM-DD
  t: number; // unix ms
  era: Era;
  bucket: PoseBucket;
  quality: number;
  hidden: boolean;
  // metrics
  boneScore: number;
  orbit: number;
  chin: number;
  jaw: number;
  cheek: number;
  symmetry: number;
  yaw: number;
  // texture
  siliconeProb: number;
  specular: number;
  lbpEntropy: number;
  frangi: number;
  wrinkle: number;
  subsurface: number;
  visualAge: number;
  calendarAge: number;
  // verdict
  p0: number;
  p1: number;
  p2: number;
  dominant: Hypothesis;
  fuzzy: FuzzyLabel;
  confidence: number;
  flags: string[];
  exifAnomaly: boolean;
  // z-scores key zones
  zOrbitDepth: number;
  zChinProj: number;
  zJawWidth: number;
  zCheek: number;
}

// Simple seeded PRNG (mulberry32)
/** Нормативная схема девяти ракурсов. Не демо-данные: этой раскладкой
 * оперирует весь пайплайн, поэтому она живёт в общем модуле. */
export const POSE_BUCKETS: PoseBucket[] = ["left_profile", "left_deep", "left_mid", "left_light", "frontal", "right_light", "right_mid", "right_deep", "right_profile"];
export const POSE_YAW: Record<PoseBucket, number> = { left_profile: -90, left_deep: -67.5, left_mid: -45, left_light: -22.5, frontal: 0, right_light: 22.5, right_mid: 45, right_deep: 67.5, right_profile: 90 };
export const POSE_LABELS: Record<PoseBucket, string> = { left_profile: "левый профиль", left_deep: "левый глубокий", left_mid: "левый средний", left_light: "левый лёгкий", frontal: "фронтальный", right_light: "правый лёгкий", right_mid: "правый средний", right_deep: "правый глубокий", right_profile: "правый профиль" };

/** Ленивая загрузка встроенного демо-набора (аудит №27).
 *
 * Генератор (170 строк + массив из 1809 объектов) вынесен в `demoData.ts`
 * и подтягивается отдельным чанком только тогда, когда backend
 * действительно недоступен. При рабочем сервере этот код не скачивается
 * и не исполняется вовсе.
 *
 * 🚨 Возвращает СИНТЕТИЧЕСКИЕ данные. Вызывающий код обязан пометить
 * результат как `source_mode: "demo"`.
 */
export async function loadDemoPhotos(): Promise<Photo[]> {
  const module = await import("./demoData");
  return module.buildDemoPhotos();
}

export const TIME_MIN = Date.parse("1999-01-01");
export const TIME_MAX = Date.parse("2026-06-30");
export const TIME_SPAN = TIME_MAX - TIME_MIN;

/** Fallback-сегменты встроенного демо-набора (`PHOTOS`).
 *
 * Используются, только когда backend недоступен. Для данных из API сегменты
 * строятся из `era_meta` ответа — см. `buildEraMeta()`. */
export const ERA_META: Record<string, EraMeta> = {
  ERA_1_BASELINE: { label: "ERA 1 · BASELINE", short: "BASELINE", color: "#4f98a3", start: "1999-08-09", end: "2011-12-31" },
  ERA_2_EARLY: { label: "ERA 2 · EARLY", short: "EARLY", color: "#e8af34", start: "2012-01-01", end: "2014-12-31" },
  ERA_3_UDMURT: { label: "ERA 3 · UDMURT", short: "UDMURT", color: "#dd6974", start: "2015-01-01", end: "2021-09-08" },
  ERA_4_TRANSITION: { label: "ERA 4 · TRANSITION", short: "TRANSITION", color: "#fdab43", start: "2021-09-09", end: "2023-09-30" },
  ERA_5_VASILICH: { label: "ERA 5 · VASILICH", short: "VASILICH", color: "#a86fdf", start: "2023-10-01", end: "2026-06-04" },
};

/** Детерминированная палитра сегментов: один и тот же идентификатор всегда
 * получает один и тот же цвет, независимо от порядка загрузки. */
const SEGMENT_PALETTE = ["#4f98a3", "#e8af34", "#dd6974", "#fdab43", "#a86fdf", "#6daa45", "#5591c7", "#a13544"];

/** 🏭 Построить таблицу сегментов из `era_meta` ответа `/api/v1/timeline`.
 *
 * Backend уже отдаёт `era_meta` (label/start/end) — менять контракт не нужно,
 * достаточно его использовать. Цвет и короткая подпись выводятся здесь, так
 * как backend их не передаёт. */
export function buildEraMeta(
  raw: Record<string, { label?: string; start?: string; end?: string }> | undefined,
  photos: Photo[],
): Record<string, EraMeta> {
  const ids = raw && Object.keys(raw).length
    ? Object.keys(raw)
    : Array.from(new Set(photos.map(p => p.era))).sort();
  if (!ids.length) return ERA_META;

  const out: Record<string, EraMeta> = {};
  ids.forEach((id, index) => {
    const entry = raw?.[id] ?? {};
    // Границы сегмента: из ответа API, иначе — из фактических дат его кадров,
    // чтобы `currentEra` и полоса эпохи работали и без era_meta.
    const own = photos.filter(p => p.era === id).map(p => p.t).sort((a, b) => a - b);
    const start = entry.start ?? (own.length ? new Date(own[0]).toISOString().slice(0, 10) : "1999-01-01");
    const end = entry.end ?? (own.length ? new Date(own[own.length - 1]).toISOString().slice(0, 10) : "2026-06-30");
    const label = entry.label ?? id;
    out[id] = {
      label,
      // Короткая подпись для тесных мест (центроиды кластеров, колонки).
      short: label.length > 14 ? `${label.slice(0, 13)}…` : label,
      color: SEGMENT_PALETTE[index % SEGMENT_PALETTE.length],
      start, end,
    };
  });
  return out;
}

export const FUZZY_COLORS: Record<FuzzyLabel, string> = {
  STRONGLY_MATCHING: "#6daa45",
  CONSISTENT: "#4f98a3",
  INSUFFICIENT_DATA: "#797876",
  WEAK_EVIDENCE: "#e8af34",
  SUSPICIOUS_TEXTURE: "#fdab43",
  GEOMETRIC_MISMATCH: "#dd6974",
  IDENTITY_ANOMALY: "#a13544",
  TEMPORAL_IMPOSSIBILITY: "#ff3b30",
};

export const HYPOTHESIS_COLORS: Record<Hypothesis, string> = {
  H0: "#6daa45",
  H1: "#fdab43",
  H2: "#a13544",
};

export interface EventPin {
  id: string;
  date: string;
  t: number;
  type: "DISAPPEARANCE" | "POLITICAL" | "AI_RESEARCH" | "REPORT" | "ERA_START" | "RTR";
  iconName: "alert-triangle" | "volume" | "flask" | "file-text" | "play" | "rotate";
  color: string;
  title: string;
  tooltip: string;
  source: string;
  folkTag?: string;
}

export const EVENT_PINS: EventPin[] = [
  { id: "ev1", date: "2015-03-06", t: Date.parse("2015-03-06"), type: "DISAPPEARANCE", iconName: "alert-triangle", color: "#e8af34",
    title: "Исчезновение 2015 года", tooltip: "10-дневное исчезновение из публичного пространства; первые публикации о двойниках (BBC, 2015).",
    source: "BBC News · 11 марта 2015", folkTag: "Удмурт (народная классификация)" },
  { id: "ev2", date: "2015-01-01", t: Date.parse("2015-01-01"), type: "ERA_START", iconName: "play", color: "#dd6974",
    title: "Начало ЭПОХИ 3 · УДМУРТ", tooltip: "Старт периода ERA_3_UDMURT. 480 фотографий. Пик гипотезы об альтерации.", source: "Пайплайн DeepUtin" },
  { id: "ev3", date: "2021-09-09", t: Date.parse("2021-09-09"), type: "ERA_START", iconName: "play", color: "#fdab43",
    title: "Начало ЭПОХИ 4 · ПЕРЕХОД", tooltip: "Старт переходной зоны. Изменение паттернов геометрии.", source: "Пайплайн DeepUtin" },
  { id: "ev4", date: "2022-05-23", t: Date.parse("2022-05-23"), type: "POLITICAL", iconName: "volume", color: "#5591c7",
    title: "Заявление Буданова", tooltip: "Глава ГУР Украины публично заявил о возможной замене. Пресс-служба Кремля отвергла версию.",
    source: "Ukrainska Pravda · май 2022", folkTag: "Говорун (народная классификация)" },
  { id: "ev5", date: "2023-04-12", t: Date.parse("2023-04-12"), type: "AI_RESEARCH", iconName: "flask", color: "#4f98a3",
    title: "Японское AI-исследование", tooltip: "Японские исследователи опубликовали анализ внешних изменений с применением нейросетей.",
    source: "Asahi Shimbun · апрель 2023" },
  { id: "ev6", date: "2023-10-01", t: Date.parse("2023-10-01"), type: "ERA_START", iconName: "play", color: "#a86fdf",
    title: "Начало ЭПОХИ 5 · ВАСИЛИЧ", tooltip: "Старт периода ERA_5_VASILICH. Текущий доминирующий кластер биометрических признаков.", source: "Пайплайн DeepUtin" },
  { id: "ev7", date: "2024-02-18", t: Date.parse("2024-02-18"), type: "REPORT", iconName: "file-text", color: "#797876",
    title: "Доклад Минченко", tooltip: "Доклад политологического агентства об управлении публичным образом и информационным полем.",
    source: "Холдинг «Минченко-консалтинг» · февраль 2024", folkTag: "Кучма (народная классификация)" },
  { id: "ev8", date: "2017-06-14", t: Date.parse("2017-06-14"), type: "RTR", iconName: "rotate", color: "#e2e2e8",
    title: "Возврат к норме (RTR)", tooltip: "Флаг RETURN_TO_BASELINE: метрики статистически откатились к эталону ЭПОХИ 1.",
    source: "Пайплайн DeepUtin · RTR_RATIO=0.81" },
  { id: "ev9", date: "2020-11-04", t: Date.parse("2020-11-04"), type: "RTR", iconName: "rotate", color: "#e2e2e8",
    title: "Возврат к норме (RTR)", tooltip: "Флаг RETURN_TO_BASELINE: метрики статистически откатились к эталону ЭПОХИ 1.",
    source: "Пайплайн DeepUtin · RTR_RATIO=0.77" },
];

// Aggregate medians per N buckets for fast track rendering
export interface TrackPoint {
  t: number;
  date: string;
  value: number;
  zScore?: number;
  flag?: "warn" | "critical" | "impossible";
}

/** Референсные медианы и разбросы встроенного демо-набора (сегмент
 * ERA_1_BASELINE).
 *
 * 🚨 WARNING: это НЕ нормативные значения исследования. Таблица —
 * fallback для встроенного демо-набора; на реальных данных baseline
 * считается из самой выборки (`ui/src/baseline.ts`, `computeBaselineRefs`)
 * и передаётся через `BaselineContext`.
 *
 * 🔧 Раньше значения вычислялись на старте функцией `refMedians()`, которая
 * прогоняла весь демо-массив из 1809 объектов. Это заставляло генератор
 * исполняться при каждой загрузке страницы — даже при работающем backend,
 * когда демо-данные не нужны ни разу (аудит №27). Значения детерминированы
 * (seeded PRNG), поэтому зафиксированы как константы; тест
 * `demoData.test.ts` проверяет, что генератор по-прежнему даёт именно их.
 */
export const REF: Record<string, { median: number; std: number }> = {
  boneScore: { median: 0.849226, std: 0.026633 },
  orbit: { median: 0.341254, std: 0.017429 },
  chin: { median: 0.459968, std: 0.023528 },
  jaw: { median: 0.519525, std: 0.015128 },
  cheek: { median: 0.480637, std: 0.016702 },
  symmetry: { median: 0.920149, std: 0.01272 },
  yaw: { median: 0.350053, std: 58.7487 },
  siliconeProb: { median: 0.145995, std: 0.032837 },
  specular: { median: 0.55072, std: 0.029295 },
  lbpEntropy: { median: 0.620603, std: 0.025908 },
  frangi: { median: 0.478001, std: 0.026101 },
  wrinkle: { median: 0.208155, std: 0.069903 },
  subsurface: { median: 0.418947, std: 0.020172 },
  visualAge: { median: 74.169065, std: 5.348968 },
};
