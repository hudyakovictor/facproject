/**
 * Pose bin definitions for the timeline.
 */

export interface PoseBin {
  id: string;
  label: string;
  fullLabel: string;
  order: number;
}

export const POSE_BINS: readonly PoseBin[] = [
  { id: 'left_profile', label: 'Лев · проф', fullLabel: 'Левый профиль', order: 0 },
  { id: 'left_deep', label: 'Лев · глуб', fullLabel: 'Левый глубокий', order: 1 },
  { id: 'left_mid', label: 'Лев · сред', fullLabel: 'Левый средний', order: 2 },
  { id: 'left_light', label: 'Лев · лёгк', fullLabel: 'Левый лёгкий', order: 3 },
  { id: 'frontal', label: 'Фронт', fullLabel: 'Фронтальный', order: 4 },
  { id: 'right_light', label: 'Прав · лёгк', fullLabel: 'Правый лёгкий', order: 5 },
  { id: 'right_mid', label: 'Прав · сред', fullLabel: 'Правый средний', order: 6 },
  { id: 'right_deep', label: 'Прав · глуб', fullLabel: 'Правый глубокий', order: 7 },
  { id: 'right_profile', label: 'Прав · проф', fullLabel: 'Правый профиль', order: 8 },
] as const;

export const POSE_BIN_IDS: readonly string[] = POSE_BINS.map(bin => bin.id);

export function poseBin(id: string): PoseBin | undefined {
  return POSE_BINS.find(bin => bin.id === id);
}

export function poseLabel(id: string): string {
  return POSE_BINS.find(bin => bin.id === id)?.label ?? id;
}

export function poseFullLabel(id: string): string {
  return POSE_BINS.find(bin => bin.id === id)?.fullLabel ?? id;
}
