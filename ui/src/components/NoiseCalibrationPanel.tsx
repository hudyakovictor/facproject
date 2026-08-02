import { useEffect, useMemo, useState } from "react";
import Icon from "./Icon";
import { t } from "../i18n";
import {
  fetchNoiseModel, subtractAngleNoise,
  type AngleTolerance, type NoiseModelInfo, type NoiseSubtractionResult,
} from "../api";

/** Режим отображения значений на графиках и в таблицах. */
export type NoiseMode = "raw" | "compensated" | "both";

export const DEFAULT_TOLERANCE: AngleTolerance = { yaw: 2, pitch: 1, roll: 1 };

interface Props {
  /** Пара для предпросмотра эффекта компенсации; без неё показывается только модель. */
  photoA?: string;
  photoB?: string;
  tolerance?: AngleTolerance;
  mode?: NoiseMode;
  onToleranceChange?: (next: AngleTolerance) => void;
  onModeChange?: (next: NoiseMode) => void;
}

/** 🎚 Панель калибровки углового шума.
 *
 * Подключает к интерфейсу механизм `app6/stage2/angle_noise.py`, который был
 * полностью реализован, но не вызывался нигде, кроме тестов: ключевая идея ТЗ
 * («по данным калибровочной пары шум можно вычесть») не влияла ни на API, ни
 * на графики.
 *
 * Принципы подачи:
 *  * сырое и компенсированное значения показываются РЯДОМ — компенсация
 *    уменьшает расхождение, и тихая подмена числа недопустима;
 *  * видно покрытие: для какой доли пар шум вообще удалось вычесть;
 *  * вырожденный подбор (расхождение схлопнулось в ноль) помечается как
 *    дефект подбора, а не как «различий нет».
 */
export default function NoiseCalibrationPanel({
  photoA, photoB, tolerance, mode = "both", onToleranceChange, onModeChange,
}: Props) {
  const active = tolerance ?? DEFAULT_TOLERANCE;
  const [draft, setDraft] = useState<AngleTolerance>(active);
  const [model, setModel] = useState<NoiseModelInfo | null>(null);
  const [preview, setPreview] = useState<NoiseSubtractionResult | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => { setDraft(active); }, [active.yaw, active.pitch, active.roll]);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    fetchNoiseModel(active)
      .then(value => { if (!cancelled) { setModel(value); setStatus("ready"); } })
      .catch((err: unknown) => {
        if (cancelled) return;
        setStatus("error");
        setErrorMessage(err instanceof Error ? err.message : String(err));
      });
    return () => { cancelled = true; };
  }, [active.yaw, active.pitch, active.roll]);

  useEffect(() => {
    if (!photoA || !photoB) { setPreview(null); return undefined; }
    let cancelled = false;
    subtractAngleNoise(photoA, photoB, active)
      .then(value => { if (!cancelled) setPreview(value); })
      .catch(() => { if (!cancelled) setPreview(null); });
    return () => { cancelled = true; };
  }, [photoA, photoB, active.yaw, active.pitch, active.roll]);

  const coveragePct = useMemo(() => {
    const c = model?.coverage.coverage;
    return c === null || c === undefined ? null : c * 100;
  }, [model]);

  return (
    <section className="space-y-3">
      <header>
        <div className="font-display text-sm tracking-forensic">{t.noiseTitle}</div>
        <p className="font-mono text-[9px] text-text-faint mt-0.5 leading-snug">{t.noiseSub}</p>
      </header>

      {status === "error" && (
        <div role="alert" className="bg-warning/15 border border-warning p-2 font-mono text-[10px] text-warning">
          {t.noiseUnavailable}: {errorMessage}
        </div>
      )}

      {/* Режим отображения значений */}
      <div className="bg-surface-2 border border-border p-2">
        <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-1.5">
          {t.noiseShowMode}
        </div>
        <div className="flex gap-px">
          {(["raw", "compensated", "both"] as const).map(value => (
            <button key={value} onClick={() => onModeChange?.(value)} aria-pressed={mode === value}
              disabled={!onModeChange}
              className={`flex-1 px-2 py-1 font-mono text-[9px] tracking-forensic border disabled:opacity-50 ${mode === value ? "bg-info/25 border-info text-text" : "border-border text-text-muted hover:text-text"}`}>
              {value === "raw" ? t.noiseModeRaw : value === "compensated" ? t.noiseModeCompensated : t.noiseModeBoth}
            </button>
          ))}
        </div>
        <div className="font-mono text-[8px] text-warning mt-1.5 flex items-start gap-1">
          <Icon name="alert-triangle" size={9} color="#e8af34" className="mt-px flex-shrink-0" />
          {t.noiseModeHint}
        </div>
      </div>

      {/* Допуски подбора */}
      <div className="bg-surface-2 border border-border p-2">
        <div className="font-mono text-[9px] tracking-forensic text-text-muted mb-2">
          {t.noiseTolerance}
        </div>
        {([
          ["yaw", t.noiseYaw, 10] as const,
          ["pitch", t.noisePitch, 10] as const,
          ["roll", t.noiseRoll, 10] as const,
        ]).map(([axis, label, max]) => (
          <div key={axis} className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[9px] text-text-muted w-14">{label}</span>
            <input type="range" min={0} max={max} step={0.1} value={draft[axis]}
              aria-label={label} className="flex-1"
              onChange={e => setDraft({ ...draft, [axis]: +e.target.value })} />
            <span className="font-mono text-[9px] w-10 text-right tabular-nums">
              {draft[axis].toFixed(1)}°
            </span>
          </div>
        ))}
        <button onClick={() => onToleranceChange?.(draft)} disabled={!onToleranceChange}
          className="mt-1 w-full px-2 py-1 font-mono text-[9px] tracking-forensic border border-info/50 bg-info/15 hover:bg-info/30 disabled:opacity-50">
          {t.noiseApply}
        </button>
        <div className="font-mono text-[8px] text-text-faint mt-1.5 leading-snug">
          {t.noiseToleranceHint}
        </div>
      </div>

      {/* Покрытие компенсации */}
      {model && (
        <div className="bg-surface-2 border border-border p-2 font-mono text-[9px] space-y-1">
          <div className="flex justify-between">
            <span className="text-text-muted">{t.noiseCoverage}</span>
            <span style={{ color: coveragePct === null ? "#797876" : coveragePct > 70 ? "#6daa45" : coveragePct > 30 ? "#e8af34" : "#dd6974" }}>
              {model.coverage.compensated_count} {t.noiseCoverageOf} {model.coverage.pair_count}
              {coveragePct !== null && ` · ${coveragePct.toFixed(0)}%`}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-muted">{t.noiseIndexSize}</span>
            <span>{model.index_size}</span>
          </div>
          {model.coverage.median_noise_removed !== null && (
            <div className="flex justify-between">
              <span className="text-text-muted">{t.noiseMedianRemoved}</span>
              <span>{model.coverage.median_noise_removed.toFixed(5)}</span>
            </div>
          )}
          {Object.keys(model.coverage.uncompensated_reasons).length > 0 && (
            <div className="pt-1 border-t border-border">
              <div className="text-text-muted mb-0.5">{t.noiseReasons}</div>
              {Object.entries(model.coverage.uncompensated_reasons).map(([reason, count]) => (
                <div key={reason} className="flex justify-between gap-2">
                  <span className="text-text-faint truncate">{reason}</span>
                  <span className="text-warning flex-shrink-0">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Предпросмотр эффекта на конкретной паре */}
      {preview && <NoisePreview preview={preview} />}
    </section>
  );
}

function NoisePreview({ preview }: { preview: NoiseSubtractionResult }) {
  const entries = Object.entries(preview.metrics);
  return (
    <div className="bg-surface border border-border p-2 space-y-1.5">
      {preview.angle_delta && (
        <div className="font-mono text-[9px] flex justify-between">
          <span className="text-text-muted">{t.noiseAngleDelta}</span>
          <span className="tabular-nums">
            yaw {preview.angle_delta.yaw.toFixed(2)}° · pitch {preview.angle_delta.pitch.toFixed(2)}° · roll {preview.angle_delta.roll.toFixed(2)}°
          </span>
        </div>
      )}

      {preview.uncompensated && (
        <div role="status" className="bg-warning/15 border border-warning p-1.5 font-mono text-[9px] text-warning">
          {t.noiseUncompensated}: {preview.reason}
        </div>
      )}

      {/* Вырожденный подбор — не «различий нет», а дефект калибровки. */}
      {preview.degenerate_match && (
        <div role="alert" className="bg-critical/15 border border-critical p-1.5 font-mono text-[9px]">
          <div className="text-critical">{t.noiseDegenerate}</div>
          <div className="text-text-muted mt-0.5 leading-snug">{t.noiseDegenerateWhy}</div>
        </div>
      )}

      {!preview.uncompensated && preview.match && (
        <div className="font-mono text-[8px] text-text-faint">
          {t.noiseMatched}: {preview.match.dataset_id} · {preview.match.record_a} ↔ {preview.match.record_b}
          {" · "}{t.noiseMatchDistance} {preview.match.match_distance.toFixed(3)}
        </div>
      )}

      {entries.length > 0 && (
        <table className="w-full border-collapse font-mono text-[9px]">
          <thead>
            <tr className="text-text-faint">
              <th className="text-left font-normal">метрика</th>
              <th className="text-right font-normal">{t.noiseRawValue}</th>
              <th className="text-right font-normal">{t.noiseNoiseValue}</th>
              <th className="text-right font-normal">{t.noiseCompValue}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key} className="border-t border-border/60">
                <td className="text-text-muted truncate">{key}</td>
                <td className="text-right tabular-nums">{value.raw.toFixed(5)}</td>
                <td className="text-right tabular-nums text-text-faint">
                  {value.noise === null ? "—" : value.noise.toFixed(5)}
                </td>
                <td className="text-right tabular-nums"
                  style={{ color: value.compensated === null ? "#797876" : "#5591c7" }}>
                  {value.compensated === null ? "—" : value.compensated.toFixed(5)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
