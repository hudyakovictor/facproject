import { useEffect, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import { fetchRunArtifact, fetchRunSummary, type ArtifactEntry } from "../api";
import { KeyGroup } from "./KeyTable";
import { flattenKeys } from "../keys";

const LABELS: Record<string, string> = {
  irreversible_return: "chronoIrreversible",
  baseline_return: "chronoBaselineReturn",
  chronology_rate: "chronoRate",
  biological_rate: "chronoBiological",
  cumulative_drift: "chronoDrift",
};

/** Сводки хронологических детекторов Stage 2.
 *
 * Stage 2 давно считает возвраты к базовой линии, необратимые возвраты A→B→A
 * и биологически неправдоподобные скорости — ровно то, что просило ТЗ, — но
 * ничего из этого не доходило до интерфейса. Панель показывает сводки как
 * есть, ничего не пересчитывая и не усиливая формулировки.
 */
export default function ChronologyAnomalies({ summaries }: {
  summaries: Record<string, Record<string, unknown>>;
}) {
  const entries = Object.entries(summaries).filter(([, v]) => v && Object.keys(v).length > 0);
  if (!entries.length) return null;

  return (
    <section className="bg-surface border border-warning/40 p-3">
      <div className="font-mono text-[9px] tracking-forensic text-warning mb-2 flex items-center gap-1.5">
        <Icon name="alert-triangle" size={11} color="#e8af34" /> {t.chronoAnomaliesTitle}
      </div>
      <div className="space-y-2">
        {entries.map(([key, payload]) => {
          const count = payload.event_count ?? payload.flagged_pairs;
          const years = Array.isArray(payload.years) ? payload.years : null;
          const labelKey = LABELS[key];
          const label = labelKey ? (t[labelKey as keyof typeof t] as string) : key;
          return (
            <div key={key} className="font-mono text-[10px] border-l-2 border-warning/50 pl-2">
              <div className="text-text">{label}</div>
              <div className="text-text-muted">
                {typeof count === "number" && <>{count} {t.chronoEvents}</>}
                {years?.length ? <> · {t.chronoYears}: {years.join(", ")}</> : null}
              </div>
              {typeof payload.note === "string" && (
                <div className="text-text-faint text-[9px] mt-0.5">{payload.note}</div>
              )}
            </div>
          );
        })}
      </div>
      {/* Категория F карты размещения ключей: точки перелома,
          alpha-хронология, модель темпа и реестр лидов сохранялись
          Stage 2 отдельными файлами и не читались ничем. */}
      <ChronologyArtifacts />

      <div className="font-mono text-[9px] text-text-faint mt-2 pt-2 border-t border-border">
        {t.chronoAnomaliesHint}
      </div>
    </section>
  );
}

/** Артефакты хронологии Stage 2, доступные для раскрытия по требованию.
 *
 * Загружаются лениво: список — сразу, содержимое — только по клику.
 * `change_points.json` и `lead_registry.json` на большом прогоне
 * значительны по объёму, и тянуть их ради свёрнутого блока не нужно. */
function ChronologyArtifacts() {
  const [entries, setEntries] = useState<ArtifactEntry[]>([]);
  const [opened, setOpened] = useState<Record<string, unknown>>({});

  useEffect(() => {
    let cancelled = false;
    fetchRunSummary()
      .then(payload => {
        if (cancelled) return;
        setEntries(payload.artifacts.filter(a => a.category === "F" && a.present));
      })
      .catch(() => undefined);  // раздел необязателен: нет Stage 2 — нет блока
    return () => { cancelled = true; };
  }, []);

  if (entries.length === 0) return null;

  const toggle = (name: string) => {
    if (opened[name] !== undefined) {
      setOpened(prev => { const next = { ...prev }; delete next[name]; return next; });
      return;
    }
    fetchRunArtifact(name)
      .then(payload => setOpened(prev => ({ ...prev, [name]: payload.payload })))
      .catch(() => undefined);
  };

  return (
    <div className="mt-2 pt-2 border-t border-border/60 space-y-1">
      {entries.map(entry => (
        <div key={entry.name}>
          <button onClick={() => toggle(entry.name)}
            aria-expanded={opened[entry.name] !== undefined}
            className="w-full flex items-center gap-1.5 font-mono text-[9px] text-text-muted hover:text-text text-left">
            <Icon name={opened[entry.name] !== undefined ? "chevron-down" : "chevron-right"} size={9} />
            <span className="truncate">{entry.purpose}</span>
          </button>
          {opened[entry.name] !== undefined && (
            <div className="mt-1">
              <KeyGroup id={entry.name} values={flattenKeys(opened[entry.name])} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
