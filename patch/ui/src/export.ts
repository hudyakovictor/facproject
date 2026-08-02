import type { Photo } from "./data";
import type { DataMode } from "./api";

export const ANALYSIS_EXPORT_SCHEMA = "deeputin.analysis-export.v1";

export interface AnalysisExportInput {
  photos: Photo[];
  totalPhotos: number;
  dataMode: DataMode;
  dataMessage: string;
  filters: Record<string, unknown>;
}

/** Медиана (не среднее): устойчива к выбросам, которых в архиве 1999–2025
 * заведомо много из-за разного качества съёмки. */
function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function countBy<T extends string>(rows: Photo[], pick: (p: Photo) => T): Record<string, number> {
  const out: Record<string, number> = {};
  for (const row of rows) {
    const key = pick(row);
    out[key] = (out[key] ?? 0) + 1;
  }
  return out;
}

/** 🏭 Собрать машиночитаемый срез текущей выборки.
 *
 * ТЗ требует «экспорта результатов ... JSON для интеграции с другими
 * системами». Ранее единственным экспортом был `document.write` HTML-текста в
 * новое окно — его нельзя ни распарсить, ни приложить к отчёту как данные.
 *
 * Инварианты, которые обязан сохранять экспорт:
 *   * `source_mode` и `not_a_verdict` едут вместе с данными, чтобы demo-срез
 *     невозможно было принять за результат исследования;
 *   * агрегаты считаются как медианы и явно подписаны как таковые;
 *   * фильтры сохраняются целиком — иначе цифры невоспроизводимы.
 */
export function buildAnalysisExport(input: AnalysisExportInput): Record<string, unknown> {
  const { photos, totalPhotos, dataMode, dataMessage, filters } = input;
  const anomalyLabels = new Set(["IDENTITY_ANOMALY", "GEOMETRIC_MISMATCH", "TEMPORAL_IMPOSSIBILITY"]);
  const anomalies = photos.filter(p => anomalyLabels.has(p.fuzzy));

  return {
    schema: ANALYSIS_EXPORT_SCHEMA,
    created_at: new Date().toISOString(),
    // Режим данных — часть контракта: demo-срез не должен маскироваться
    // под результат исследования.
    source_mode: dataMode,
    source_note: dataMessage,
    not_a_verdict: true,
    disclaimer:
      "Исследовательский сигнал, а не установление личности. Требуется проверка " +
      "происхождения изображений и независимая экспертиза.",
    selection: {
      photos_in_selection: photos.length,
      photos_total: totalPhotos,
      filters,
    },
    distribution: {
      by_pose_bin: countBy(photos, p => p.bucket),
      by_era: countBy(photos, p => p.era),
      by_hypothesis: countBy(photos, p => p.dominant),
      by_evidence_state: countBy(photos, p => p.fuzzy),
    },
    aggregates_median: {
      note: "медианы по текущей выборке; не сравнивать между разными pose bins",
      boneScore: median(photos.map(p => p.boneScore)),
      quality: median(photos.map(p => p.quality)),
      confidence: median(photos.map(p => p.confidence)),
      p0: median(photos.map(p => p.p0)),
      p1: median(photos.map(p => p.p1)),
      p2: median(photos.map(p => p.p2)),
    },
    anomalies: {
      count: anomalies.length,
      photo_ids: anomalies.map(p => p.id),
    },
    photos: photos.map(p => ({
      id:p.id,date:p.date,pose_bin:p.bucket,era:p.era,provenance:{date_authority:"filename",date_status:p.dateProvenanceStatus??"unknown",exif_date:p.exifDate??null,date_delta_days:p.dateDeltaDays??null,source_claimed_date:p.sourceClaimedDate??null,source_claimed_delta_days:p.sourceClaimedDeltaDays??null,conflict_sources:p.dateConflictSources??[],chronology_limited:p.dateProvenanceLimited??false},
      quality: p.quality, confidence: p.confidence,
      boneScore: p.boneScore, symmetry: p.symmetry,
      hypothesis: { H0: p.p0, H1: p.p1, H2: p.p2, dominant: p.dominant },
      evidence_state: p.fuzzy,
      flags: p.flags,
      z_scores: {
        orbit_depth: p.zOrbitDepth, chin_projection: p.zChinProj,
        jaw_width: p.zJawWidth, cheek: p.zCheek,
      },
    })),
  };
}

/** Скачать срез как .json-файл. */
export function exportAnalysisJson(input: AnalysisExportInput): void {
  const payload = buildAnalysisExport(input);
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  anchor.download = `deeputin-analysis-${input.dataMode}-${stamp}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

// =============================================================================
// Печатный отчёт
// =============================================================================

export interface PrintReportInput extends AnalysisExportInput {
  playheadT: number;
  currentEra: string;
  events: { t: number; title: string; tooltip: string; source: string }[];
}

/** Экранирование HTML: данные попадают в разметку и не должны её ломать.
 *
 * Подписи событий приходят из набора данных; без экранирования кавычка или
 * `<` в источнике сломала бы документ, а `<script>` — исполнился бы. */
function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char] as string));
}

/** 🏭 Собрать печатный HTML-отчёт текущей выборки.
 *
 * Заменяет прежний `document.write` в пустое окно. Тот подход был плох
 * трижды: разметка собиралась конкатенацией без экранирования (подпись
 * события с `<` ломала документ), `document.write` после загрузки страницы
 * устарел и блокируется частью браузеров, а результат нельзя было ни
 * сохранить осмысленным файлом, ни напечатать без артефактов.
 *
 * Отчёт — самостоятельный документ со стилями `@media print`: тёмная тема
 * экрана превращается в чёрное на белом, служебные элементы скрываются,
 * таблицы не рвутся между страницами.
 */
export function buildPrintReport(input: PrintReportInput): string {
  const { photos, totalPhotos, dataMode, dataMessage, filters, playheadT, currentEra, events } = input;
  const stamp = new Date().toLocaleString("ru-RU");
  const anomalies = photos.filter(
    p => !["CONSISTENT", "STRONGLY_MATCHING"].includes(p.fuzzy)).length;

  const med = (pick: (p: Photo) => number) => {
    const value = median(photos.map(pick).filter(Number.isFinite));
    return value === null ? "—" : value.toFixed(3);
  };

  const eventRows = events.map(event => `
    <tr>
      <td>${escapeHtml(new Date(event.t).toLocaleDateString("ru-RU"))}</td>
      <td>${escapeHtml(event.title)}</td>
      <td>${escapeHtml(event.tooltip)}</td>
      <td>${escapeHtml(event.source)}</td>
    </tr>`).join("");

  // 🚨 Демо-срез обязан быть отличим от исследования в напечатанном виде:
  // бумажную копию нельзя переспросить о происхождении.
  const demoBanner = dataMode === "research" ? "" : `
    <p class="banner">Демонстрационные данные. Не результат исследования.
    ${escapeHtml(dataMessage)}</p>`;

  return `<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>DEEPUTIN · отчёт форензики</title>
<style>
  :root { color-scheme: light; }
  body { font: 13px/1.5 ui-monospace, "JetBrains Mono", monospace;
         color: #1a1a1a; background: #fff; margin: 0; padding: 24px; }
  h1 { font-size: 20px; margin: 0 0 4px; letter-spacing: .04em; }
  h2 { font-size: 14px; margin: 24px 0 8px; letter-spacing: .06em;
       border-bottom: 1px solid #ccc; padding-bottom: 4px; }
  .sub { color: #666; font-size: 11px; margin: 0 0 16px; }
  .banner { background: #fff4d6; border-left: 3px solid #d19a00;
            padding: 8px 12px; margin: 12px 0; }
  .notice { background: #eef4fb; border-left: 3px solid #2783de;
            padding: 8px 12px; margin: 12px 0; font-size: 11px; }
  table { border-collapse: collapse; width: 100%; font-size: 11px; }
  th, td { border: 1px solid #ddd; padding: 4px 6px; text-align: left;
           vertical-align: top; }
  th { background: #f4f4f4; }
  .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .card { border: 1px solid #ddd; padding: 8px; }
  .card b { display: block; font-size: 18px; }
  .card span { color: #666; font-size: 10px; }
  footer { margin-top: 24px; padding-top: 8px; border-top: 1px solid #ccc;
           color: #666; font-size: 10px; }
  @media print {
    /* Бумага светлая: экранная тёмная тема на печати нечитаема и
       расходует тонер. Ссылки бесполезны — раскрываем URL текстом. */
    body { padding: 0; font-size: 11px; }
    h2 { page-break-after: avoid; }
    tr, .card { page-break-inside: avoid; }
    thead { display: table-header-group; }
    .no-print { display: none; }
    a[href]::after { content: " (" attr(href) ")"; }
    @page { margin: 16mm; }
  }
</style></head>
<body>
<h1>DEEPUTIN · отчёт форензики</h1>
<p class="sub">Сформирован ${escapeHtml(stamp)} · режим данных: ${escapeHtml(dataMode)}
 · схема ${escapeHtml(ANALYSIS_EXPORT_SCHEMA)}</p>
${demoBanner}
<p class="notice">Документ фиксирует наблюдаемые измерения и их статусы.
Ни один статус сам по себе не доказывает подмену личности, маску или
операцию. Отчёт не является заключением.</p>

<h2>Охват выборки</h2>
<div class="grid">
  <div class="card"><b>${photos.length}</b><span>фото в выборке</span></div>
  <div class="card"><b>${totalPhotos}</b><span>всего в наборе</span></div>
  <div class="card"><b>${anomalies}</b><span>аномальных сигналов</span></div>
  <div class="card"><b>${escapeHtml(currentEra)}</b><span>сегмент курсора</span></div>
</div>
<p class="sub">Курсор хронологии: ${escapeHtml(new Date(playheadT).toLocaleDateString("ru-RU"))}</p>

<h2>Медианы по выборке</h2>
<table><thead><tr><th>Показатель</th><th>Медиана</th></tr></thead><tbody>
  <tr><td>Костный индекс</td><td>${med(p => p.boneScore)}</td></tr>
  <tr><td>Качество кадра</td><td>${med(p => p.quality)}</td></tr>
  <tr><td>P(H0)</td><td>${med(p => p.p0)}</td></tr>
  <tr><td>P(H1)</td><td>${med(p => p.p1)}</td></tr>
  <tr><td>P(H2)</td><td>${med(p => p.p2)}</td></tr>
</tbody></table>
<p class="sub">Медиана, а не среднее: архив 1999–2025 содержит кадры резко
разного качества, и среднее по ним смещается выбросами.</p>

<h2>События хронологии</h2>
${events.length
    ? `<table><thead><tr><th>Дата</th><th>Событие</th><th>Описание</th><th>Источник</th></tr></thead><tbody>${eventRows}</tbody></table>`
    : "<p class=\"sub\">Событий в выборке нет.</p>"}

<h2>Параметры фильтрации</h2>
<table><thead><tr><th>Параметр</th><th>Значение</th></tr></thead><tbody>
${Object.entries(filters).map(([key, value]) =>
    `<tr><td>${escapeHtml(key)}</td><td>${escapeHtml(
      value instanceof Set ? [...value].join(", ") : JSON.stringify(value))}</td></tr>`).join("")}
</tbody></table>
<p class="sub">Фильтры приведены целиком: без них приведённые числа
невоспроизводимы.</p>

<footer>${escapeHtml(dataMessage)} · not_a_verdict: true</footer>
</body></html>`;
}

/** Открыть печатный отчёт как самостоятельный документ.
 *
 * Через Blob-URL, а не `document.write`: последний после загрузки страницы
 * помечен как устаревший и в части браузеров игнорируется, а окно остаётся
 * пустым без единого сообщения об ошибке.
 */
export function openPrintReport(input: PrintReportInput): boolean {
  const html = buildPrintReport(input);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const win = window.open(url, "_blank", "noopener,noreferrer");
  // Блокировщик всплывающих окон — штатная ситуация: сообщаем вызывающему
  // коду, чтобы он показал пользователю причину, а не молчал.
  if (!win) {
    URL.revokeObjectURL(url);
    return false;
  }
  // Освобождаем URL после того, как окно успело загрузиться.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return true;
}
