/**
 * Модель ручного контроля качества (§10.5) без React.
 *
 * Вынесено из компонента, чтобы решение эксперта можно было проверить тестом
 * без рендера, и чтобы правила «что считается заполненным отзывом» жили в
 * одном месте.
 */

export const DECISIONS = [
  { id: "approve", label: "Принять" },
  { id: "reject_reconstruction", label: "Отклонить реконструкцию" },
  { id: "needs_recrop", label: "Требуется перекадрирование" },
  { id: "wrong_face", label: "Не то лицо" },
  { id: "invalid_source", label: "Недостоверный источник или дата" },
] as const;

export type DecisionId = (typeof DECISIONS)[number]["id"];

export interface ReviewRecord {
  schema: "deeputin-ui-review-v1";
  photo_id: string;
  decision: DecisionId;
  comment: string;
  reviewer: string;
  created_at: string;
  creates_issue: boolean;
}

export function buildReview(input: {
  photoId: string;
  decision: DecisionId;
  comment: string;
  reviewer: string;
  createsIssue: boolean;
  now?: Date;
}): ReviewRecord {
  return {
    schema: "deeputin-ui-review-v1",
    photo_id: input.photoId,
    decision: input.decision,
    comment: input.comment.trim(),
    reviewer: input.reviewer.trim(),
    created_at: (input.now ?? new Date()).toISOString(),
    creates_issue: input.createsIssue,
  };
}

/**
 * Решение, отличное от «принять», без комментария бессмысленно: через месяц
 * «отклонить реконструкцию» без причины неотличимо от случайного нажатия.
 */
export function reviewBlockers(input: {
  decision: DecisionId | null;
  comment: string;
  reviewer: string;
}): string[] {
  const problems: string[] = [];
  if (input.decision === null) problems.push("не выбрано решение");
  if (input.reviewer.trim() === "") problems.push("не указан рецензент");
  if (input.decision !== null && input.decision !== "approve" && input.comment.trim() === "") {
    problems.push("отклонение требует комментария с причиной");
  }
  return problems;
}

