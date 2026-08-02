/** Эмпирический тренд метрики во времени внутри ОДНОГО pose bin.
 *
 * ⚠️ Это НЕ биологическая модель старения. Это робастная линия тренда по
 * фактическим наблюдениям базового периода, подписанная в интерфейсе именно
 * так. Называть её «ожидаемым старением» в смысле физиологии было бы
 * заявкой на точность, которой у нас нет (`app6/AGENTS.md`: формулировки
 * должны быть проверяемыми).
 *
 * Назначение: дать глазу опорную линию, относительно которой видно, идёт ли
 * изменение метрики плавно (совместимо с постепенным процессом) или скачком.
 */

export interface TrendPoint { t: number; v: number }

export interface TrendModel {
  /** Наклон в единицах метрики за миллисекунду. */
  slope: number;
  /** Значение тренда в момент t0. */
  intercept: number;
  t0: number;
  /** Робастный разброс остатков (1.4826·MAD) — полуширина полосы ±1σ. */
  residualSpread: number;
  /** Число наблюдений, на которых построен тренд. */
  sampleSize: number;
  /** Тренд пригоден к показу. */
  usable: boolean;
  predict: (t: number) => number;
}

const MIN_TREND_SAMPLE = 6;

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

/** 🏭 Оценка тренда методом Тейла — Сена.
 *
 * Медиана попарных наклонов. В отличие от МНК, устойчива к выбросам: до ~29%
 * испорченных наблюдений не смещают оценку. Для архива с разнородным
 * качеством съёмки это принципиально — единственный плохой кадр не должен
 * задавать наклон «ожидания».
 *
 * Сложность O(n²) по парам; для дорожки таймлайна n — это кадры одного
 * pose bin (десятки), поэтому приемлемо. При n > 120 берётся равномерная
 * подвыборка, чтобы не тормозить рендер.
 */
export function fitTrend(points: TrendPoint[]): TrendModel {
  const clean = points
    .filter(p => Number.isFinite(p.t) && Number.isFinite(p.v))
    .sort((a, b) => a.t - b.t);

  const empty: TrendModel = {
    slope: 0, intercept: 0, t0: 0, residualSpread: 0,
    sampleSize: clean.length, usable: false, predict: () => 0,
  };
  if (clean.length < MIN_TREND_SAMPLE) return empty;

  const sample = clean.length > 120
    ? clean.filter((_, i) => i % Math.ceil(clean.length / 120) === 0)
    : clean;

  const slopes: number[] = [];
  for (let i = 0; i < sample.length; i++) {
    for (let j = i + 1; j < sample.length; j++) {
      const dt = sample[j].t - sample[i].t;
      if (dt <= 0) continue;   // одинаковые даты не задают наклон
      slopes.push((sample[j].v - sample[i].v) / dt);
    }
  }
  if (!slopes.length) return empty;

  const slope = median(slopes);
  const t0 = sample[0].t;
  // Свободный член: медиана (v - slope·(t - t0)) — тоже робастная оценка.
  const intercept = median(sample.map(p => p.v - slope * (p.t - t0)));
  const predict = (t: number) => intercept + slope * (t - t0);

  const residuals = sample.map(p => Math.abs(p.v - predict(p.t)));
  const residualSpread = 1.4826 * median(residuals);

  return {
    slope, intercept, t0,
    residualSpread: Math.max(1e-9, residualSpread),
    sampleSize: sample.length,
    usable: true,
    predict,
  };
}

/** Отклонение наблюдения от тренда в единицах робастного разброса.
 * Возвращает `null`, когда тренд непригоден — «нет оценки» вместо нуля. */
export function trendDeviation(model: TrendModel, point: TrendPoint): number | null {
  if (!model.usable) return null;
  return (point.v - model.predict(point.t)) / model.residualSpread;
}
