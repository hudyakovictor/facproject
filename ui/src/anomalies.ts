import type { IconName } from "./components/Icon";
import type { Photo } from "./data";

/** Уровень критичности флага. Определяет цвет и поведение маркера. */
export type Severity = "critical" | "high" | "medium" | "low" | "quality";

export const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "#ff3b30",
  high: "#dd6974",
  medium: "#fdab43",
  low: "#e8af34",
  // `quality` — НЕ аномалия личности, а ограничение применимости кадра
  // (плохая видимость, активная мимика). Нейтральный цвет: показывать такое
  // красным наравне с подменой личности значило бы раздувать тревогу и
  // обесценивать настоящие флаги (`app6/AGENTS.md`: excluded ≠ аномалия).
  quality: "#5591c7",
};

/** Порядок сортировки: критичное первым. */
export const SEVERITY_RANK: Record<Severity, number> = {
  critical: 0, high: 1, medium: 2, low: 3, quality: 4,
};

export interface AnomalyKind {
  id: string;
  icon: IconName;
  severity: Severity;
  /** Ключ короткой подписи в i18n. */
  labelKey: string;
  /** Ключ объяснения «почему сработал флаг» в i18n. */
  reasonKey: string;
}

/** 🗂 Единый реестр типов аномалий.
 *
 * До этого на таймлайне отрисовывался ровно ОДИН флаг из шести
 * (`TEMPORAL_IMPOSSIBILITY`), а остальные существовали только как строка в
 * тултипе. Реестр задаёт для каждого типа иконку, критичность и объяснение,
 * чтобы аномалии были различимы визуально, а не только по коду.
 *
 * Порядок ключей соответствует `ALL_FLAGS` в App.tsx и флагам, которые
 * проставляет `research_timeline.py`.
 */
export const ANOMALY_KINDS: Record<string, AnomalyKind> = {
  TEMPORAL_IMPOSSIBILITY: {
    id: "TEMPORAL_IMPOSSIBILITY", icon: "alert-octagon", severity: "critical",
    labelKey: "anomTemporalImpossibility", reasonKey: "anomTemporalImpossibilityWhy",
  },
  IDENTITY_ANOMALY: {
    id: "IDENTITY_ANOMALY", icon: "alert-triangle", severity: "high",
    labelKey: "anomIdentity", reasonKey: "anomIdentityWhy",
  },
  RETURN_TO_BASELINE: {
    id: "RETURN_TO_BASELINE", icon: "rotate", severity: "high",
    labelKey: "anomReturnToBaseline", reasonKey: "anomReturnToBaselineWhy",
  },
  IMPOSSIBLE_SHORT: {
    id: "IMPOSSIBLE_SHORT", icon: "clock", severity: "critical",
    labelKey: "anomImpossibleShort", reasonKey: "anomImpossibleShortWhy",
  },
  TEXTURE_SPIKE: {
    id: "TEXTURE_SPIKE", icon: "circle-dot", severity: "medium",
    labelKey: "anomTextureSpike", reasonKey: "anomTextureSpikeWhy",
  },
  TRANSITION: {
    id: "TRANSITION", icon: "swap", severity: "low",
    labelKey: "anomTransition", reasonKey: "anomTransitionWhy",
  },
  // --- Ограничения применимости кадра (не аномалии личности) ---
  LOW_VISIBILITY: {
    id: "LOW_VISIBILITY", icon: "eye-off", severity: "quality",
    labelKey: "anomLowVisibility", reasonKey: "anomLowVisibilityWhy",
  },
  EXPRESSION_ACTIVE: {
    id: "EXPRESSION_ACTIVE", icon: "radio", severity: "quality",
    labelKey: "anomExpressionActive", reasonKey: "anomExpressionActiveWhy",
  },
};

/** Флаги качества не являются аномалиями: они ограничивают применимость
 * кадра к анализу и не должны попадать в счётчик «аномальных кадров». */
export function isQualityFlag(kind: AnomalyKind): boolean {
  return kind.severity === "quality";
}

/** Неизвестный флаг не должен исчезать с экрана: показываем как «прочее». */
export function anomalyKind(flag: string): AnomalyKind {
  return ANOMALY_KINDS[flag] ?? {
    id: flag, icon: "info", severity: "low",
    labelKey: "anomUnknown", reasonKey: "anomUnknownWhy",
  };
}

/** Флаги фото, отсортированные по критичности. */
export function photoAnomalies(photo: Photo): AnomalyKind[] {
  return photo.flags
    .map(anomalyKind)
    .sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
}

/** Максимальная критичность фото; `null` — аномалий нет. */
export function topSeverity(photo: Photo): Severity | null {
  const kinds = photoAnomalies(photo);
  return kinds.length ? kinds[0].severity : null;
}

export interface AnomalyBucket {
  /** Индекс фото в общем массиве. */
  index: number;
  photo: Photo;
  kinds: AnomalyKind[];
  severity: Severity;
}

/** Все кадры с флагами — для дорожки аномалий, мини-карты и навигации. */
export function collectAnomalies(photos: Photo[], includeQuality = false): AnomalyBucket[] {
  const out: AnomalyBucket[] = [];
  photos.forEach((photo, index) => {
    const all = photoAnomalies(photo);
    const kinds = includeQuality ? all : all.filter(k => !isQualityFlag(k));
    if (!kinds.length) return;
    out.push({ index, photo, kinds, severity: kinds[0].severity });
  });
  return out;
}

/** Сводка по типам для легенды: сколько кадров каждого типа. */
export function anomalyCounts(photos: Photo[]): { kind: AnomalyKind; count: number }[] {
  const counts = new Map<string, number>();
  for (const photo of photos) {
    for (const flag of photo.flags) counts.set(flag, (counts.get(flag) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([flag, count]) => ({ kind: anomalyKind(flag), count }))
    .sort((a, b) =>
      SEVERITY_RANK[a.kind.severity] - SEVERITY_RANK[b.kind.severity] || b.count - a.count);
}

/** Ближайший кадр с аномалией в заданном направлении (для навигации). */
export function nextAnomalyIndex(
  buckets: AnomalyBucket[], from: number, direction: 1 | -1,
): number | null {
  if (!buckets.length) return null;
  if (direction === 1) {
    const found = buckets.find(b => b.index > from);
    return (found ?? buckets[0]).index;          // циклический переход
  }
  const before = buckets.filter(b => b.index < from);
  return (before.length ? before[before.length - 1] : buckets[buckets.length - 1]).index;
}
