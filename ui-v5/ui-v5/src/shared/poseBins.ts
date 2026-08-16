/**
 * Единый справочник бинов ракурса.
 *
 * Инвариант 1 AGENTS.md: девять канонических бинов. До появления этого модуля
 * в коде существовало три расходящихся справочника — в TimelinePage (9 бинов),
 * в OverviewPage (8 бинов, без обоих профилей, с выдуманным `unknown`) и в
 * TopBar (`id.replaceAll("_", " ")`). Любое расхождение здесь означает, что
 * один и тот же кадр подписан на разных экранах по-разному.
 */
export interface PoseBin {
  id: string;
  /** Короткая подпись для плотных элементов: таймлайн, чипы. */
  label: string;
  /** Развёрнутая подпись для карточек и таблиц. */
  fullLabel: string;
  /** Порядок отображения: от левого профиля к правому. */
  order: number;
}

export const POSE_BINS: readonly PoseBin[] = [
  { id: "left_profile", label: "Лево · профиль", fullLabel: "Левый профиль", order: 0 },
  { id: "left_deep", label: "Лево · глубокий", fullLabel: "Левый глубокий", order: 1 },
  { id: "left_mid", label: "Лево · средний", fullLabel: "Левый средний", order: 2 },
  { id: "left_light", label: "Лево · лёгкий", fullLabel: "Левый лёгкий", order: 3 },
  { id: "frontal", label: "Фронт", fullLabel: "Фронтальный", order: 4 },
  { id: "right_light", label: "Право · лёгкий", fullLabel: "Правый лёгкий", order: 5 },
  { id: "right_mid", label: "Право · средний", fullLabel: "Правый средний", order: 6 },
  { id: "right_deep", label: "Право · глубокий", fullLabel: "Правый глубокий", order: 7 },
  { id: "right_profile", label: "Право · профиль", fullLabel: "Правый профиль", order: 8 },
] as const;

const BY_ID = new Map(POSE_BINS.map((bin) => [bin.id, bin]));

export const POSE_BIN_IDS: readonly string[] = POSE_BINS.map((bin) => bin.id);

export function poseBin(id: string): PoseBin | undefined {
  return BY_ID.get(id);
}

/**
 * Подпись бина. Неизвестный идентификатор возвращается как есть — это честнее,
 * чем подставлять «Не классифицирован» и скрывать расхождение с backend.
 */
export function poseLabel(id: string): string {
  return BY_ID.get(id)?.label ?? id;
}

export function poseFullLabel(id: string): string {
  return BY_ID.get(id)?.fullLabel ?? id;
}

/** Известен ли бин каноническому справочнику. */
export function isKnownPoseBin(id: string): boolean {
  return BY_ID.has(id);
}

/** Сортировка идентификаторов бинов в анатомическом порядке. */
export function sortPoseBins(ids: readonly string[]): string[] {
  return [...ids].sort((a, b) => {
    const oa = BY_ID.get(a)?.order ?? Number.MAX_SAFE_INTEGER;
    const ob = BY_ID.get(b)?.order ?? Number.MAX_SAFE_INTEGER;
    return oa === ob ? a.localeCompare(b) : oa - ob;
  });
}
