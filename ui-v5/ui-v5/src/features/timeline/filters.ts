import type { ResearchPhoto } from "../../shared/researchApi";

/**
 * Живые фильтры вида (§9.1, §9.4, §9.5 ТЗ).
 *
 * Фильтр вида меняет только отображение и не создаёт нового научного
 * результата: он не перезапускает расчёт и не меняет выборку будущего прогона.
 * Разделение существенно — порог, подкрученный до красивой картинки, не должен
 * выглядеть как результат анализа. Поэтому здесь считаются и показываются
 * последствия каждого порога: сколько кадров он убирает и какие именно.
 *
 * Профили анализа (§9.6) — отдельная сущность с версионированием и манифестом
 * выборки; они появятся вместе с контуром прогонов и здесь не подменяются
 * фильтром вида.
 */

export interface FilterSettings {
  qualityThreshold: number;
  poseAngleThreshold: number;
  mouthThreshold: number;
  findingsMode: boolean;
  search: string;
  activePose: string;
  multiPose: boolean;
}

/** Причина, по которой кадр не показан. */
export interface ExclusionReason {
  /** Короткая запись вида `quality 0.31 < 0.50`. */
  text: string;
  /** Какой регулятор её снимает. */
  control: "quality" | "pose" | "mouth" | "poseBin" | "search";
}

/**
 * Почему кадр не виден. Возвращаются все причины сразу, а не первая: сняв один
 * порог, пользователь иначе обнаружит, что кадр по-прежнему скрыт другим, и
 * будет искать причину заново.
 */
export function exclusionReasons(
  photo: ResearchPhoto,
  settings: FilterSettings,
): ExclusionReason[] {
  const reasons: ExclusionReason[] = [];

  // Отсутствие оценки — не ноль: такой кадр порогом не отбрасывается.
  if (typeof photo.quality === "number" && photo.quality < settings.qualityThreshold) {
    reasons.push({
      text: `quality ${photo.quality.toFixed(2)} < ${settings.qualityThreshold.toFixed(2)}`,
      control: "quality",
    });
  }

  // Поля остаточного угла независимы: отсутствие одного из них не должно
  // превращать весь максимум в NaN и скрывать остальные валидные измерения.
  const residualValues = [photo.residualYaw, photo.residualPitch, photo.residualRoll]
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
    .map((value) => Math.abs(value));
  const residual = residualValues.length > 0 ? Math.max(...residualValues) : null;
  if (residual !== null && residual > settings.poseAngleThreshold) {
    reasons.push({
      text: `остаточный угол ${residual.toFixed(1)}° > ±${settings.poseAngleThreshold}°`,
      control: "pose",
    });
  }

  const mouth = photo.jawOpenRatio;
  if (typeof mouth === "number" && mouth > settings.mouthThreshold) {
    reasons.push({
      text: `рот ${mouth.toFixed(2)} > ${settings.mouthThreshold.toFixed(2)}`,
      control: "mouth",
    });
  }

  if (
    !settings.multiPose &&
    photo.bucket.toLowerCase() !== settings.activePose.toLowerCase()
  ) {
    reasons.push({
      text: `pose_bin=${photo.bucket} ≠ ${settings.activePose}`,
      control: "poseBin",
    });
  }

  const query = settings.search.trim().toLowerCase();
  if (query) {
    const haystack = [photo.id, photo.date, photo.bucket, photo.era, photo.fuzzy, ...photo.flags]
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(query)) {
      reasons.push({ text: `не совпадает с поиском «${settings.search.trim()}»`, control: "search" });
    }
  }

  return reasons;
}

export interface HistogramBin {
  from: number;
  to: number;
  /** Всего кадров в корзине. */
  total: number;
  /** Сколько из них проходят текущий порог. */
  kept: number;
}

/**
 * Распределение величины с отметкой текущего среза (§9.4).
 *
 * Кадры без значения не попадают в гистограмму и учитываются отдельно: место
 * в корзине «0» приписало бы им измерение, которого нет.
 */
export function histogramOf(
  photos: readonly ResearchPhoto[],
  value: (photo: ResearchPhoto) => number | null,
  options: { min: number; max: number; bins: number; threshold: number },
): { bins: HistogramBin[]; withoutValue: number; kept: number; dropped: number } {
  const { min, max, bins, threshold } = options;
  const width = (max - min) / bins || 1;
  const result: HistogramBin[] = Array.from({ length: bins }, (_, i) => ({
    from: min + i * width,
    to: min + (i + 1) * width,
    total: 0,
    kept: 0,
  }));

  let withoutValue = 0;
  let kept = 0;
  let dropped = 0;

  for (const photo of photos) {
    const v = value(photo);
    if (v === null) {
      withoutValue += 1;
      kept += 1; // отсутствие оценки не является основанием отбросить кадр
      continue;
    }
    const index = Math.min(bins - 1, Math.max(0, Math.floor((v - min) / width)));
    result[index].total += 1;
    if (v >= threshold) {
      result[index].kept += 1;
      kept += 1;
    } else {
      dropped += 1;
    }
  }

  return { bins: result, withoutValue, kept, dropped };
}

/**
 * Порог оставил слишком мало кадров, чтобы на них что-то строить.
 *
 * Число выбрано как нижняя граница, ниже которой разброс перестаёт быть
 * оценимым; это предупреждение, а не запрет.
 */
export const SMALL_N = 5;

export function isSmallSample(count: number): boolean {
  return count > 0 && count < SMALL_N;
}
