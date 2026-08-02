import { useMemo } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import {
  DEFAULT_GRADIENT, GRADIENT_PRESETS, evaluateGradient, gradientToCss,
  sanitizeGradient, toHex, valueAt,
  type GradientModel, type GradientStop,
} from "../gradient";

interface Props {
  model: GradientModel;
  onChange: (next: GradientModel) => void;
  /** Отметки на шкале — например пороги классификации точек. */
  marks?: { value: number; label: string; color?: string }[];
}

/** 🎨 Редактор градиента тепловой карты с посегментной резкостью.
 *
 * Отвечает на требование: переход должен быть НЕ равномерным — плавным в
 * пределах допустимой для одного человека изменчивости и резким там, где
 * начинаются аномальные различия.
 *
 * Каждая остановка задаёт цвет, позицию и `sharpness` перехода к следующей.
 * Всё превью строится тем же `evaluateGradient`, что и раскраска меша, —
 * то, что видит пользователь в редакторе, буквально то же, что попадёт на
 * тепловую карту.
 */
export default function GradientEditor({ model, onChange, marks = [] }: Props) {
  const safe = useMemo(() => sanitizeGradient(model), [model]);
  const css = useMemo(() => gradientToCss(safe), [safe]);

  const update = (index: number, patch: Partial<GradientStop>) => {
    const stops = safe.stops.map((stop, i) => (i === index ? { ...stop, ...patch } : stop));
    onChange(sanitizeGradient({ ...safe, stops }));
  };

  const removeStop = (index: number) => {
    // Минимум две остановки: градиент из одной точки не определён.
    if (safe.stops.length <= 2) return;
    onChange(sanitizeGradient({ ...safe, stops: safe.stops.filter((_, i) => i !== index) }));
  };

  const addStop = () => {
    // Новая остановка — в самый широкий промежуток, чтобы не наслаивать точки.
    let bestIndex = 0;
    let bestGap = -1;
    for (let i = 1; i < safe.stops.length; i++) {
      const gap = safe.stops[i].position - safe.stops[i - 1].position;
      if (gap > bestGap) { bestGap = gap; bestIndex = i; }
    }
    const prev = safe.stops[bestIndex - 1];
    const next = safe.stops[bestIndex];
    const position = (prev.position + next.position) / 2;
    const inserted: GradientStop = {
      position,
      color: toHex(evaluateGradient(safe, position)),
      sharpness: 0,
    };
    const stops = [...safe.stops];
    stops.splice(bestIndex, 0, inserted);
    onChange(sanitizeGradient({ ...safe, stops }));
  };

  return (
    <section className="space-y-3">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-display text-sm tracking-forensic">{t.gradTitle}</div>
          <p className="font-mono text-[9px] text-text-faint mt-0.5 leading-snug">{t.gradSub}</p>
        </div>
        <select
          aria-label={t.gradPreset}
          defaultValue=""
          onChange={e => {
            const preset = GRADIENT_PRESETS[e.target.value];
            if (preset) onChange(sanitizeGradient({ ...preset.model, maxReference: safe.maxReference }));
          }}
          className="bg-surface-2 border border-border px-2 py-1 font-mono text-[9px] text-text flex-shrink-0">
          <option value="">{t.gradPreset}</option>
          {Object.entries(GRADIENT_PRESETS).map(([key, preset]) => (
            <option key={key} value={key}>{t[preset.labelKey as keyof typeof t] as string}</option>
          ))}
        </select>
      </header>

      {/* Живое превью шкалы с отметками порогов */}
      <div>
        <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-1">
          {t.gradPreview}
        </div>
        <div className="relative">
          <div className="h-6 w-full border border-border" style={{ background: css }} />
          {/* Маркеры остановок */}
          {safe.stops.map((stop, i) => (
            <div key={`s${i}`} className="absolute -top-1 w-px h-8 bg-text/40 pointer-events-none"
              style={{ left: `${stop.position * 100}%` }} />
          ))}
          {/* Внешние отметки (например пороги классификации точек) */}
          {marks.map(mark => {
            const pos = Math.max(0, Math.min(1, mark.value / Math.max(1e-9, safe.maxReference)));
            return (
              <div key={mark.label} className="absolute -bottom-1 h-8 w-px pointer-events-none"
                style={{ left: `${pos * 100}%`, background: mark.color ?? "#ffffff" }}
                title={`${mark.label}: ${mark.value.toFixed(4)}`} />
            );
          })}
        </div>
        {/* Числовая шкала */}
        <div className="relative h-4 mt-0.5 font-mono text-[8px] text-text-faint">
          {[0, 0.25, 0.5, 0.75, 1].map(f => (
            <span key={f} className="absolute -translate-x-1/2" style={{ left: `${f * 100}%` }}>
              {valueAt(safe, f).toFixed(3)}
            </span>
          ))}
        </div>
        <div className="font-mono text-[8px] text-text-faint mt-2">{t.gradLiveHint}</div>
      </div>

      {/* Кривая перехода: наглядно показывает, где переход резкий */}
      <TransitionCurve model={safe} />

      {/* Верх шкалы */}
      <div className="flex items-center gap-2">
        <span className="font-mono text-[9px] text-text-muted flex-1 truncate">
          {t.gradMaxReference}
        </span>
        <input type="number" min={0.001} step={0.005} value={safe.maxReference}
          aria-label={t.gradMaxReference}
          onChange={e => {
            const v = Number(e.target.value);
            if (Number.isFinite(v) && v > 0) onChange(sanitizeGradient({ ...safe, maxReference: v }));
          }}
          className="w-20 bg-surface-2 border border-border px-1.5 py-1 font-mono text-[9px] text-text text-right" />
      </div>
      <div className="font-mono text-[8px] text-text-faint -mt-2">{t.gradMaxReferenceHint}</div>

      {/* Остановки */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="font-mono text-[9px] tracking-forensic text-text-muted">
            {t.gradStops} · {safe.stops.length}
          </span>
          <button onClick={addStop}
            className="px-2 py-0.5 font-mono text-[9px] border border-border text-text-muted hover:text-text">
            + {t.gradAddStop}
          </button>
        </div>

        <div className="space-y-1.5">
          {safe.stops.map((stop, index) => {
            const isLast = index === safe.stops.length - 1;
            return (
              <div key={index} className="bg-surface-2 border border-border p-1.5">
                <div className="flex items-center gap-1.5">
                  <input type="color" value={stop.color}
                    aria-label={`${t.gradColor} ${index + 1}`}
                    onChange={e => update(index, { color: e.target.value })}
                    className="w-6 h-6 bg-transparent border border-border cursor-pointer flex-shrink-0" />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1">
                      <span className="font-mono text-[8px] text-text-muted w-12">{t.gradPosition}</span>
                      <input type="range" min={0} max={1} step={0.01} value={stop.position}
                        aria-label={`${t.gradPosition} ${index + 1}`}
                        onChange={e => update(index, { position: +e.target.value })}
                        className="flex-1" />
                      <span className="font-mono text-[8px] w-14 text-right tabular-nums">
                        {valueAt(safe, stop.position).toFixed(4)}
                      </span>
                    </div>

                    {/* Резкость перехода — только если есть следующий сегмент */}
                    {!isLast && (
                      <div className="flex items-center gap-1 mt-0.5">
                        <span className="font-mono text-[8px] text-text-muted w-12">{t.gradSharpness}</span>
                        <input type="range" min={0} max={1} step={0.05} value={stop.sharpness}
                          aria-label={`${t.gradSharpness} ${index + 1}`}
                          onChange={e => update(index, { sharpness: +e.target.value })}
                          className="flex-1" />
                        <span className="font-mono text-[8px] w-14 text-right tabular-nums"
                          style={{ color: stop.sharpness > 0.6 ? "#fdab43" : "#797876" }}>
                          {stop.sharpness.toFixed(2)}
                        </span>
                      </div>
                    )}
                  </div>

                  <button onClick={() => removeStop(index)}
                    disabled={safe.stops.length <= 2}
                    aria-label={t.gradRemoveStop} title={t.gradRemoveStop}
                    className="w-5 h-5 flex items-center justify-center text-text-muted hover:text-critical disabled:opacity-30 flex-shrink-0">
                    <Icon name="x" size={10} />
                  </button>
                </div>

                {stop.label && (
                  <div className="font-mono text-[8px] text-text-faint mt-0.5 pl-8">{stop.label}</div>
                )}
              </div>
            );
          })}
        </div>
        <div className="font-mono text-[8px] text-text-faint mt-1.5 leading-snug">
          {t.gradSharpnessHint}
        </div>
      </div>

      <button onClick={() => onChange(DEFAULT_GRADIENT)}
        className="w-full px-2 py-1 font-mono text-[9px] tracking-forensic border border-border text-text-muted hover:text-text">
        {t.gradReset}
      </button>
    </section>
  );
}

/** Кривая перехода: показывает, на каких участках цвет меняется резко.
 *
 * По вертикали откладывается пройденный «путь» по цветовому пространству —
 * накопленное изменение цвета. Крутой участок = резкий переход. Это делает
 * настройку `sharpness` наглядной, а не абстрактным числом. */
function TransitionCurve({ model }: { model: GradientModel }) {
  const path = useMemo(() => {
    const steps = 120;
    const W = 300, H = 60;
    // Накопленное расстояние в RGB — монотонная мера «сколько цвета пройдено».
    const distances: number[] = [0];
    let prev = evaluateGradient(model, 0);
    for (let i = 1; i <= steps; i++) {
      const cur = evaluateGradient(model, i / steps);
      const d = Math.hypot(cur.r - prev.r, cur.g - prev.g, cur.b - prev.b);
      distances.push(distances[i - 1] + d);
      prev = cur;
    }
    const total = distances[distances.length - 1] || 1;
    return distances
      .map((d, i) => `${((i / steps) * W).toFixed(1)} ${(H - (d / total) * H).toFixed(1)}`)
      .join(" L ");
  }, [model]);

  return (
    <div>
      <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-1">
        {t.gradCurveTitle}
      </div>
      <svg viewBox="0 0 300 60" className="w-full border border-border bg-surface"
        style={{ height: 60 }} role="img" aria-label={t.gradCurveTitle}>
        {[0.25, 0.5, 0.75].map(f => (
          <line key={f} x1={300 * f} y1={0} x2={300 * f} y2={60}
            stroke="rgba(255,255,255,0.06)" />
        ))}
        <path d={`M ${path}`} fill="none" stroke="#5591c7" strokeWidth="1.2" />
      </svg>
      <div className="font-mono text-[8px] text-text-faint mt-0.5">{t.gradCurveHint}</div>
    </div>
  );
}
