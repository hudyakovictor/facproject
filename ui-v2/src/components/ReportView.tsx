import { useEffect, useState } from "react";
import {
  fetchReportSection, fetchReportSummary, type ReportSection, type ReportSummary,
} from "../api";
import { KeyGroup } from "./KeyTable";
import { flattenKeys } from "../keys";
import { Spinner } from "./Loading";
import Icon from "./Icon";
import { t } from "../i18n";

/** Публичный отчёт Stage 3 внутри рабочей станции.
 *
 * Stage 3 был единственным этапом пайплайна без эндпоинта: он строит
 * самостоятельный HTML со встроенным JSON, и чтобы увидеть итог
 * расследования, нужно было открыть файл с диска мимо интерфейса.
 *
 * Здесь показывается не копия того HTML, а его данные в терминах рабочей
 * станции: нарратив, счётчики, статус валидации и секции по требованию.
 * Крупные секции (`pairs`, `motion_maps`) грузятся страницами — обзор не
 * должен тянуть 40 карт по 134 точки.
 */
export default function ReportView() {
  const [data, setData] = useState<ReportSummary | null>(null);
  const [state, setState] = useState<"loading" | "idle" | "unavailable" | "error">("loading");
  const [message, setMessage] = useState("");
  const [section, setSection] = useState<ReportSection | null>(null);
  const [sectionError, setSectionError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchReportSummary()
      .then(payload => { if (!cancelled) { setData(payload); setState("idle"); } })
      .catch((err: unknown) => {
        if (cancelled) return;
        const text = err instanceof Error ? err.message : String(err);
        setState(/409|404/.test(text) ? "unavailable" : "error");
        setMessage(text);
      });
    return () => { cancelled = true; };
  }, []);

  const openSection = (name: string, offset = 0) => {
    setSectionError("");
    fetchReportSection(name, offset)
      .then(setSection)
      .catch((err: unknown) => setSectionError(err instanceof Error ? err.message : String(err)));
  };

  return (
    <section className="h-full overflow-auto bg-bg p-5 scanlines" data-scroll>
      <header className="mb-5">
        <h1 className="font-display text-xl tracking-forensic">{t.reportTitle}</h1>
        <p className="font-mono text-[10px] text-text-muted mt-1">{t.reportSub}</p>
      </header>

      {state === "loading" && <Spinner label={t.keysLoading} />}

      {state === "unavailable" && (
        <div role="status" className="bg-warning/15 border border-warning p-3 font-mono text-[10px] text-warning flex items-start gap-2">
          <Icon name="alert-triangle" size={14} color="#e8af34" className="mt-0.5 flex-shrink-0" />
          <div>
            <div>{t.reportUnavailable}</div>
            <div className="text-text-faint mt-1 break-words">{message}</div>
          </div>
        </div>
      )}

      {state === "error" && (
        <div role="alert" className="bg-critical/15 border border-critical p-3 font-mono text-[10px] text-critical break-words">
          {t.keysLoadFailed}: {message}
        </div>
      )}

      {data && (
        <div className="space-y-5">
          <ValidationBanner data={data} />
          <SemanticsNotice data={data} />

          {data.narrative.length > 0 && (
            <div className="space-y-1.5">
              <h2 className="font-display text-xs tracking-forensic">{t.reportNarrative}</h2>
              {data.narrative.map((line, index) => (
                <p key={index} className="font-mono text-[10px] text-text leading-relaxed border-l-2 border-info/40 pl-2">
                  {line}
                </p>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <h2 className="font-display text-xs tracking-forensic">{t.reportCounters}</h2>
              <KeyGroup id="summary" values={flattenKeys(data.summary)} />
              {Object.keys(data.methodology).length > 0 && (
                <KeyGroup id="other" values={flattenKeys(data.methodology)} defaultOpen={false} />
              )}
            </div>

            <div className="space-y-2">
              <h2 className="font-display text-xs tracking-forensic">{t.reportSections}</h2>
              <SectionList data={data} onOpen={openSection} />
              {sectionError && (
                <div role="alert" className="font-mono text-[9px] text-critical break-words">{sectionError}</div>
              )}
            </div>
          </div>

          {section && (
            <SectionPreview
              section={section}
              onClose={() => setSection(null)}
              onPage={offset => openSection(section.name, offset)}
            />
          )}

          <footer className="font-mono text-[8px] text-text-faint border-t border-border pt-2">
            {t.reportFooter(data.report_schema_version ?? "—", data.stage2_schema_version ?? "—", data.created_at_utc ?? "—")}
          </footer>
        </div>
      )}
    </section>
  );
}

/** Статус валидации отчёта: без него нельзя понять, полон ли он. */
function ValidationBanner({ data }: { data: ReportSummary }) {
  const validation = data.validation;
  if (!validation) {
    return (
      <div className="bg-surface border border-border p-2 font-mono text-[9px] text-text-muted">
        {t.reportNoValidation}
      </div>
    );
  }
  const status = String(validation.status ?? "");
  const errors = Array.isArray(validation.errors) ? validation.errors : [];
  const ok = status === "complete" && errors.length === 0;
  return (
    <div className={`border p-2 font-mono text-[9px] flex items-start gap-1.5 ${ok ? "bg-nominal/10 border-nominal/40 text-nominal" : "bg-warning/10 border-warning/40 text-warning"}`}>
      <Icon name={ok ? "check" : "alert-triangle"} size={11} color={ok ? "#6daa45" : "#e8af34"} className="mt-0.5 flex-shrink-0" />
      <div>
        <div>{t.reportValidation}: {status || "—"}</div>
        {errors.length > 0 && (
          <div className="text-text-faint mt-0.5">{errors.map(String).join(" · ")}</div>
        )}
      </div>
    </div>
  );
}

/** Пояснение о разной семантике `status` между Stage 2 и Stage 3.
 *
 * Без него читатель, сверяя отчёт с таблицей метрик пары, увидит разные
 * значения одного и того же поля и решит, что данные расходятся. */
function SemanticsNotice({ data }: { data: ReportSummary }) {
  return (
    <div className="bg-info/10 border-l-2 border-info px-2 py-1.5 space-y-0.5">
      <div className="font-mono text-[9px] text-info">{t.reportSemanticsTitle}</div>
      <div className="font-mono text-[9px] text-text-muted">{data.status_semantics.note}</div>
      <div className="font-mono text-[9px] text-text-faint">{data.withheld_note}</div>
    </div>
  );
}

function SectionList({ data, onOpen }: { data: ReportSummary; onOpen: (name: string) => void }) {
  return (
    <div className="border border-border">
      <table className="w-full border-collapse font-mono text-[10px]">
        <tbody>
          {data.sections.map(entry => (
            <tr key={entry.name} className="border-t border-border/60">
              <td className="p-1">
                {entry.present ? (
                  <button onClick={() => onOpen(entry.name)}
                    className="text-info hover:underline text-left">{entry.title}</button>
                ) : (
                  <span className="text-text-faint">{entry.title}</span>
                )}
              </td>
              <td className="p-1 text-right text-text-muted tabular-nums">
                {/* Отсутствующая секция показывается явно: «не создана
                    прогоном» — это результат, а не пустое место. */}
                {entry.present ? (entry.size ?? "—") : t.reportSectionAbsent}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SectionPreview({ section, onClose, onPage }: {
  section: ReportSection;
  onClose: () => void;
  onPage: (offset: number) => void;
}) {
  const offset = section.offset ?? 0;
  const returned = section.returned ?? 0;
  const total = section.total ?? 0;
  const hasPrev = offset > 0;
  const hasNext = offset + returned < total;

  return (
    <div className="border border-info/50 bg-surface">
      <div className="flex items-center justify-between px-2 py-1 border-b border-border">
        <div className="font-mono text-[9px] tracking-forensic text-info">
          {section.title}
          {section.total !== null && (
            <span className="text-text-faint"> · {offset + 1}–{offset + returned} / {total}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {section.paged && (
            <>
              <button onClick={() => onPage(Math.max(0, offset - 100))} disabled={!hasPrev}
                aria-label={t.reportPrevPage} title={t.reportPrevPage}
                className="w-5 h-5 flex items-center justify-center border border-border text-text-muted hover:text-text disabled:opacity-30">
                <Icon name="chevron-left" size={10} />
              </button>
              <button onClick={() => onPage(offset + 100)} disabled={!hasNext}
                aria-label={t.reportNextPage} title={t.reportNextPage}
                className="w-5 h-5 flex items-center justify-center border border-border text-text-muted hover:text-text disabled:opacity-30">
                <Icon name="chevron-right" size={10} />
              </button>
            </>
          )}
          <button onClick={onClose} aria-label={t.closeLabel}
            className="text-text-muted hover:text-text ml-1"><Icon name="x" size={11} /></button>
        </div>
      </div>
      <pre className="p-2 font-mono text-[9px] text-text-muted overflow-auto max-h-96 whitespace-pre-wrap break-all">
        {JSON.stringify(section.payload, null, 1)}
      </pre>
    </div>
  );
}
