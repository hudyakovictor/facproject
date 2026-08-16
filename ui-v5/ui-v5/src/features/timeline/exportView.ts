import type { ResearchPhoto } from "../../shared/researchApi";
import { METRIC_CATALOG, metricById } from "../../shared/metrics";
import type { Viewport } from "./viewport";

/**
 * Экспорт текущего состояния таймлайна (§8.10 ТЗ).
 *
 * Любая выгрузка несёт маркировку: схема ответа, режим источника, границы
 * временного окна и строка «НЕ ВЕРДИКТ». Файл переживает интерфейс — попав в
 * переписку или в отчёт, таблица чисел без этой пометки читается как
 * заключение, хотя является лишь срезом отображения.
 *
 * Экспортируется именно видимое: те кадры и те метрики, что были на экране.
 * Выгружать «всё» под именем текущего вида значило бы подменить предмет.
 */

export const NOT_A_VERDICT =
  "НЕ ВЕРДИКТ: технический результат измерений, не заключение о личности.";

export interface ExportContext {
  photos: readonly ResearchPhoto[];
  metrics: readonly string[];
  viewport: Viewport;
  pose: string;
  multiPose: boolean;
  schema: string | null;
  sourceMode: string | null;
  /** Полный адрес страницы со всем состоянием вида. */
  permalink: string;
}

function isoDay(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

/** Экранирование поля CSV по RFC 4180. */
function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/**
 * CSV видимых данных. Заголовок предваряется строками-комментариями с
 * происхождением среза: без них столбец `quality` невозможно отличить от
 * чужого файла с тем же названием.
 */
export function buildCsv(context: ExportContext): string {
  const metrics = context.metrics
    .map((id) => metricById(id))
    .filter((metric): metric is NonNullable<typeof metric> => Boolean(metric));

  const header = [
    `# ${NOT_A_VERDICT}`,
    `# schema: ${context.schema ?? "неизвестна"}`,
    `# source_mode: ${context.sourceMode ?? "неизвестен"}`,
    `# viewport: ${isoDay(context.viewport.start)} … ${isoDay(context.viewport.end)}`,
    `# pose_bin: ${context.multiPose ? "мультиракурс" : context.pose}`,
    `# exported_at: ${new Date().toISOString()}`,
    `# rows: ${context.photos.length}`,
  ].join("\n");

  const columns = ["id", "date", "bucket", "era", "is_finding", ...metrics.map((m) => m.id)];
  const unitRow = [
    "",
    "",
    "",
    "",
    "",
    ...metrics.map((m) => `${m.unit ?? "безразмерн."} · ${m.status}`),
  ];

  const rows = context.photos.map((photo) =>
    [
      csvCell(photo.id),
      csvCell(photo.date ?? ""),
      csvCell(photo.bucket),
      csvCell(photo.era),
      csvCell((photo.flags?.length ?? 0) > 0),
      ...metrics.map((metric) => {
        const value = metric.valueOf(photo);
        // Пустая ячейка, а не 0: подстановка нуля превратила бы отсутствие
        // измерения в измеренное значение.
        return value === null ? "" : csvCell(value);
      }),
    ].join(","),
  );

  return [header, columns.join(","), unitRow.join(","), ...rows].join("\n");
}

/** Состояние вида: позволяет воспроизвести экран, а не только числа. */
export function buildViewState(context: ExportContext): string {
  return JSON.stringify(
    {
      not_a_verdict: NOT_A_VERDICT,
      schema: context.schema,
      source_mode: context.sourceMode,
      exported_at: new Date().toISOString(),
      view: {
        viewport_start: new Date(context.viewport.start).toISOString(),
        viewport_end: new Date(context.viewport.end).toISOString(),
        pose_bin: context.pose,
        multi_pose: context.multiPose,
        visible_metrics: context.metrics,
        visible_photo_count: context.photos.length,
      },
      metric_catalog: METRIC_CATALOG.filter((metric) =>
        context.metrics.includes(metric.id),
      ).map((metric) => ({
        id: metric.id,
        label: metric.label,
        unit: metric.unit,
        space: metric.space,
        status: metric.status,
        catalog_source: "ui-v5/src/shared/metrics.ts (backend каталога не отдаёт)",
      })),
      permalink: context.permalink,
    },
    null,
    2,
  );
}

/** Сохранение файла в браузере. */
export function downloadText(filename: string, text: string, mime: string): void {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
