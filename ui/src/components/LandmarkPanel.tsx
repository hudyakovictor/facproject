import { useMemo, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import {
  DEFAULT_SHIFT_THRESHOLDS, SHIFT_COLOR, SHIFT_LABEL_KEY, morphPosition,
  summarizeByZone, summarizeShifts, toLandmarkRows,
  type LandmarkRow, type ShiftClass, type ShiftThresholds,
} from "../landmarks";
import type { CompareResult } from "../api";

interface Props {
  result: CompareResult;
  /** Пороги из настроек; при отсутствии — значения по умолчанию. */
  thresholds?: ShiftThresholds;
  /** Сохранить изменённые пороги (например в настройки backend). */
  onThresholdsChange?: (next: ShiftThresholds) => void;
}

const CLASS_ORDER: ShiftClass[] = ["anomalous", "suspect", "within", "no_data"];

/** 🔬 Панель анализа ключевых точек.
 *
 * Отвечает на вопрос «в каких именно точках лица расходятся два кадра».
 * Раньше 134 точки существовали только как облако в тепловой карте — увидеть
 * конкретную точку, её смещение и направление было невозможно.
 *
 * Ключевые решения:
 *  * подписи ТОЛЬКО геометрические (`LM-042`, координатная зона). Анатомических
 *    имён точек в проекте нет, а `app6/stage2/core.py` прямо отказывается от
 *    «unverified anatomical labels» — домысливать их в forensic-инструменте
 *    недопустимо;
 *  * точка, невидимая на одном из кадров, показывается как «нет данных», а не
 *    как совпавшая;
 *  * пороги настраиваются пользователем и честно помечаются как
 *    неоткалиброванные, пока это не подтверждено калибровочным набором.
 */
export default function LandmarkPanel({ result, thresholds, onThresholdsChange }: Props) {
  const active = thresholds ?? DEFAULT_SHIFT_THRESHOLDS;
  const [morphT, setMorphT] = useState(0);
  const [sortBy, setSortBy] = useState<"shift" | "index" | "zone">("shift");
  const [filterClass, setFilterClass] = useState<ShiftClass | "all">("all");
  const [view, setView] = useState<"table" | "scatter">("scatter");
  const [local, setLocal] = useState<ShiftThresholds>(active);

  // Локальные пороги живут в панели; наружу отдаются по отпусканию слайдера,
  // чтобы не слать запрос на каждое движение мыши.
  const effective = onThresholdsChange ? local : active;

  const rows = useMemo(
    () => toLandmarkRows(result.heatmap_points, effective),
    [result.heatmap_points, effective]);

  const summary = useMemo(() => summarizeShifts(rows), [rows]);
  const zones = useMemo(() => summarizeByZone(rows), [rows]);

  const visibleRows = useMemo(() => {
    const filtered = filterClass === "all" ? rows : rows.filter(r => r.shiftClass === filterClass);
    const sorted = [...filtered];
    if (sortBy === "shift") {
      sorted.sort((a, b) => (b.residual ?? -1) - (a.residual ?? -1));
    } else if (sortBy === "index") {
      sorted.sort((a, b) => a.index - b.index);
    } else {
      sorted.sort((a, b) => (a.zone ?? "").localeCompare(b.zone ?? "") || a.index - b.index);
    }
    return sorted;
  }, [rows, filterClass, sortBy]);

  if (!rows.length) {
    return <div className="font-mono text-[10px] text-text-muted p-3">{t.lmNoData}</div>;
  }

  const commitThresholds = (next: ShiftThresholds) => {
    setLocal(next);
    onThresholdsChange?.(next);
  };

  return (
    <section className="space-y-3">
      <header>
        <div className="font-display text-sm tracking-forensic">{t.lmPanelTitle}</div>
        <p className="font-mono text-[9px] text-text-faint mt-0.5 leading-snug">{t.lmPanelSub}</p>
      </header>

      {/* Сводка по классам */}
      <div className="grid grid-cols-4 gap-2">
        {CLASS_ORDER.map(cls => (
          <button key={cls}
            onClick={() => setFilterClass(filterClass === cls ? "all" : cls)}
            aria-pressed={filterClass === cls}
            className={`bg-surface-2 border p-2 text-left ${filterClass === cls ? "border-info" : "border-border"}`}>
            <div className="font-mono text-[8px] text-text-muted truncate">
              {t[SHIFT_LABEL_KEY[cls] as keyof typeof t] as string}
            </div>
            <div className="font-display text-lg" style={{ color: SHIFT_COLOR[cls] }}>
              {summary[cls]}
            </div>
          </button>
        ))}
      </div>

      <div className="font-mono text-[9px] text-text-muted flex flex-wrap gap-x-3">
        <span>{t.lmMeasured}: {summary.total - summary.no_data} {t.lmOfTotal} {summary.total}</span>
        {summary.anomalousShare !== null && (
          <span>{t.lmAnomalousShare}: {(summary.anomalousShare * 100).toFixed(1)}%</span>
        )}
        {summary.medianResidual !== null && (
          <span>{t.lmMedianShift}: {summary.medianResidual.toFixed(4)}</span>
        )}
      </div>

      {/* Пороги */}
      <div className="bg-surface-2 border border-border p-2">
        <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-2">
          {t.lmThresholdsTitle}
        </div>
        <ThresholdSlider
          label={t.lmTolerance} value={effective.tolerance} color={SHIFT_COLOR.within}
          max={Math.max(0.1, effective.suspect)}
          onChange={v => commitThresholds({ ...effective, tolerance: Math.min(v, effective.suspect) })}
        />
        <ThresholdSlider
          label={t.lmSuspect} value={effective.suspect} color={SHIFT_COLOR.suspect}
          max={0.3} min={effective.tolerance}
          onChange={v => commitThresholds({ ...effective, suspect: Math.max(v, effective.tolerance) })}
        />
        <div className="font-mono text-[8px] mt-1.5 flex items-start gap-1"
          style={{ color: effective.calibrated ? "#6daa45" : "#e8af34" }}>
          <Icon name={effective.calibrated ? "check" : "alert-triangle"} size={9}
            color={effective.calibrated ? "#6daa45" : "#e8af34"} className="mt-px flex-shrink-0" />
          {effective.calibrated ? t.lmCalibrated : t.lmNotCalibrated}
        </div>
        <div className="font-mono text-[8px] text-text-faint mt-1 leading-snug">{t.lmThresholdsHint}</div>
      </div>

      {/* Морфинг A→B */}
      <div className="bg-surface-2 border border-border p-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] tracking-forensic text-info w-4">A</span>
          <input type="range" min={0} max={1} step={0.01} value={morphT}
            onChange={e => setMorphT(+e.target.value)}
            aria-label={t.lmMorphLabel} className="flex-1" />
          <span className="font-mono text-[9px] tracking-forensic text-warning w-4 text-right">B</span>
          <span className="font-mono text-[10px] text-text-muted w-10 text-right">
            {(morphT * 100).toFixed(0)}%
          </span>
        </div>
        <div className="font-mono text-[8px] text-text-faint mt-1">{t.lmMorphHint}</div>
      </div>

      {/* Переключатель вида */}
      <div className="flex items-center gap-2">
        <div className="flex gap-px">
          {(["scatter", "table"] as const).map(mode => (
            <button key={mode} onClick={() => setView(mode)} aria-pressed={view === mode}
              className={`px-2 py-1 font-mono text-[9px] tracking-forensic border ${view === mode ? "bg-info/25 border-info text-text" : "border-border text-text-muted hover:text-text"}`}>
              {mode === "scatter" ? t.lmViewScatter : t.lmViewTable}
            </button>
          ))}
        </div>
        <select value={sortBy} onChange={e => setSortBy(e.target.value as typeof sortBy)}
          aria-label={t.lmSortBy}
          className="ml-auto bg-surface-2 border border-border px-2 py-1 font-mono text-[9px] text-text">
          <option value="shift">{t.lmSortByShift}</option>
          <option value="index">{t.lmSortByIndex}</option>
          <option value="zone">{t.lmSortByZone}</option>
        </select>
      </div>

      {view === "scatter"
        ? <LandmarkScatter rows={rows} morphT={morphT} highlight={filterClass} />
        : <LandmarkTable rows={visibleRows} />}

      {/* Сводка по координатным зонам */}
      <div className="bg-surface-2 border border-border p-2">
        <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-1">
          {t.lmZoneSummary}
        </div>
        <div className="space-y-0.5 font-mono text-[9px]">
          {zones.map(z => (
            <div key={z.zone} className="flex justify-between gap-2">
              <span className="text-text">{z.zone}</span>
              <span className="text-text-muted">
                {z.anomalous > 0 && (
                  <span style={{ color: SHIFT_COLOR.anomalous }}>{z.anomalous} {t.lmZoneAnomalous} · </span>
                )}
                {z.medianResidual !== null ? `${t.lmMedianShift} ${z.medianResidual.toFixed(4)}` : "—"}
                <span className="text-text-faint"> · n={z.total}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ThresholdSlider({ label, value, onChange, color, max = 0.3, min = 0 }: {
  label: string; value: number; onChange: (v: number) => void;
  color: string; max?: number; min?: number;
}) {
  return (
    <div className="flex items-center gap-2 mb-1">
      <span className="w-1.5 h-3 flex-shrink-0" style={{ background: color }} />
      <span className="font-mono text-[9px] text-text-muted flex-1 truncate">{label}</span>
      <input type="range" min={min} max={max} step={0.001} value={value}
        onChange={e => onChange(+e.target.value)} aria-label={label}
        className="w-24" />
      <span className="font-mono text-[9px] w-12 text-right tabular-nums">{value.toFixed(3)}</span>
    </div>
  );
}

/** Фронтальная проекция точек с морфингом A→B и окраской по классу смещения. */
function LandmarkScatter({ rows, morphT, highlight }: {
  rows: LandmarkRow[]; morphT: number; highlight: ShiftClass | "all";
}) {
  const positioned = rows
    .map(row => ({ row, pos: morphPosition(row, morphT) }))
    .filter((entry): entry is { row: LandmarkRow; pos: [number, number, number] } => entry.pos !== null);

  if (!positioned.length) {
    return <div className="font-mono text-[10px] text-text-muted p-3">{t.lmNoData}</div>;
  }

  const xs = positioned.map(p => p.pos[0]);
  const ys = positioned.map(p => p.pos[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const spanX = maxX - minX || 1, spanY = maxY - minY || 1;
  const W = 420, H = 460, pad = 24;

  const px = (x: number) => pad + ((x - minX) / spanX) * (W - 2 * pad);
  // Ось Y инвертируется: в координатах модели Y растёт вверх, в SVG — вниз.
  const py = (y: number) => H - pad - ((y - minY) / spanY) * (H - 2 * pad);

  const maxResidual = Math.max(1e-6, ...rows.map(r => r.residual ?? 0));

  return (
    <div className="bg-surface border border-border">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 460 }}>
        {positioned.map(({ row, pos }) => {
          const dim = highlight !== "all" && row.shiftClass !== highlight;
          const color = SHIFT_COLOR[row.shiftClass];
          const magnitude = (row.residual ?? 0) / maxResidual;
          const r = row.shiftClass === "no_data" ? 1.6 : 1.8 + magnitude * 3.2;
          return (
            <g key={row.index} opacity={dim ? 0.15 : 1}>
              {/* След смещения: от позиции A к текущей позиции морфинга. */}
              {row.a && row.b && morphT > 0 && row.shiftClass !== "no_data" && (
                <line x1={px(row.a[0])} y1={py(row.a[1])} x2={px(pos[0])} y2={py(pos[1])}
                  stroke={color} strokeOpacity="0.35" strokeWidth="0.6" />
              )}
              {row.shiftClass === "no_data" ? (
                <circle cx={px(pos[0])} cy={py(pos[1])} r={r}
                  fill="none" stroke={color} strokeWidth="0.8" strokeDasharray="1.5 1" />
              ) : (
                <circle cx={px(pos[0])} cy={py(pos[1])} r={r} fill={color} fillOpacity="0.85"
                  stroke="#0d0d0f" strokeWidth="0.4" />
              )}
              <title>
                {`LM-${String(row.index).padStart(3, "0")} · ${row.zone ?? "—"}\n`}
                {row.residual !== null
                  ? `смещение ${row.residual.toFixed(4)}`
                  : (t.shiftNoData as string)}
              </title>
            </g>
          );
        })}
      </svg>
      <div className="px-2 py-1 border-t border-border font-mono text-[8px] text-text-faint">
        {t.lmProjectionHint}
      </div>
    </div>
  );
}

function LandmarkTable({ rows }: { rows: LandmarkRow[] }) {
  return (
    <div className="bg-surface border border-border max-h-[420px] overflow-auto" data-scroll>
      <table className="w-full border-collapse font-mono text-[9px]">
        <thead className="sticky top-0 bg-surface">
          <tr className="text-text-faint">
            <th className="text-left font-normal p-1">{t.lmColPoint}</th>
            <th className="text-left font-normal p-1">{t.lmColZone}</th>
            <th className="text-right font-normal p-1">{t.lmColShift}</th>
            <th className="text-right font-normal p-1">{t.lmColDelta}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.index} className="border-t border-border/60">
              <td className="p-1">
                <span className="inline-block w-1.5 h-1.5 mr-1.5 align-middle"
                  style={{ background: SHIFT_COLOR[row.shiftClass] }} />
                LM-{String(row.index).padStart(3, "0")}
              </td>
              <td className="p-1 text-text-muted">{row.zone ?? "—"}</td>
              <td className="p-1 text-right tabular-nums"
                style={{ color: SHIFT_COLOR[row.shiftClass] }}>
                {row.residual !== null ? row.residual.toFixed(4) : "—"}
              </td>
              <td className="p-1 text-right text-text-muted tabular-nums">
                {row.delta
                  ? row.delta.map(v => `${v >= 0 ? "+" : ""}${v.toFixed(3)}`).join(" ")
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
