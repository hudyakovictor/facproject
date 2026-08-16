import React, { useMemo, useState } from "react";
import { AlertTriangle, FileText } from "lucide-react";
import {
  useReportSection,
  useReportSummary,
  useRunArtifact,
  useRunSummary,
  useTimeline,
} from "../../shared/api/queries";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { ErrorState, LoadingState } from "../../shared/ui/states";
import { sortPhotosByTime } from "../../shared/time";

/**
 * Экран отчёта Stage 3.
 *
 * Раньше здесь была заглушка с текстом «отчёт пока не сформирован», хотя
 * backend отдаёт `/api/v1/report/summary` и `/api/v1/report/sections/{name}`.
 * Теперь экран читает реальный перечень секций, а отсутствие прогона
 * Stage 3 показывается как штатное состояние, а не как сбой.
 *
 * Список секций не зашит в UI: его задаёт Stage 3, и добавленная на backend
 * секция появится здесь без правки фронтенда.
 */

const PAGE_SIZE = 50;

function preview(value: unknown): string {
  if (value == null) return "н/д";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2) ?? String(value);
  } catch {
    return String(value);
  }
}

export const ReportsPage: React.FC = () => {
  const timeline = useTimeline();
  const runSummary = useRunSummary();
  const report = useReportSummary();

  const [section, setSection] = useState<string | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const sectionQuery = useReportSection(section, offset, PAGE_SIZE);
  const artifactQuery = useRunArtifact(selectedArtifact);

  const photos = sortPhotosByTime(timeline.data?.photos ?? []).dated;
  const technical = runSummary.data?.technical_summary;
  const artifacts = runSummary.data?.artifacts ?? [];
  const presentArtifacts = artifacts.filter((item) => item.present);
  const stage = resolveStage(timeline.data);

  const sections = useMemo(() => report.data?.sections ?? [], [report.data]);
  const narrative = report.data?.narrative ?? [];

  if (timeline.isLoading || runSummary.isLoading) {
    return <LoadingState text="Загрузка сведений о запуске…" />;
  }
  if (timeline.error || runSummary.error) {
    return (
      <ErrorState
        title="Сведения о запуске недоступны"
        error={timeline.error ?? runSummary.error}
        onRetry={() => {
          void timeline.refetch();
          void runSummary.refetch();
        }}
      />
    );
  }

  const reportMissing = Boolean(report.error);

  return (
    <div className="flex h-workspace w-full flex-col space-y-5 overflow-y-auto bg-surface-canvas p-6 text-ink-primary">
      <StageBanner stage={stage} note={timeline.data?.note} />

      <header className="rounded-lg border border-cyan-600 bg-surface-base p-5">
        <div className="flex items-center gap-2 font-mono text-sm font-bold text-cyan-300">
          <FileText className="h-5 w-5" /> ОТЧЁТ ПО ЗАПУСКУ · {stageLabel(stage)}
        </div>
        <p className="mt-2 text-xs text-ink-secondary">
          Здесь собраны результаты текущего запуска и доступные материалы анализа.
          Пустые разделы не заменяются демонстрационными данными.
        </p>
      </header>

      {reportMissing && (
        <section className="rounded-lg border border-amber-500/80 bg-amber-950/20 p-5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
            <div>
              <h2 className="text-sm font-semibold text-amber-200">Итоговый отчёт ещё не сформирован</h2>
              <p className="mt-1 text-xs leading-5 text-amber-100/75">
                Stage 3 пока не запускался. Ниже доступны только реальные материалы Stage 1–2:
                фотографии, метрики и файлы текущего прогона.
              </p>
            </div>
          </div>
        </section>
      )}

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {(
          [
            ["Фото", photos.length],
            ["Точки перелома", technical?.change_point_count],
            ["Источник", runSummary.data?.source_mode],
            [
              "Stage 3",
              reportMissing ? "не выполнялся" : report.data?.report_schema_version ?? "есть",
            ],
          ] as const
        ).map(([key, value]) => (
          <div key={key} className="rounded-lg border border-line-default bg-surface-base p-4">
            <div className="text-xs text-ink-muted">{key}</div>
            <div className="mt-2 font-mono text-lg text-cyan-300">{value ?? "н/д"}</div>
          </div>
        ))}
      </section>

      <section className="rounded-lg border border-line-default bg-surface-base p-5">
        <details>
          <summary className="cursor-pointer list-none">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-mono text-xs text-cyan-300">ТЕХНИЧЕСКИЕ ФАЙЛЫ ЗАПУСКА</h2>
              <span className="text-2xs font-mono text-ink-muted">
                {presentArtifacts.length} из {artifacts.length} доступны · показать список
              </span>
            </div>
            <p className="mt-2 text-xs text-ink-secondary">
              Служебные файлы Stage 2 доступны для проверки, но не перегружают основной отчёт.
            </p>
          </summary>
          <div className="mt-3 grid gap-2 md:grid-cols-2 lg:grid-cols-3">
          {artifacts.map((item) => (
            <button
              type="button"
              key={item.name}
              onClick={() => setSelectedArtifact(item.present ? (item.name === selectedArtifact ? null : item.name) : null)}
              disabled={!item.present}
              aria-pressed={item.name === selectedArtifact}
              className={`rounded border p-3 ${
                item.present
                  ? item.name === selectedArtifact
                    ? "border-cyan-600"
                    : "border-line-default"
                  : "border-line-default opacity-50"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-xs text-ink-primary">{item.name}</span>
                <span className="shrink-0 text-2xs uppercase text-ink-muted">{item.format ?? "json"}</span>
              </div>
              <div className="mt-1 text-2xs text-ink-secondary">{item.purpose ?? "без описания"}</div>
              <div className="mt-2 text-2xs font-mono text-ink-muted">
                {item.present ? `${item.size_bytes ?? 0} байт` : "нет в выводе"}
              </div>
            </button>
          ))}
          </div>
        </details>
        {selectedArtifact && (
          <div className="mt-4 rounded border border-cyan-600 bg-surface-canvas p-3">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-mono text-xs text-cyan-300">АРТЕФАКТ · {selectedArtifact}</h3>
              {artifactQuery.data?.truncated && (
                <span className="text-2xs text-amber-300">показан только срез</span>
              )}
            </div>
            {artifactQuery.isLoading && <p className="mt-3 text-xs text-ink-muted">Загрузка артефакта…</p>}
            {artifactQuery.error ? (
              <p className="mt-3 text-xs text-amber-300">Артефакт недоступен: {String(artifactQuery.error)}</p>
            ) : null}
            {artifactQuery.data && (
              <pre className="mt-3 max-h-[420px] overflow-auto rounded bg-surface-base p-3 text-2xs text-ink-secondary">
                {preview(artifactQuery.data.payload)}
              </pre>
            )}
          </div>
        )}
      </section>

      {report.isLoading && <LoadingState text="Загрузка отчёта Stage 3…" />}

      {report.data && (
        <>
          <section className="rounded-lg border border-line-default bg-surface-base p-5">
            <h2 className="font-mono text-xs text-cyan-300">СЕКЦИИ ОТЧЁТА</h2>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {sections.map((item) => {
                const selected = section === item.name;
                return (
                  <button
                    key={item.name}
                    type="button"
                    disabled={!item.present}
                    onClick={() => {
                      setSection(selected ? null : item.name);
                      setOffset(0);
                    }}
                    aria-pressed={selected}
                    className={`rounded border px-3 py-2 text-left text-xs ${
                      selected ? "border-cyan-600 text-cyan-300" : "border-line-default text-ink-secondary"
                    } disabled:opacity-40`}
                  >
                    <div className="font-mono">{item.title || item.name}</div>
                    <div className="mt-1 text-2xs text-ink-muted">
                      {item.present ? `записей: ${item.size ?? "—"}` : "нет в выводе"}
                      {item.paged ? " · страницами" : ""}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {narrative.length > 0 && (
            <section className="rounded-lg border border-line-default bg-surface-base p-5">
              <h2 className="font-mono text-xs text-cyan-300">РАССЛЕДОВАТЕЛЬСКАЯ СВОДКА</h2>
              <ul className="mt-3 space-y-2 text-sm text-ink-secondary">
                {narrative.slice(0, 20).map((item, index) => (
                  <li key={index} className="border-l-2 border-line-default pl-3">
                    {preview(item)}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {section && (
            <section className="rounded-lg border border-cyan-600 bg-surface-base p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-mono text-xs text-cyan-300">
                  {sectionQuery.data?.title || section}
                </h2>
                <div className="flex items-center gap-2 text-2xs font-mono text-ink-muted">
                  <span>
                    {sectionQuery.data?.returned ?? 0} из {sectionQuery.data?.total ?? "—"}
                  </span>
                  <button
                    type="button"
                    onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
                    disabled={offset === 0}
                    className="rounded border border-line-default px-2 py-1 disabled:opacity-40"
                  >
                    назад
                  </button>
                  <button
                    type="button"
                    onClick={() => setOffset((value) => value + PAGE_SIZE)}
                    disabled={!sectionQuery.data?.paged}
                    className="rounded border border-line-default px-2 py-1 disabled:opacity-40"
                  >
                    далее
                  </button>
                </div>
              </div>

              {sectionQuery.isLoading && <p className="mt-3 text-xs text-ink-muted">Загрузка секции…</p>}
              {sectionQuery.error ? (
                <p className="mt-3 text-xs text-amber-300">
                  Секция недоступна:{" "}
                  {String(
                    (sectionQuery.error as { message?: string }).message ?? sectionQuery.error,
                  )}
                </p>
              ) : null}
              {sectionQuery.data && (
                <pre className="mt-3 max-h-[420px] overflow-auto rounded bg-surface-canvas p-3 text-2xs text-ink-secondary">
                  {preview(sectionQuery.data.payload)}
                </pre>
              )}
            </section>
          )}

          <section className="rounded-lg border border-line-default bg-surface-base p-5 text-xs text-ink-secondary">
            <h2 className="font-mono text-xs text-cyan-300">СЕМАНТИКА И ОГРАНИЧЕНИЯ</h2>
            <div className="mt-3 space-y-2">
              {Object.entries(report.data.status_semantics ?? {}).map(([key, value]) => (
                <p key={key}>
                  <span className="font-mono text-cyan-300">{key}</span>: {value}
                </p>
              ))}
              {report.data.withheld_note && (
                <p className="text-amber-300">
                  <AlertTriangle className="mr-1 inline h-4 w-4" />
                  {report.data.withheld_note}
                </p>
              )}
            </div>
          </section>
        </>
      )}

      <section className="rounded-lg border border-line-default bg-surface-base p-5">
        <h2 className="font-mono text-xs text-cyan-300">ФАКТЫ ЗАПУСКА</h2>
        <div className="mt-3 space-y-2 text-sm text-ink-secondary">
          <p>
            Диапазон наблюдений: {photos[0]?.date ?? "н/д"} — {photos.at(-1)?.date ?? "н/д"}.
          </p>
          <p>Доступны: идентификатор, дата, ракурс, качество, флаги и связи Stage 2.</p>
        </div>
      </section>
    </div>
  );
};
