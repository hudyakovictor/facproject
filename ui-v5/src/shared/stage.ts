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

export function normalizeStage(value: string | null | undefined): AnalysisStage {
  return value === "stage2" ? "stage2" : "stage1_inventory";
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
