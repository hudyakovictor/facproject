import type { ResearchPhoto } from "../researchApi";

/**
 * Клиентское зеркало контракта полей из `app6/api/ui_fields.py`.
 *
 * Backend проверяет каждую строку функцией `validate_ui_row` и присылает сводку
 * в `ui_fields_complete_photo_count` / `ui_fields_violations_by_field`. Но
 * сводка приходит не всегда: `stage1_timeline.py` её не формирует, а более
 * старый backend не знает о ней вовсе. Без собственной проверки интерфейс в
 * таком случае молча показывает «н/д» и не сообщает, что контракт нарушен.
 *
 * Список обязательных полей должен совпадать с `REQUIRED_UI_FIELDS`. При
 * расхождении честнее показать лишнее предупреждение, чем скрыть настоящее.
 */
export const REQUIRED_UI_FIELDS = [
  "id",
  "date",
  "t",
  "era",
  "bucket",
  "quality",
  "boneScore",
  "p0",
  "p1",
  "p2",
] as const;

export type RequiredUiField = (typeof REQUIRED_UI_FIELDS)[number];

export interface ContractIssues {
  /** Сколько записей содержат все обязательные поля. */
  completeCount: number;
  /** Сколько записей лишены каждого конкретного поля. */
  violationsByField: Record<string, number>;
  /** Проверка выполнена клиентом, потому что backend сводку не прислал. */
  computedLocally: boolean;
}

/**
 * Отсутствующие обязательные поля одной записи.
 *
 * Семантика повторяет `validate_ui_row`: значимо именно отсутствие значения
 * (`null`/`undefined`), а не его величина. Ноль — законная величина метрики и
 * нарушением контракта не является.
 */
export function missingFields(photo: ResearchPhoto): RequiredUiField[] {
  return REQUIRED_UI_FIELDS.filter((field) => {
    const value = (photo as unknown as Record<string, unknown>)[field];
    return value === null || value === undefined || value === "";
  });
}

/**
 * Сводка по всему ответу. Если backend уже прислал свою, она имеет приоритет:
 * серверная проверка видит поля, которых в клиентском типе нет.
 */
export function collectContractIssues(
  photos: readonly ResearchPhoto[],
  serverSummary?: {
    completeCount?: number;
    violationsByField?: Record<string, number>;
  },
): ContractIssues {
  if (
    serverSummary?.completeCount !== undefined ||
    (serverSummary?.violationsByField &&
      Object.keys(serverSummary.violationsByField).length > 0)
  ) {
    return {
      completeCount: serverSummary.completeCount ?? 0,
      violationsByField: serverSummary.violationsByField ?? {},
      computedLocally: false,
    };
  }

  const violationsByField: Record<string, number> = {};
  let completeCount = 0;

  for (const photo of photos) {
    const missing = missingFields(photo);
    if (missing.length === 0) {
      completeCount += 1;
      continue;
    }
    for (const field of missing) {
      violationsByField[field] = (violationsByField[field] ?? 0) + 1;
    }
  }

  return { completeCount, violationsByField, computedLocally: true };
}
