/**
 * Стадия анализа, из которой получены данные.
 *
 * `/api/v1/timeline` двухрежимный: при наличии Stage 2 отдаёт полные
 * сравнительные метрики, иначе — инвентарь Stage 1 (`stage1_timeline.py`).
 * API честно сообщает режим в поле `analysis_stage`; интерфейс обязан это
 * поле читать и не подписывать инвентарь Stage 1 как результат Stage 2.
 */
export type AnalysisStage = "stage1_inventory" | "stage2";

/** Значение поля `analysisStage` на строке фотографии. */
export const STAGE1_PHOTO_MARKER = "stage1_inventory";

/** Схемы ответов из `app6/api`: по ним стадия определяется однозначно. */
export const STAGE1_TIMELINE_SCHEMA = "deeputin-api-stage1-inventory-v1.0";
export const STAGE2_TIMELINE_SCHEMA = "deeputin-api-research-timeline-v1.0";

/**
 * Определение стадии по ответу целиком.
 *
 * Полагаться на одно поле нельзя: `research_timeline.py` (полный Stage 2)
 * поле `analysis_stage` вообще не проставляет — его добавляет только
 * `stage1_timeline.py`. Наивный вывод «нет поля → Stage 1» превратил бы
 * настоящий Stage 2 в «инвентарь» и стал бы зеркальной версией той же ошибки,
 * из-за которой инвентарь Stage 1 подписывался как Stage 2.
 *
 * Поэтому опрашиваются три независимых признака, в порядке надёжности:
 * схема ответа → явное поле `analysis_stage` → маркер `analysisStage` на строках.
 */
export function resolveStage(response: {
  schema?: string;
  analysis_stage?: string;
  photos?: readonly { analysisStage?: string }[];
} | null | undefined): AnalysisStage {
  if (!response) return "stage1_inventory";

  if (response.schema === STAGE2_TIMELINE_SCHEMA) return "stage2";
  if (response.schema === STAGE1_TIMELINE_SCHEMA) return "stage1_inventory";

  const declared = response.analysis_stage;
  if (declared) return declared.startsWith("stage2") ? "stage2" : "stage1_inventory";

  const marker = response.photos?.find((photo) => photo.analysisStage)?.analysisStage;
  if (marker) return marker.startsWith("stage2") ? "stage2" : "stage1_inventory";

  return "stage1_inventory";
}

/** Нормализация одиночного строкового значения стадии. */
export function normalizeStage(value: string | null | undefined): AnalysisStage {
  return value?.startsWith("stage2") ? "stage2" : "stage1_inventory";
}

export function isStage2(stage: AnalysisStage): boolean {
  return stage === "stage2";
}

/** Короткая метка стадии для заголовков разделов. */
export function stageLabel(stage: AnalysisStage): string {
  return stage === "stage2" ? "STAGE 2" : "STAGE 1 · ИНВЕНТАРЬ";
}

/** Расшифровка того, какие данные доступны в этой стадии. */
export function stageDescription(stage: AnalysisStage): string {
  return stage === "stage2"
    ? "Сравнительные метрики Stage 2. Это отображение измерений, не вердикт."
    : "Инвентарь Stage 1: только съёмочные параметры кадра. Сравнительные метрики, вероятности и выводы появятся после Stage 2 и калибровки.";
}

/**
 * Доступны ли сравнительные метрики (boneScore, p0–p2, попарные сравнения).
 * В режиме Stage 1 они физически отсутствуют и должны показываться как «н/д».
 */
export function hasComparativeMetrics(stage: AnalysisStage): boolean {
  return stage === "stage2";
}
