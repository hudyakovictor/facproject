/**
 * Модель рецензирования пары (§11.10) без React.
 *
 * Вынесено из компонента, чтобы правила «что считается заполненной карточкой»
 * можно было проверить тестом без рендера. Перечень решений намеренно не
 * содержит суждений о личности — см. комментарий к `PAIR_DECISIONS`.
 */

export const PAIR_DECISIONS = [
  { id: "candidate", label: "Кандидат на изменение" },
  { id: "limited", label: "Ограниченно применимо" },
  { id: "inconclusive", label: "Неубедительно" },
  { id: "request_recrop", label: "Запросить перекадрирование" },
  { id: "request_source_check", label: "Запросить проверку источника" },
] as const;

export type PairDecisionId = (typeof PAIR_DECISIONS)[number]["id"];

export interface PairReview {
  schema: "deeputin-ui-pair-review-v1";
  photo_a: string;
  photo_b: string;
  decision: PairDecisionId;
  observation: string;
  confidence: "low" | "medium" | "high";
  alternatives_checked: string[];
  reviewer: string;
  second_reviewer: string | null;
  created_at: string;
}

/** Альтернативные объяснения, которые обязан рассмотреть рецензент. */
export const ALTERNATIVES: ReadonlyArray<{ id: string; label: string }> = [
  { id: "pose", label: "Различие ракурса" },
  { id: "expression", label: "Мимика" },
  { id: "lighting", label: "Освещение и экспозиция" },
  { id: "quality", label: "Качество съёмки и сжатие" },
  { id: "reconstruction", label: "Ошибка реконструкции" },
  { id: "aging", label: "Естественное старение" },
];

/**
 * Вывод «кандидат на изменение» без рассмотренных альтернатив недопустим:
 * ровно так шум ракурса и мимики превращается в «находку».
 */
export function pairReviewBlockers(input: {
  decision: PairDecisionId | null;
  observation: string;
  reviewer: string;
  alternatives: string[];
}): string[] {
  const problems: string[] = [];
  if (input.decision === null) problems.push("не выбрано решение");
  if (input.reviewer.trim() === "") problems.push("не указан рецензент");
  if (input.observation.trim().length < 10) {
    problems.push("наблюдение должно быть описано словами");
  }
  if (input.decision === "candidate" && input.alternatives.length < 2) {
    problems.push("для кандидата нужно отметить минимум две проверенные альтернативы");
  }
  return problems;
}

export function buildPairReview(input: {
  photoA: string;
  photoB: string;
  decision: PairDecisionId;
  observation: string;
  confidence: "low" | "medium" | "high";
  alternatives: string[];
  reviewer: string;
  secondReviewer: string;
  now?: Date;
}): PairReview {
  return {
    schema: "deeputin-ui-pair-review-v1",
    photo_a: input.photoA,
    photo_b: input.photoB,
    decision: input.decision,
    observation: input.observation.trim(),
    confidence: input.confidence,
    alternatives_checked: [...input.alternatives].sort(),
    reviewer: input.reviewer.trim(),
    second_reviewer: input.secondReviewer.trim() || null,
    created_at: (input.now ?? new Date()).toISOString(),
  };
}

