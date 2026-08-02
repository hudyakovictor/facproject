import { createContext, useContext } from "react";
import { ERA_META, REF, type Photo } from "./data";

/** Референс одной метрики: медиана и разброс базового сегмента. */
export interface MetricRef { median: number; std: number }

/** Набор референсов + сведения о том, на чём он построен.
 *
 * `sufficient === false` означает, что базовый сегмент слишком мал для
 * осмысленного z-score. В этом случае интерфейс ОБЯЗАН не показывать z-score
 * (`app6/AGENTS.md`: недостаток данных — это `inconclusive`, а не число).
 */
export interface BaselineRefs {
  refs: Record<string, MetricRef>;
  baselineEra: string | null;
  sampleSize: number;
  sufficient: boolean;
  source: "api" | "builtin-demo";
}

/** Минимальный размер базового сегмента. Ниже — разброс оценивается по
 * единицам наблюдений, и |z| становится артефактом малой выборки. */
export const MIN_BASELINE_SAMPLE = 8;

export const BASELINE_METRIC_KEYS = [
  "boneScore", "orbit", "chin", "jaw", "cheek", "symmetry", "yaw",
  "siliconeProb", "specular", "lbpEntropy", "frangi", "wrinkle", "subsurface", "visualAge",
] as const;

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

/** Устойчивый разброс: 1.4826 · MAD.
 *
 * Обычное стандартное отклонение раздувается единственным выбросом, а в
 * архиве 1999–2025 выбросы гарантированы (разное качество съёмки, ракурсы).
 * MAD даёт сопоставимую с σ величину для нормальных данных и не «съедает»
 * реальные аномалии. */
function robustStd(values: number[], center: number): number {
  if (values.length < 2) return 0;
  const deviations = values.map(v => Math.abs(v - center));
  return 1.4826 * median(deviations);
}

/** 🏭 Построить референсы по ФАКТИЧЕСКИ загруженным фотографиям.
 *
 * Раньше `REF` был модульной константой, вычисленной один раз из встроенного
 * демо-набора и никогда не пересчитываемой. Все z-score на таймлайне
 * сравнивали реальные метрики с медианой синтетики — подсветка аномалий не
 * имела отношения к анализируемому архиву.
 *
 * Базовый сегмент — самый ранний по времени: гипотеза H0 («это один и тот же
 * человек») проверяется относительно наиболее раннего состояния, а не
 * относительно всего набора, который может уже содержать подмену.
 */
export function computeBaselineRefs(photos: Photo[]): BaselineRefs {
  if (!photos.length) {
    return { refs: REF, baselineEra: null, sampleSize: 0, sufficient: false, source: "builtin-demo" };
  }

  // Самый ранний сегмент по минимальной дате кадра.
  const earliestByEra = new Map<string, number>();
  for (const photo of photos) {
    const known = earliestByEra.get(photo.era);
    if (known === undefined || photo.t < known) earliestByEra.set(photo.era, photo.t);
  }
  const baselineEra = [...earliestByEra.entries()].sort((a, b) => a[1] - b[1])[0]?.[0] ?? null;
  const sample = baselineEra === null ? [] : photos.filter(p => p.era === baselineEra);

  const refs: Record<string, MetricRef> = {};
  for (const key of BASELINE_METRIC_KEYS) {
    const values = sample
      .map(p => p[key as keyof Photo])
      .filter((v): v is number => typeof v === "number" && Number.isFinite(v));
    if (!values.length) {
      // Канал отсутствует в этом наборе (например research-режим не отдаёт
      // текстуру) — берём встроенный референс, но выборку не подделываем.
      refs[key] = REF[key] ?? { median: 0, std: 1 };
      continue;
    }
    const center = median(values);
    const spread = robustStd(values, center);
    refs[key] = { median: center, std: Math.max(1e-6, spread) };
  }

  return {
    refs,
    baselineEra,
    sampleSize: sample.length,
    sufficient: sample.length >= MIN_BASELINE_SAMPLE,
    source: "api",
  };
}

/** Fallback до появления данных: встроенный демо-референс. */
export const BUILTIN_BASELINE: BaselineRefs = {
  refs: REF,
  baselineEra: Object.keys(ERA_META)[0] ?? null,
  sampleSize: 0,
  sufficient: false,
  source: "builtin-demo",
};

export const BaselineContext = createContext<BaselineRefs>(BUILTIN_BASELINE);

/** Референсы текущего набора. Компоненты обязаны проверять `sufficient`
 * перед показом z-score. */
export function useBaseline(): BaselineRefs {
  return useContext(BaselineContext);
}
