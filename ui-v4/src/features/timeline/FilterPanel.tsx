import { useEffect, useMemo, useState } from "react";
import {
  evaluateSelection,
  fetchSelectionDefaults,
  saveSelection,
  type FilterEvalResult,
  type FilterState,
  type QualityFilterKey,
} from "../../shared/api";

const FILTER_STATE_KEY = "deeputin.timeline.selection_state";
const LABELS: Record<string, string> = {
  visibility: "Visibility",
  confidence: "Confidence",
  faceResolution: "Face resolution",
  blur: "Sharpness (blur↑)",
  exposure: "Exposure / skin cover",
  occlusion: "Occlusion",
  reconstructionResidual: "Reconstruction residual",
  alignmentQuality: "Alignment quality",
  landmarkVisibility: "Landmark visibility",
  textureApplicability: "Texture applicability",
  expressionMagnitude: "Expression magnitude",
  jawOpenRatio: "Jaw-open ratio",
  smileScore: "Smile score",
};

function cloneState(state: FilterState): FilterState {
  return JSON.parse(JSON.stringify(state)) as FilterState;
}

function Histogram({ counts, color }: { counts: number[]; color: string }) {
  const max = Math.max(1, ...counts);
  return <div className="filter-histogram">{counts.map((count, index) => (
    <i key={index} style={{ height: `${Math.max(2, (count / max) * 36)}px`, background: color }} title={String(count)} />
  ))}</div>;
}

export default function FilterPanel({
  open,
  onClose,
  onApplied,
}: {
  open: boolean;
  onClose: () => void;
  onApplied: (result: FilterEvalResult) => void;
}) {
  const [state, setState] = useState<FilterState | null>(null);
  const [result, setResult] = useState<FilterEvalResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [keys, setKeys] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    let dead = false;
    setBusy(true);
    fetchSelectionDefaults()
      .then(async defaults => {
        if (dead) return;
        setKeys(defaults.quality_keys || Object.keys(LABELS));
        let initial = cloneState(defaults.filter_state);
        try {
          const saved = localStorage.getItem(FILTER_STATE_KEY);
          if (saved) initial = { ...initial, ...cloneState(JSON.parse(saved) as FilterState) };
        } catch { /* use backend defaults */ }
        setState(initial);
        const evaluation = await evaluateSelection(initial);
        if (!dead) {
          setResult(evaluation);
          onApplied(evaluation);
        }
      })
      .catch(error => setMessage(error instanceof Error ? error.message : String(error)))
      .finally(() => { if (!dead) setBusy(false); });
    return () => { dead = true; };
  }, [open]);

  const reasonEntries = useMemo(
    () => Object.entries(result?.reason_counts || {}).sort((a, b) => b[1] - a[1]),
    [result],
  );

  if (!open || !state) return null;

  const updateEnabled = (key: string, enabled: boolean) => {
    setState(current => current ? {
      ...current,
      enabled: { ...current.enabled, [key]: enabled },
    } : current);
  };

  const updateRange = (key: string, side: "min" | "max", value: number) => {
    setState(current => {
      if (!current) return current;
      const previous = current.ranges[key] || { min: null, max: null };
      return {
        ...current,
        enabled: { ...current.enabled, [key]: true },
        ranges: {
          ...current.ranges,
          [key]: { ...previous, [side]: Number.isFinite(value) ? value : null },
        },
      };
    });
  };

  const updateBoolean = (key: keyof FilterState["booleans"], value: boolean) => {
    setState(current => current ? {
      ...current,
      booleans: { ...current.booleans, [key]: value },
    } : current);
  };

  const updatePose = (patch: Partial<FilterState["poseOutlier"]>) => {
    setState(current => current ? {
      ...current,
      poseOutlier: { ...current.poseOutlier, ...patch },
    } : current);
  };

  const runEvaluate = async () => {
    if (!state) return;
    localStorage.setItem(FILTER_STATE_KEY, JSON.stringify(state));
    setBusy(true); setMessage("");
    try {
      const evaluation = await evaluateSelection(state);
      setResult(evaluation);
      onApplied(evaluation);
      setMessage(`Выборка: ${evaluation.included_count} включено · ${evaluation.excluded_count} исключено`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const runSave = async () => {
    if (!state) return;
    localStorage.setItem(FILTER_STATE_KEY, JSON.stringify(state));
    setBusy(true); setMessage("");
    try {
      const saved = await saveSelection(state, `selection_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}`);
      setMessage(`selection_manifest сохранён · ${saved.path}`);
      await runEvaluate();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return <aside className="filter-panel">
    <header>
      <div>
        <small>ITERATION 03 · SELECTION</small>
        <b>Фильтры качества и ракурса</b>
        <span>Stage 1 immutable · Stage 2 не запускается</span>
      </div>
      <button onClick={onClose}>×</button>
    </header>
    {message && <div className="filter-message">{message}</div>}
    <div className="filter-summary">
      <div><strong>{result?.included_count ?? "—"}</strong><span>в выборке</span></div>
      <div><strong>{result?.excluded_count ?? "—"}</strong><span>исключено</span></div>
      <div><strong>{result?.total ?? "—"}</strong><span>всего</span></div>
    </div>

    <section>
      <h3>Quality ranges</h3>
      <div className="filter-list">
        {keys.map(key => {
          const hist = result?.histograms?.[key];
          const lo = hist?.min ?? 0;
          const hi = hist?.max ?? 1;
          const range = state.ranges[key] || { min: lo, max: hi };
          const minValue = range.min ?? lo;
          const maxValue = range.max ?? hi;
          const step = Math.max((hi - lo) / 100, 0.0001);
          return <article key={key} className={state.enabled[key] ? "enabled" : ""}>
            <label className="filter-enable">
              <input type="checkbox" checked={Boolean(state.enabled[key])} onChange={event => updateEnabled(key, event.target.checked)} />
              <b>{LABELS[key] || key}</b>
              <em>{hist?.count ?? 0} values</em>
            </label>
            {hist && hist.counts?.length > 0 && <Histogram counts={hist.counts} color={state.enabled[key] ? "#68c3cf" : "#3a4654"} />}
            <div className="filter-range">
              <span>{Number(minValue).toFixed(3)}</span>
              <input type="range" min={lo} max={hi} step={step} value={minValue} disabled={!state.enabled[key] && hist?.count === 0} onChange={event => updateRange(key, "min", Number(event.target.value))} />
              <input type="range" min={lo} max={hi} step={step} value={maxValue} disabled={!state.enabled[key] && hist?.count === 0} onChange={event => updateRange(key, "max", Number(event.target.value))} />
              <span>{Number(maxValue).toFixed(3)}</span>
            </div>
          </article>;
        })}
      </div>
    </section>

    <section>
      <h3>Pose outlier</h3>
      <label className="filter-enable">
        <input type="checkbox" checked={state.poseOutlier.enabled} onChange={event => updatePose({ enabled: event.target.checked })} />
        <b>Отсекать экстремальные позы внутри bin</b>
      </label>
      <label className="filter-slider">
        <span>Master keep % (percentile)</span>
        <input type="range" min={50} max={100} step={1} value={state.poseOutlier.masterPercentile} onChange={event => updatePose({ masterPercentile: Number(event.target.value), enabled: true })} />
        <b>{state.poseOutlier.masterPercentile.toFixed(0)}%</b>
      </label>
      <label className="filter-slider">
        <span>MAD multiplier</span>
        <input type="range" min={1} max={8} step={0.1} value={state.poseOutlier.madMultiplier} onChange={event => updatePose({ madMultiplier: Number(event.target.value), method: "mad", enabled: true })} />
        <b>{state.poseOutlier.madMultiplier.toFixed(1)}</b>
      </label>
      {(["yawLimit", "pitchLimit", "rollLimit"] as const).map(axis => (
        <label className="filter-slider" key={axis}>
          <span>{axis.replace("Limit", "")} limit (°)</span>
          <input
            type="range"
            min={0}
            max={axis === "pitchLimit" ? 30 : 60}
            step={0.5}
            value={state.poseOutlier[axis] ?? 0}
            onChange={event => updatePose({ [axis]: Number(event.target.value), enabled: true })}
          />
          <b>{(state.poseOutlier[axis] ?? 0).toFixed(1)}</b>
        </label>
      ))}
    </section>

    <section>
      <h3>Boolean gates</h3>
      {([
        ["excludeSmileDetected", "Исключить smile_detected"],
        ["excludeJawOpenDetected", "Исключить jaw_open_detected"],
        ["excludeDateConflict", "Исключить date conflict"],
        ["excludeNearDuplicate", "Исключить near duplicates"],
        ["excludeMissingSourceChain", "Исключить missing source chain"],
      ] as const).map(([key, label]) => (
        <label className="filter-enable" key={key}>
          <input type="checkbox" checked={Boolean(state.booleans[key])} onChange={event => updateBoolean(key, event.target.checked)} />
          <b>{label}</b>
        </label>
      ))}
    </section>

    <section>
      <h3>Exclusion reasons</h3>
      <div className="reason-list">
        {reasonEntries.length === 0 && <em>Нет исключений</em>}
        {reasonEntries.map(([reason, count]) => <div key={reason}><code>{reason}</code><b>{count}</b></div>)}
      </div>
    </section>

    <footer>
      <button className="ghost" disabled={busy} onClick={() => void runEvaluate()}>{busy ? "Счёт…" : "Применить"}</button>
      <button className="primary" disabled={busy} onClick={() => void runSave()}>Сохранить selection</button>
    </footer>
  </aside>;
}

export type { FilterEvalResult, FilterState, QualityFilterKey };
