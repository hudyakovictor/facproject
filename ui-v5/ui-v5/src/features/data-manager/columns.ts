import type { ResearchPhoto } from "../../shared/researchApi";
import { poseFullLabel } from "../../shared/poseBins";
import { substantiveFlags } from "../../shared/findings";

/**
 * Колонки таблицы данных (§7.4 ТЗ).
 *
 * Ключевое требование раздела — каждая колонка либо показывает настоящее
 * значение, либо честно говорит, что источника нет. Прежняя реализация
 * заполняла `sha256` строкой «недоступен в API», но при этом рисовала рядом
 * зелёную галочку совпадения хеша, вычисленную из `shaMatch: false`, — то
 * есть показывала результат сверки, которой не было.
 *
 * Поэтому у каждой колонки объявлено происхождение: `stage2` — величина из
 * ответа API, `derived` — вычислено интерфейсом из присланных полей,
 * `absent` — источника нет вовсе. Колонки с `absent` доступны в выборе
 * колонок, но показывают «н/д» и объясняют причину, вместо того чтобы
 * исчезнуть: отсутствие хеша в API — это факт о системе, который оператор
 * должен видеть.
 */

export type ColumnOrigin = "stage2" | "derived" | "absent";

export interface DataColumn {
  id: string;
  header: string;
  /** Ширина в пикселях: таблица виртуализирована, ширины фиксированы. */
  width: number;
  origin: ColumnOrigin;
  /** Пояснение к происхождению — показывается в выборе колонок. */
  note?: string;
  /** Значение для сортировки и поиска. */
  value: (photo: ResearchPhoto) => string | number | null;
  /** Текст ячейки. */
  render: (photo: ResearchPhoto) => string;
  align?: "right";
  /** Входит ли колонка в набор по умолчанию. */
  default: boolean;
}

const nz = (value: number | null | undefined): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

export const DATA_COLUMNS: readonly DataColumn[] = [
  {
    id: "id",
    header: "Идентификатор",
    width: 260,
    origin: "stage2",
    value: (p) => p.id,
    render: (p) => p.id,
    default: true,
  },
  {
    id: "date",
    header: "Дата",
    width: 110,
    origin: "stage2",
    value: (p) => p.date,
    // Кадр без даты не получает подставленную: пустая дата — тоже сведение.
    render: (p) => p.date ?? "н/д",
    default: true,
  },
  {
    id: "dateProvenance",
    header: "Происхождение даты",
    width: 150,
    origin: "stage2",
    note: "Поле dateProvenanceStatus из ответа API.",
    value: (p) => p.dateProvenanceStatus ?? null,
    render: (p) => p.dateProvenanceStatus ?? "н/д",
    default: true,
  },
  {
    id: "bucket",
    header: "Ракурс",
    width: 140,
    origin: "stage2",
    value: (p) => p.bucket,
    render: (p) => poseFullLabel(p.bucket),
    default: true,
  },
  {
    id: "quality",
    header: "Качество",
    width: 90,
    origin: "stage2",
    align: "right",
    value: (p) => nz(p.quality),
    render: (p) => (nz(p.quality) === null ? "н/д" : `${Math.round(p.quality! * 100)}%`),
    default: true,
  },
  {
    id: "yaw",
    header: "Yaw",
    width: 80,
    origin: "stage2",
    align: "right",
    value: (p) => nz(p.yaw),
    render: (p) => (nz(p.yaw) === null ? "н/д" : `${p.yaw!.toFixed(1)}°`),
    default: false,
  },
  {
    id: "stage",
    header: "Стадия",
    width: 100,
    origin: "stage2",
    value: (p) => p.analysisStage,
    render: (p) => p.analysisStage,
    default: true,
  },
  {
    id: "evidence",
    header: "Доказательная база",
    width: 140,
    origin: "stage2",
    value: (p) => p.evidenceState ?? null,
    render: (p) => p.evidenceState ?? "н/д",
    default: false,
  },
  {
    id: "pairs",
    header: "Пар",
    width: 70,
    origin: "stage2",
    align: "right",
    value: (p) => nz(p.stage2PairCount),
    render: (p) => (nz(p.stage2PairCount) === null ? "н/д" : String(p.stage2PairCount)),
    default: false,
  },
  {
    id: "flags",
    header: "Отметки",
    width: 220,
    origin: "derived",
    note: "Содержательные флаги из flags, отфильтрованные shared/findings.ts.",
    value: (p) => substantiveFlags(p).join(" "),
    render: (p) => {
      const flags = substantiveFlags(p);
      return flags.length ? flags.join(", ") : "—";
    },
    default: true,
  },
  {
    id: "exifAnomaly",
    header: "Аномалия EXIF",
    width: 130,
    origin: "stage2",
    value: (p) => (p.exifAnomaly ? 1 : 0),
    render: (p) => (p.exifAnomaly ? "да" : "нет"),
    default: false,
  },
  {
    id: "era",
    header: "Эпоха",
    width: 120,
    origin: "stage2",
    value: (p) => p.era,
    render: (p) => p.era,
    default: false,
  },
  {
    id: "sha256",
    header: "SHA-256",
    width: 130,
    origin: "absent",
    note: "В списке кадров хеша нет: /api/v1/timeline его не отдаёт. Значение есть в info.json конкретного кадра (source_digest) и доступно через /api/v1/photos/{id}/info_keys — оно показано в панели деталей. Для колонки нужен hash в списочном ответе (B-02).",
    value: () => null,
    render: () => "н/д",
    default: false,
  },
  {
    id: "duplicate",
    header: "Дубликат",
    width: 120,
    origin: "absent",
    note: "Stage 1 считает perceptual_dhash и near_duplicate_of, но /api/v1/timeline их не отдаёт. Значения видны в панели деталей кадра. Показывать пустую ячейку как «дубликатов нет» нельзя (B-02).",
    value: () => null,
    render: () => "н/д",
    default: false,
  },
  {
    id: "rights",
    header: "Права",
    width: 120,
    origin: "absent",
    note: "Лицензия и статус прав хранятся в sidecar, которого API пока не отдаёт (B-02).",
    value: () => null,
    render: () => "н/д",
    default: false,
  },
];

export const DEFAULT_COLUMN_IDS = DATA_COLUMNS.filter((column) => column.default).map(
  (column) => column.id,
);

export function columnById(id: string): DataColumn | undefined {
  return DATA_COLUMNS.find((column) => column.id === id);
}

/** Есть ли у колонки источник данных. */
export function isBackedByData(column: DataColumn): boolean {
  return column.origin !== "absent";
}
