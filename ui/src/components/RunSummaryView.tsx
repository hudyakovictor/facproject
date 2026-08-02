import { useEffect, useMemo, useState } from "react";
import {
  fetchRunArtifact, fetchRunSummary, type ArtifactPayload, type RunSummary,
} from "../api";
import { CATEGORY_ORDER, flattenKeys, groupTitle } from "../keys";
import { KeyGroup } from "./KeyTable";
import { Spinner } from "./Loading";
import Icon from "./Icon";
import { getLanguage, t } from "../i18n";

/** Сводка прогона — категория I карты размещения ключей.
 *
 * `analysis_manifest.json` (40 ключей) и `technical_summary.json` содержат
 * готовый технический отчёт: счётчики статусов, число пропущенных пар с
 * причинами, ограничения прогона, целостность артефактов. Всё это
 * вычислялось и сохранялось, но не имело ни одного потребителя, поэтому
 * ответить на вопрос «что НЕ измерено и почему» по интерфейсу было нельзя.
 *
 * Отдельный раздел, а не блок в STATS: STATS описывает выборку фотографий,
 * здесь — свойства самого вычислительного прогона.
 */
export default function RunSummaryView() {
  const [data, setData] = useState<RunSummary | null>(null);
  const [state, setState] = useState<"loading" | "idle" | "unavailable" | "error">("loading");
  const [message, setMessage] = useState("");
  const [artifact, setArtifact] = useState<ArtifactPayload | null>(null);
  const [artifactError, setArtifactError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchRunSummary()
      .then(payload => { if (!cancelled) { setData(payload); setState("idle"); } })
      .catch((err: unknown) => {
        if (cancelled) return;
        const text = err instanceof Error ? err.message : String(err);
        setState(/409|404/.test(text) ? "unavailable" : "error");
        setMessage(text);
      });
    return () => { cancelled = true; };
  }, []);

  const openArtifact = (name: string) => {
    setArtifact(null);
    setArtifactError("");
    fetchRunArtifact(name)
      .then(setArtifact)
      .catch((err: unknown) => setArtifactError(err instanceof Error ? err.message : String(err)));
  };

  const grouped = useMemo(() => {
    if (!data) return [];
    return CATEGORY_ORDER
      .filter(id => data.categories[id])
      .map(id => ({ id, title: titleOf(data, id), groups: data.categories[id] }));
  }, [data]);

  return (
    <section className="h-full overflow-auto bg-bg p-5 scanlines" data-scroll>
      <header className="mb-5">
        <h1 className="font-display text-xl tracking-forensic">{t.runSummaryTitle}</h1>
        <p className="font-mono text-[10px] text-text-muted mt-1">{t.runSummarySub}</p>
      </header>

      {state === "loading" && <Spinner label={t.keysLoading} />}

      {state === "unavailable" && (
        <div role="status" className="bg-warning/15 border border-warning p-3 font-mono text-[10px] text-warning flex items-start gap-2">
          <Icon name="alert-triangle" size={14} color="#e8af34" className="mt-0.5 flex-shrink-0" />
          <div>
            <div>{t.runSummaryUnavailable}</div>
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
          {/* Ограничения прогона — выше всего остального: это ответ на
              вопрос «чему нельзя верить», и он не должен быть внизу. */}
          <Limitations data={data} />

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <h2 className="font-display text-xs tracking-forensic">{t.runSummaryManifest}</h2>
              {grouped.map(section => (
                <div key={section.id} className="space-y-1">
                  <div className="font-mono text-[9px] tracking-forensic text-text-muted">{section.title}</div>
                  {Object.entries(section.groups).map(([group, values]) => (
                    <KeyGroup key={group} id={group} values={flattenKeys(values)} defaultOpen={false} />
                  ))}
                </div>
              ))}
            </div>

            <div className="space-y-2">
              <h2 className="font-display text-xs tracking-forensic">{t.runSummaryArtifacts}</h2>
              <ArtifactList data={data} onOpen={openArtifact} />
              {artifactError && (
                <div role="alert" className="font-mono text-[9px] text-critical break-words">{artifactError}</div>
              )}
              {artifact && <ArtifactPreview artifact={artifact} onClose={() => setArtifact(null)} />}
            </div>
          </div>

          {data.technical_summary && (
            <div className="space-y-1">
              <h2 className="font-display text-xs tracking-forensic">{t.runSummaryTechnical}</h2>
              <KeyGroup id="summary" values={flattenKeys(data.technical_summary)} defaultOpen={false} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

/** Блок «Ограничения прогона»: что НЕ измерено и почему. */
function Limitations({ data }: { data: RunSummary }) {
  const summary = data.categories.I?.summary ?? {};
  const limitations = summary.limitations;
  const skipped = summary.skipped_pair_counts;
  const missingQc = summary.missing_mandatory_qc_record_count;

  const items: { label: string; value: string }[] = [];
  if (Array.isArray(limitations)) {
    for (const entry of limitations) items.push({ label: String(entry), value: "" });
  } else if (limitations && typeof limitations === "object") {
    for (const [key, value] of Object.entries(limitations as Record<string, unknown>)) {
      items.push({ label: key.replace(/_/g, " "), value: String(value) });
    }
  }
  if (skipped && typeof skipped === "object") {
    for (const [reason, count] of Object.entries(skipped as Record<string, unknown>)) {
      items.push({ label: `${t.runSkippedPairs}: ${reason.replace(/_/g, " ")}`, value: String(count) });
    }
  }
  if (typeof missingQc === "number" && missingQc > 0) {
    items.push({ label: t.runMissingQc, value: String(missingQc) });
  }

  if (items.length === 0) {
    return (
      <div className="bg-surface border border-border p-3 font-mono text-[10px] text-text-muted">
        {t.runNoLimitations}
      </div>
    );
  }

  return (
    <div className="bg-warning/10 border border-warning/40 p-3">
      <div className="font-mono text-[9px] tracking-forensic text-warning mb-2 flex items-center gap-1.5">
        <Icon name="alert-triangle" size={11} color="#e8af34" /> {t.runLimitationsTitle}
      </div>
      <div className="space-y-0.5">
        {items.map(item => (
          <div key={item.label} className="flex justify-between gap-3 font-mono text-[10px]">
            <span className="text-text">{item.label}</span>
            {item.value && <span className="text-warning tabular-nums">{item.value}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Перечень артефактов Stage 2 с указанием раздела-потребителя. */
function ArtifactList({ data, onOpen }: { data: RunSummary; onOpen: (name: string) => void }) {
  return (
    <div className="border border-border">
      <table className="w-full border-collapse font-mono text-[10px]">
        <thead>
          <tr className="text-text-faint bg-surface-2">
            <th className="text-left font-normal p-1">{t.runArtifactName}</th>
            <th className="text-left font-normal p-1">{t.runArtifactPurpose}</th>
            <th className="text-right font-normal p-1">{t.runArtifactState}</th>
          </tr>
        </thead>
        <tbody>
          {data.artifacts.map(entry => (
            <tr key={entry.name} className="border-t border-border/60">
              <td className="p-1">
                {entry.present ? (
                  <button onClick={() => onOpen(entry.name)}
                    className="text-info hover:underline text-left">{entry.name}</button>
                ) : (
                  <span className="text-text-faint">{entry.name}</span>
                )}
              </td>
              <td className="p-1 text-text-muted">
                <span className="text-text-faint">[{entry.category}]</span> {entry.purpose}
              </td>
              <td className="p-1 text-right">
                {/* Отсутствующий артефакт перечисляется явно: иначе «не
                    создан прогоном» неотличимо от «раздел не реализован». */}
                {entry.present
                  ? <span className="text-nominal">{formatBytes(entry.size_bytes)}</span>
                  : <span className="text-text-faint">{t.runArtifactAbsent}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ArtifactPreview({ artifact, onClose }: { artifact: ArtifactPayload; onClose: () => void }) {
  return (
    <div className="border border-info/50 bg-surface">
      <div className="flex items-center justify-between px-2 py-1 border-b border-border">
        <div className="font-mono text-[9px] tracking-forensic text-info">{artifact.name}</div>
        <button onClick={onClose} aria-label={t.closeLabel}
          className="text-text-muted hover:text-text"><Icon name="x" size={11} /></button>
      </div>
      {artifact.truncated ? (
        <div className="p-2 font-mono text-[9px] text-warning">
          {t.runArtifactTooLarge(formatBytes(artifact.size_bytes))}
        </div>
      ) : (
        <pre className="p-2 font-mono text-[9px] text-text-muted overflow-auto max-h-96 whitespace-pre-wrap break-all">
          {JSON.stringify(artifact.payload, null, 1)}
        </pre>
      )}
    </div>
  );
}

function formatBytes(size: number | null): string {
  if (size === null) return "—";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function titleOf(data: RunSummary, id: string): string {
  const entry = data.category_titles[id];
  if (!entry) return groupTitle(id);
  return getLanguage() === "en" ? entry.en : entry.ru;
}
