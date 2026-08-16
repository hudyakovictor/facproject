import type { ResearchPhoto } from "../../shared/researchApi";
import { columnById } from "./columns";

/**
 * Экспорт выбранных строк (§7.4).
 *
 * Выгружаются те же колонки, что видны на экране, и в том же виде: «н/д»
 * остаётся «н/д». Подстановка пустой строки вместо него в файле неотличима от
 * измеренного пустого значения.
 */
function cell(value: string): string {
  return /[",\n;]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function buildCsv(
  photos: readonly ResearchPhoto[],
  visibleColumns: readonly string[],
): string {
  const columns = visibleColumns
    .map((id) => columnById(id))
    .filter((column): column is NonNullable<typeof column> => Boolean(column));

  const header = [
    "# НЕ ВЕРДИКТ: технический результат измерений, не заключение о личности.",
    `# exported_at: ${new Date().toISOString()}`,
    `# rows: ${photos.length}`,
    "# «н/д» означает, что backend значения не прислал.",
  ].join("\n");

  const titles = columns.map((column) => cell(column.header)).join(",");
  const rows = photos.map((photo) =>
    columns.map((column) => cell(column.render(photo))).join(","),
  );

  return [header, titles, ...rows].join("\n");
}
