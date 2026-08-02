import { Photo, HYPOTHESIS_COLORS, FUZZY_COLORS } from "../data";
import { useModal } from "../useModal";
import { useThresholds } from "../settings";
import Icon from "./Icon";
import { t } from "../i18n";

interface RangeData {
  t0: number; t1: number; photos: Photo[];
}

interface Props {
  rangeA: RangeData;
  rangeB: RangeData | null;
  onClose: () => void;
  onSetSide: (side: "A" | "B") => void;
  activeSide: "A" | "B";
}

/** P3.12 (DEV_FIX_TZ): корректная медиана. Для чётной длины берётся среднее
 * двух центральных значений, а не нижнее из них — иначе сравнение диапазонов
 * A/B систематически смещалось вниз на выборках чётного размера. */
function median(arr: number[]) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 === 0 ? (s[mid - 1] + s[mid]) / 2 : s[mid];
}

function summary(range: RangeData) {
  const ps = range.photos;
  if (!ps.length) return null;
  return {
    n: ps.length,
    bone: median(ps.map(p => p.boneScore)),
    orbit: median(ps.map(p => p.orbit)),
    chin: median(ps.map(p => p.chin)),
    jaw: median(ps.map(p => p.jaw)),
    cheek: median(ps.map(p => p.cheek)),
    sym: median(ps.map(p => p.symmetry)),
    sil: median(ps.map(p => p.siliconeProb)),
    spec: median(ps.map(p => p.specular)),
    lbp: median(ps.map(p => p.lbpEntropy)),
    fra: median(ps.map(p => p.frangi)),
    wri: median(ps.map(p => p.wrinkle)),
    sub: median(ps.map(p => p.subsurface)),
    p0: median(ps.map(p => p.p0)),
    p1: median(ps.map(p => p.p1)),
    p2: median(ps.map(p => p.p2)),
    fuzzy: mode(ps.map(p => p.fuzzy)),
    dom: mode(ps.map(p => p.dominant)),
  };
}

function mode<T extends string>(arr: T[]): T {
  const counts: Record<string, number> = {};
  for (const a of arr) counts[a] = (counts[a] || 0) + 1;
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0] as T;
}

/** Числовые метрики сводки диапазона. Явный union вместо `Record<string, …>`
 * + `as any` (DEV_FIX_TZ P2.1/1.10): опечатка в ключе метрики теперь ошибка
 * компиляции, а не `undefined` в таблице сравнения. */
type MetricKey = "bone" | "orbit" | "chin" | "jaw" | "cheek" | "sym"
  | "sil" | "spec" | "lbp" | "fra" | "wri" | "sub";

/** Геометрические метрики берут лимит `geometry_zone_delta_limit`,
 * текстурные — `texture_zone_delta_limit`.
 *
 * 🔧 Раньше здесь стоял `POLICY_DELTA` с зашитыми `0.018`/`0.04` — буквально
 * копия дефолтов из `app6/api/settings.DEFAULT_SETTINGS`. Пользователь
 * двигал ползунок в настройках, значение сохранялось на диск, а сравнение
 * продолжало считать по константе: интерфейс заявлял управление, которого
 * не было. */
const TEXTURE_METRICS: ReadonlySet<MetricKey> = new Set<MetricKey>(
  ["sil", "spec", "lbp", "fra", "wri", "sub"]);

export default function ComparisonPanel({ rangeA, rangeB, onClose, onSetSide, activeSide }: Props) {
  const dialogRef = useModal<HTMLDivElement>(onClose);
  const thresholds = useThresholds();
  const a = summary(rangeA);
  const b = rangeB ? summary(rangeB) : null;

  const fmtDate = (ts: number) => new Date(ts).toLocaleDateString("ru-RU");

  const metrics = [
    { k: "bone", label: t.trackBone },
    { k: "orbit", label: t.trackOrbits },
    { k: "chin", label: t.trackChin },
    { k: "jaw", label: t.trackJaw },
    { k: "cheek", label: t.trackCheek },
    { k: "sym", label: t.trackSymmetry },
    { k: "sil", label: t.trackSilicone },
    { k: "spec", label: t.trackSpecular },
    { k: "lbp", label: t.trackLBP },
    { k: "fra", label: t.trackFrangi },
    { k: "wri", label: t.trackWrinkle },
    { k: "sub", label: t.trackSubsurface },
  ] satisfies { k: MetricKey; label: string }[];

  return (
    /* Не `aria-modal`: панель занимает нижнюю треть, фон остаётся рабочим —
       объявлять её модальной означало бы соврать screen reader'у. Region с
       именем + закрытие по Escape (WCAG 2.1.2, 1.3.1). */
    <div ref={dialogRef} data-no-pan role="region" aria-label={t.comparisonMode} tabIndex={-1}
      className="absolute left-0 right-0 bottom-0 z-40 bg-surface border-t-2 border-info shadow-2xl outline-none"
      style={{ height: 280 }}>
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface-2">
        <div className="flex items-center gap-3">
          <Icon name="compare" size={16} color="#5591c7" />
          <div className="font-display tracking-forensic text-sm">{t.comparisonMode}</div>
          <div className="font-mono text-[10px] text-text-muted">{t.comparisonSub}</div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => onSetSide("A")}
            className={`px-2 py-1 font-mono text-[10px] tracking-forensic border ${activeSide === "A" ? "bg-info/20 border-info" : "border-border text-text-muted"}`}>{t.setA}</button>
          <button onClick={() => onSetSide("B")}
            className={`px-2 py-1 font-mono text-[10px] tracking-forensic border ${activeSide === "B" ? "bg-info/20 border-info" : "border-border text-text-muted"}`}>{t.setB}</button>
          <button onClick={onClose} aria-label={t.closeLabel} className="w-7 h-7 flex items-center justify-center border border-border hover:bg-critical/30"><Icon name="x" size={14} /></button>
        </div>
      </div>

      <div className="flex h-[238px]">
        <div className="flex-1 p-3 border-r border-border">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-info" />
              <div className="font-display tracking-forensic text-xs">{t.rangeA}</div>
            </div>
            <div className="font-mono text-[10px] text-text-muted">{fmtDate(rangeA.t0)} → {fmtDate(rangeA.t1)} · {a?.n || 0} {t.photos.toLowerCase()}</div>
          </div>
          {a ? (
            <div className="space-y-1 font-mono text-[10px]">
              <div className="flex justify-between"><span className="text-text-muted">{t.dominantHyp}</span><span style={{ color: HYPOTHESIS_COLORS[a.dom] }}>{a.dom} · {t.hypothesisShort[a.dom]}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.fuzzyMode}</span><span style={{ color: FUZZY_COLORS[a.fuzzy] }}>{t.fuzzy[a.fuzzy]}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.pAll}</span>
                <span><span style={{ color: HYPOTHESIS_COLORS.H0 }}>{(a.p0 * 100).toFixed(0)}</span>/<span style={{ color: HYPOTHESIS_COLORS.H1 }}>{(a.p1 * 100).toFixed(0)}</span>/<span style={{ color: HYPOTHESIS_COLORS.H2 }}>{(a.p2 * 100).toFixed(0)}</span>%</span>
              </div>
            </div>
          ) : <div className="text-text-muted font-mono text-[10px]">{t.noPhotosInRange}</div>}
        </div>

        <div className="flex-[1.4] p-3 border-r border-border overflow-y-auto" data-scroll>
          <div className="font-display tracking-forensic text-xs mb-2">{t.metricDiff}</div>
          {a && b ? (
            <div className="border border-border">
              <div className="grid grid-cols-12 px-2 py-1 bg-surface-2 font-mono text-[9px] text-text-muted tracking-forensic">
                <div className="col-span-4">{t.colMetric}</div>
                <div className="col-span-2 text-right">{t.colA}</div>
                <div className="col-span-2 text-right">{t.colB}</div>
                <div className="col-span-2 text-right">{t.colDeltaC}</div>
                <div className="col-span-2 text-right">{t.colPolicy}</div>
              </div>
              {metrics.map(m => {
                const va = a[m.k];
                const vb = b[m.k];
                const delta = va - vb;
                const limit = TEXTURE_METRICS.has(m.k)
                  ? thresholds.texture_zone_delta_limit
                  : thresholds.geometry_zone_delta_limit;
                const exceeded = Math.abs(delta) > limit;
                return (
                  <div key={m.k} className={`grid grid-cols-12 px-2 py-0.5 font-mono text-[10px] border-t border-border ${exceeded ? "bg-critical/15" : ""}`}>
                    <div className="col-span-4">{m.label}</div>
                    <div className="col-span-2 text-right">{va.toFixed(3)}</div>
                    <div className="col-span-2 text-right">{vb.toFixed(3)}</div>
                    <div className="col-span-2 text-right" style={{ color: exceeded ? "#ff3b30" : "#7a7a8a" }}>{delta >= 0 ? "+" : ""}{delta.toFixed(3)}</div>
                    <div className="col-span-2 text-right text-text-faint">±{limit.toFixed(3)}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-text-muted font-mono text-[10px] py-4 px-3 text-center bg-surface-2 border border-border border-dashed">
              {t.setBPlaceholder}
            </div>
          )}
        </div>

        <div className="flex-1 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-warning" />
              <div className="font-display tracking-forensic text-xs">{t.rangeB}</div>
            </div>
            <div className="font-mono text-[10px] text-text-muted">
              {rangeB ? `${fmtDate(rangeB.t0)} → ${fmtDate(rangeB.t1)} · ${b?.n || 0} ${t.photos.toLowerCase()}` : t.notSet}
            </div>
          </div>
          {b ? (
            <div className="space-y-1 font-mono text-[10px]">
              <div className="flex justify-between"><span className="text-text-muted">{t.dominantHyp}</span><span style={{ color: HYPOTHESIS_COLORS[b.dom] }}>{b.dom} · {t.hypothesisShort[b.dom]}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.fuzzyMode}</span><span style={{ color: FUZZY_COLORS[b.fuzzy] }}>{t.fuzzy[b.fuzzy]}</span></div>
              <div className="flex justify-between"><span className="text-text-muted">{t.pAll}</span>
                <span><span style={{ color: HYPOTHESIS_COLORS.H0 }}>{(b.p0 * 100).toFixed(0)}</span>/<span style={{ color: HYPOTHESIS_COLORS.H1 }}>{(b.p1 * 100).toFixed(0)}</span>/<span style={{ color: HYPOTHESIS_COLORS.H2 }}>{(b.p2 * 100).toFixed(0)}</span>%</span>
              </div>
            </div>
          ) : (
            <div className="font-mono text-[10px] text-text-muted bg-surface-2 border border-dashed border-border p-2 flex items-start gap-2">
              <Icon name="info" size={12} className="mt-0.5 flex-shrink-0" /> {t.setBHint}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
