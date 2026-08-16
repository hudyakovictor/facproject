import type { ResearchPhoto } from "./researchApi";

/**
 * Каталог метрик таймлайна: группа, единица измерения, система координат,
 * статус калибровки.
 *
 * Источник каталога — этот файл, а не backend. `/api/v1/run/summary` отдаёт
 * только `source_mode`, `not_a_verdict` и `technical_summary`; поля
 * `metric_catalog` в ответе нет (оно упоминается лишь в
 * `app6/api/key_catalog.py` как описание ключа). Пока backend не начнёт
 * присылать каталог (задача B-09), подписи ведутся здесь и помечаются в
 * интерфейсе как описание на стороне клиента — иначе пользователь примет их
 * за метаданные, пришедшие вместе с числами.
 *
 * Ответственность за соответствие подписи и величины лежит на этом файле:
 * назвать сырую диагностическую величину «калиброванной» значит превратить
 * измерение в утверждение, которого расчёт не делал.
 */

/** Группы из §8.1 ТЗ. Порядок определяет порядок разделов в меню. */
export const METRIC_GROUPS = [
  "pose",
  "quality",
  "descriptors",
  "mesh",
  "chronology",
  "texture",
  "calibration",
] as const;

export type MetricGroup = (typeof METRIC_GROUPS)[number];

export const METRIC_GROUP_LABELS: Record<MetricGroup, string> = {
  pose: "Поза",
  quality: "Качество",
  descriptors: "Дескрипторы",
  mesh: "Геометрия меша",
  chronology: "Хронология",
  texture: "Диагностика текстуры",
  calibration: "Калиброванные z-оценки",
};

/**
 * Статус величины.
 *
 * `calibrated` — величина приведена к базовой линии калибровки и сопоставима
 * между кадрами. `diagnostic` — сырой признак: пригоден, чтобы заметить
 * аномалию, но не для утверждений о тождестве. Разделение существует, потому
 * что смешивать их на одной шкале — значит придавать сырому признаку вес
 * измерения.
 */
export type MetricStatus = "calibrated" | "diagnostic";

export interface MetricDescriptor {
  id: string;
  label: string;
  group: MetricGroup;
  /** Единица измерения. `null` — величина безразмерна. */
  unit: string | null;
  /** Система координат / база отсчёта. */
  space: string;
  status: MetricStatus;
  /** Диапазон для нормализации дорожки; `null` — считать по данным. */
  domain: [number, number] | null;
  /** Извлечение значения. Отсутствие величины — `null`, никогда не 0. */
  valueOf: (photo: ResearchPhoto) => number | null;
}

/** Числовое поле или null. Ноль — законное значение и сохраняется. */
function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export const METRIC_CATALOG: readonly MetricDescriptor[] = [
  {
    id: "yaw",
    label: "Yaw",
    group: "pose",
    unit: "°",
    space: "камера, поворот вокруг вертикальной оси",
    status: "diagnostic",
    domain: [-90, 90],
    valueOf: (p) => num(p.yaw),
  },
  {
    id: "pitch",
    label: "Pitch",
    group: "pose",
    unit: "°",
    space: "камера, наклон вперёд/назад",
    status: "diagnostic",
    domain: [-45, 45],
    valueOf: (p) => num(p.pitch),
  },
  {
    id: "roll",
    label: "Roll",
    group: "pose",
    unit: "°",
    space: "камера, крен в плоскости кадра",
    status: "diagnostic",
    domain: [-45, 45],
    valueOf: (p) => num(p.roll),
  },
  {
    id: "quality",
    label: "Качество кадра",
    group: "quality",
    unit: null,
    space: "нормировано 0…1",
    status: "diagnostic",
    domain: [0, 1],
    valueOf: (p) => num(p.quality),
  },
  {
    id: "confidence",
    label: "Уверенность измерения",
    group: "quality",
    unit: null,
    space: "нормировано 0…1",
    status: "diagnostic",
    domain: [0, 1],
    valueOf: (p) => num(p.confidence),
  },
  {
    id: "p0",
    label: "PC 0",
    group: "descriptors",
    unit: null,
    space: "главная компонента формы, единицы модели",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.p0),
  },
  {
    id: "p1",
    label: "PC 1",
    group: "descriptors",
    unit: null,
    space: "главная компонента формы, единицы модели",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.p1),
  },
  {
    id: "p2",
    label: "PC 2",
    group: "descriptors",
    unit: null,
    space: "главная компонента формы, единицы модели",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.p2),
  },
  {
    id: "boneScore",
    label: "Костная основа",
    group: "mesh",
    unit: null,
    space: "сводная оценка по меш-признакам, 0…1",
    status: "diagnostic",
    domain: [0, 1],
    valueOf: (p) => num(p.boneScore),
  },
  {
    id: "orbit",
    label: "Глазница",
    group: "mesh",
    unit: null,
    space: "меш BFM, нормировано",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.orbit),
  },
  {
    id: "chin",
    label: "Подбородок",
    group: "mesh",
    unit: null,
    space: "меш BFM, нормировано",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.chin),
  },
  {
    id: "jaw",
    label: "Челюсть",
    group: "mesh",
    unit: null,
    space: "меш BFM, нормировано",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.jaw),
  },
  {
    id: "cheek",
    label: "Скула",
    group: "mesh",
    unit: null,
    space: "меш BFM, нормировано",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.cheek),
  },
  {
    id: "symmetry",
    label: "Симметрия",
    group: "mesh",
    unit: null,
    space: "меш BFM, нормировано",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.symmetry),
  },
  {
    id: "visualAge",
    label: "Визуальный возраст",
    group: "chronology",
    unit: "лет",
    space: "оценка модели",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.visualAge),
  },
  {
    id: "calendarAge",
    label: "Календарный возраст",
    group: "chronology",
    unit: "лет",
    space: "по дате кадра",
    status: "diagnostic",
    domain: null,
    valueOf: (p) => num(p.calendarAge),
  },
  {
    id: "skinQuality",
    label: "Качество кожи",
    group: "texture",
    unit: null,
    space: "диагностика текстуры, 0…1",
    status: "diagnostic",
    domain: [0, 1],
    valueOf: (p) => num(p.skinQuality),
  },
  {
    id: "wrinkleDensity",
    label: "Плотность морщин",
    group: "texture",
    unit: null,
    space: "диагностика текстуры, 0…1",
    status: "diagnostic",
    domain: [0, 1],
    valueOf: (p) => num(p.wrinkleDensity),
  },
  {
    id: "subsurface",
    label: "Подповерхностное рассеяние",
    group: "texture",
    unit: null,
    space: "диагностика текстуры, 0…1",
    status: "diagnostic",
    domain: [0, 1],
    valueOf: (p) => num(p.subsurface),
  },
  {
    id: "siliconeProb",
    label: "Признак силикона",
    group: "texture",
    unit: null,
    space: "диагностический признак, 0…1",
    status: "diagnostic",
    domain: [0, 1],
    valueOf: (p) => num(p.siliconeProb),
  },
  {
    id: "fillerProb",
    label: "Признак филлера",
    group: "texture",
    unit: null,
    space: "диагностический признак, 0…1",
    status: "diagnostic",
    domain: [0, 1],
    valueOf: (p) => num(p.fillerProb),
  },
  {
    id: "zOrbitDepth",
    label: "z · глубина глазницы",
    group: "calibration",
    unit: "σ",
    space: "отклонение от базовой линии калибровки",
    status: "calibrated",
    domain: null,
    valueOf: (p) => num(p.zOrbitDepth),
  },
  {
    id: "zChinProj",
    label: "z · выступ подбородка",
    group: "calibration",
    unit: "σ",
    space: "отклонение от базовой линии калибровки",
    status: "calibrated",
    domain: null,
    valueOf: (p) => num(p.zChinProj),
  },
  {
    id: "zJawWidth",
    label: "z · ширина челюсти",
    group: "calibration",
    unit: "σ",
    space: "отклонение от базовой линии калибровки",
    status: "calibrated",
    domain: null,
    valueOf: (p) => num(p.zJawWidth),
  },
  {
    id: "zCheek",
    label: "z · скула",
    group: "calibration",
    unit: "σ",
    space: "отклонение от базовой линии калибровки",
    status: "calibrated",
    domain: null,
    valueOf: (p) => num(p.zCheek),
  },
];

export type MetricKey = string;

const BY_ID = new Map(METRIC_CATALOG.map((metric) => [metric.id, metric]));

export function metricById(id: string): MetricDescriptor | undefined {
  return BY_ID.get(id);
}

/** Подпись величины с единицей измерения. */
export function formatMetricValue(metric: MetricDescriptor, value: number | null): string {
  if (value === null) return "н/д";
  const digits = Math.abs(value) >= 100 ? 0 : Math.abs(value) >= 10 ? 1 : 2;
  return `${value.toFixed(digits)}${metric.unit ?? ""}`;
}

/**
 * Сколько кадров имеют значение метрики. Пустая метрика остаётся в списке —
 * скрыть её значило бы скрыть и факт отсутствия данных.
 */
export function availabilityOf(
  metric: MetricDescriptor,
  photos: readonly ResearchPhoto[],
): number {
  let count = 0;
  for (const photo of photos) {
    if (metric.valueOf(photo) !== null) count += 1;
  }
  return count;
}
