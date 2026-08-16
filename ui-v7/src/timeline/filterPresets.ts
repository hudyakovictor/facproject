import { useTimelineStore } from './store';

/**
 * Filter presets for quick selection.
 * Predefined configurations for common analysis scenarios.
 */

export interface FilterPreset {
  id: string;
  label: string;
  description: string;
  apply: (store: ReturnType<typeof useTimelineStore.getState> & {
    setQualityThreshold: (v: number) => void;
    setSkinAuthenticityThreshold: (v: number) => void;
    setSiliconeProbThreshold: (v: number) => void;
    setShapeDifferenceThreshold: (v: number) => void;
    setFindingsMode: (v: boolean) => void;
    setPoseAngleThreshold: (v: number) => void;
  }) => void;
}

export const FILTER_PRESETS: FilterPreset[] = [
  {
    id: 'all',
    label: 'Все кадры',
    description: 'Без фильтров',
    apply: (store) => {
      store.setQualityThreshold(0);
      store.setSkinAuthenticityThreshold(0);
      store.setSiliconeProbThreshold(1);
      store.setShapeDifferenceThreshold(1);
      store.setFindingsMode(false);
      store.setPoseAngleThreshold(30);
    },
  },
  {
    id: 'high_quality',
    label: 'Высокое качество',
    description: 'Только качественные кадры (q > 0.7)',
    apply: (store) => {
      store.setQualityThreshold(0.7);
      store.setSkinAuthenticityThreshold(0);
      store.setSiliconeProbThreshold(1);
      store.setShapeDifferenceThreshold(1);
      store.setFindingsMode(false);
      store.setPoseAngleThreshold(30);
    },
  },
  {
    id: 'authentic_skin',
    label: 'Аутентичная кожа',
    description: 'Кадры с натуральной кожей',
    apply: (store) => {
      store.setQualityThreshold(0.3);
      store.setSkinAuthenticityThreshold(0.7);
      store.setSiliconeProbThreshold(0.2);
      store.setShapeDifferenceThreshold(1);
      store.setFindingsMode(false);
      store.setPoseAngleThreshold(30);
    },
  },
  {
    id: 'suspicious',
    label: 'Подозрительные',
    description: 'Признаки силикона или низкая аутентичность',
    apply: (store) => {
      store.setQualityThreshold(0);
      store.setSkinAuthenticityThreshold(0);
      store.setSiliconeProbThreshold(0.3);
      store.setShapeDifferenceThreshold(1);
      store.setFindingsMode(false);
      store.setPoseAngleThreshold(30);
    },
  },
  {
    id: 'shape_changes',
    label: 'Изменения формы',
    description: 'Значительные различия в форме лица',
    apply: (store) => {
      store.setQualityThreshold(0.3);
      store.setSkinAuthenticityThreshold(0);
      store.setSiliconeProbThreshold(1);
      store.setShapeDifferenceThreshold(0.4);
      store.setFindingsMode(false);
      store.setPoseAngleThreshold(30);
    },
  },
  {
    id: 'findings_only',
    label: 'Только находки',
    description: 'Кадры с обнаруженными аномалиями',
    apply: (store) => {
      store.setQualityThreshold(0);
      store.setSkinAuthenticityThreshold(0);
      store.setSiliconeProbThreshold(1);
      store.setShapeDifferenceThreshold(1);
      store.setFindingsMode(true);
      store.setPoseAngleThreshold(30);
    },
  },
  {
    id: 'strict_pose',
    label: 'Строгая поза',
    description: 'Точная поза для сравнения (±5°)',
    apply: (store) => {
      store.setQualityThreshold(0.5);
      store.setSkinAuthenticityThreshold(0);
      store.setSiliconeProbThreshold(1);
      store.setShapeDifferenceThreshold(1);
      store.setFindingsMode(false);
      store.setPoseAngleThreshold(5);
    },
  },
];

export function applyPreset(presetId: string): void {
  const store = useTimelineStore.getState();
  const preset = FILTER_PRESETS.find(p => p.id === presetId);
  if (preset) {
    preset.apply(store);
  }
}
