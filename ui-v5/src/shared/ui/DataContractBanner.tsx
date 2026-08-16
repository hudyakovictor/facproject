import { ShieldAlert } from "lucide-react";
import { collectContractIssues } from "../api/contract";
import type { ResearchPhoto } from "../researchApi";
import styles from "./banners.module.css";

/**
 * Сводка соблюдения контракта полей.
 *
 * `app6/api/ui_fields.py` проверяет каждую строку через `validate_ui_row` и
 * возвращает `ui_fields_complete_photo_count` и `ui_fields_violations_by_field`.
 * Раньше интерфейс эти поля игнорировал и вместо них печатал захардкоженную
 * строку «Недоступные поля не подменяются: boneScore/p0–p2», которая совпала с
 * реальностью случайно и начала бы врать при первом же изменении пайплайна.
 *
 * Если сводки в ответе нет (её не формирует `stage1_timeline.py`), проверка
 * повторяется на клиенте по зеркалу `REQUIRED_UI_FIELDS`, и об этом сказано
 * прямо: пользователь должен знать, кто именно считал.
 */
export function DataContractBanner({
  photos,
  totalPhotos,
  completeCount,
  violationsByField,
  schema,
}: {
  /** Записи для локальной проверки, когда backend сводку не прислал. */
  photos?: readonly ResearchPhoto[];
  totalPhotos: number;
  completeCount?: number;
  violationsByField?: Record<string, number>;
  schema?: string;
}) {
  const issues = collectContractIssues(photos ?? [], { completeCount, violationsByField });

  const violations = Object.entries(issues.violationsByField)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a);

  if (totalPhotos === 0) return null;
  if (issues.completeCount === totalPhotos && violations.length === 0) {
    return null;
  }

  const allComplete = violations.length === 0 && issues.completeCount === totalPhotos;

  return (
    <div className={allComplete ? styles.contractOk : styles.contractWarn} role="status">
      <ShieldAlert className={styles.icon} aria-hidden="true" />
      <div className={styles.contractBody}>
        <div className={styles.contractTitle}>
          Полнота полей: {issues.completeCount.toLocaleString("ru-RU")} из{" "}
          {totalPhotos.toLocaleString("ru-RU")} записей
          {schema && <span className={styles.schema}> · схема {schema}</span>}
        </div>
        {violations.length > 0 && (
          <ul className={styles.violationList}>
            {violations.map(([field, count]) => (
              <li key={field} className={styles.violation}>
                <code>{field}</code>
                <span>недоступно у {count.toLocaleString("ru-RU")}</span>
              </li>
            ))}
          </ul>
        )}
        <p className={styles.contractNote}>
          Недоступные значения показываются как «н/д» и не заменяются нулями.
          {issues.computedLocally &&
            " Сводка посчитана в интерфейсе: ответ API её не содержал."}
        </p>
      </div>
    </div>
  );
}
