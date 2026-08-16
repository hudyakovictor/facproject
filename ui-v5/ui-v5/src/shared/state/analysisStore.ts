import { create } from "zustand";
import { POSE_BIN_IDS } from "../poseBins";
import { METRIC_CATALOG } from "../metrics";

/**
 * Общее состояние анализа для всей рабочей станции.
 *
 * До этого модуля верхняя панель хранила состояние в `useState` внутри
 * `RootLayout` и передавала его пропсами только вниз, в саму панель. Страницы
 * этих значений не получали: выбор ракурса, пороги и режим находок в шапке ни
 * на что не влияли (BUG-1). Одновременно каждая страница вела собственные
 * `useState` для тех же понятий, поэтому «активный ракурс» на таймлайне и в
 * шапке были разными величинами с одинаковым названием.
 *
 * Пакет `zustand` числился в зависимостях как «слой состояния» и не
 * импортировался ни разу.
 */

/**
 * Метрики, которые могут отображаться дорожками таймлайна.
 *
 * Список величин ведётся в `shared/metrics.ts` вместе с единицами измерения и
 * статусом калибровки. Дублировать его здесь union-типом значило бы завести
 * второй источник истины: добавленная в каталог метрика молча не появлялась бы
 * в меню, а удалённая оставалась бы валидной в URL.
 */
export type MetricKey = string;

/** Идентификаторы всех известных метрик — для проверки значений из URL. */
export const METRIC_KEYS: readonly string[] = METRIC_CATALOG.map((metric) => metric.id);

/** Дорожки, которые Stage 1 реально заполняет в info.json. */
export const DEFAULT_VISIBLE_METRICS: MetricKey[] = [
  "quality",
  "alignmentQuality",
  "yaw",
  "pitch",
];

export interface AnalysisState {
  /** Активный бин ракурса. Инвариант 1: сравнение идёт внутри одного бина. */
  activePose: string;
  /** Показывать все бины сразу. Пара A/B при этом остаётся запрещена между бинами. */
  multiPose: boolean;
  /** Порог качества кадра, 0…1. */
  qualityThreshold: number;
  /** Порог активности рта, 0…1. */
  mouthThreshold: number;
  /** Допуск угла отклонения позы в градусах. */
  poseAngleThreshold: number;
  /** Показывать только находки. */
  findingsMode: boolean;
  /** Поисковый запрос по идентификатору, дате, флагам. */
  search: string;
  /** Выбранные для сравнения кадры. */
  pairA: string | null;
  pairB: string | null;
  /** Кадр, открытый в контекстной панели. */
  selectedPhoto: string | null;
  /** Видимые дорожки метрик. */
  visibleMetrics: MetricKey[];
  /**
   * Слепой режим: скрывает идентифицирующие подписи, чтобы рецензент оценивал
   * геометрию, а не узнавал кадр (§18.3 ТЗ).
   */
  blindMode: boolean;

  setActivePose: (pose: string) => void;
  setMultiPose: (value: boolean) => void;
  setQualityThreshold: (value: number) => void;
  setMouthThreshold: (value: number) => void;
  setPoseAngleThreshold: (value: number) => void;
  setFindingsMode: (value: boolean) => void;
  setSearch: (value: string) => void;
  setSelectedPhoto: (id: string | null) => void;
  setVisibleMetrics: (metrics: MetricKey[]) => void;
  toggleMetric: (metric: MetricKey) => void;
  setBlindMode: (value: boolean) => void;
  /** Назначить кадр в пару. Возвращает причину отказа либо null. */
  assignToPair: (id: string, bucket: string, bucketOf: (id: string) => string | undefined) => string | null;
  swapPair: () => void;
  clearPair: () => void;
  /** Применить состояние из URL, не создавая лишних перерисовок. */
  hydrate: (patch: Partial<AnalysisState>) => void;
}

export const useAnalysisStore = create<AnalysisState>((set, get) => ({
  activePose: POSE_BIN_IDS.includes("frontal") ? "frontal" : POSE_BIN_IDS[0],
  multiPose: false,
  qualityThreshold: 0,
  mouthThreshold: 0.35,
  poseAngleThreshold: 6,
  findingsMode: false,
  search: "",
  pairA: null,
  pairB: null,
  selectedPhoto: null,
  visibleMetrics: DEFAULT_VISIBLE_METRICS,
  blindMode: false,

  setActivePose: (activePose) => set({ activePose }),
  setMultiPose: (multiPose) => set({ multiPose }),
  setQualityThreshold: (qualityThreshold) => set({ qualityThreshold }),
  setMouthThreshold: (mouthThreshold) => set({ mouthThreshold }),
  setPoseAngleThreshold: (poseAngleThreshold) => set({ poseAngleThreshold }),
  setFindingsMode: (findingsMode) => set({ findingsMode }),
  setSearch: (search) => set({ search }),
  setSelectedPhoto: (selectedPhoto) => set({ selectedPhoto }),
  setVisibleMetrics: (visibleMetrics) => set({ visibleMetrics }),
  toggleMetric: (metric) =>
    set((state) => ({
      visibleMetrics: state.visibleMetrics.includes(metric)
        ? state.visibleMetrics.filter((item) => item !== metric)
        : [...state.visibleMetrics, metric],
    })),
  setBlindMode: (blindMode) => set({ blindMode }),

  /**
   * Инвариант 5 AGENTS.md: сравнивать можно только кадры одного бина ракурса.
   * Проверка живёт в сторе, а не в компоненте, чтобы её нельзя было обойти,
   * назначив пару с другого экрана.
   */
  assignToPair: (id, bucket, bucketOf) => {
    const { pairA } = get();
    if (!pairA) {
      set({ pairA: id });
      return null;
    }
    if (pairA === id) return null;
    const anchorBucket = bucketOf(pairA);
    if (anchorBucket && anchorBucket !== bucket) {
      return `Кадры принадлежат разным бинам ракурса (${anchorBucket} и ${bucket}). Сравнение геометрии допустимо только внутри одного бина.`;
    }
    set({ pairB: id });
    return null;
  },
  swapPair: () => set((state) => ({ pairA: state.pairB, pairB: state.pairA })),
  clearPair: () => set({ pairA: null, pairB: null }),
  hydrate: (patch) => set(patch),
}));
