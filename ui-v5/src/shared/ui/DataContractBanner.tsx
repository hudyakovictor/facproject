import { ShieldAlert } from "lucide-react";
import styles from "./banners.module.css";

/**
 * Сводка соблюдения контракта полей, полученная от backend.
 *
 * `app6/api/ui_fields.py` проверяет каждую строку через `validate_ui_row` и
 * возвращает `ui_fields_complete_photo_count` и `ui_fields_violations_by_field`.
 * Раньше интерфейс эти поля игнорировал и вместо них печатал захардкоженную
 * строку «Недоступные поля не подменяются: boneScore/p0–p2», которая совпала с
 * реальностью случайно и начала бы врать при первом же изменении пайплайна.
 */
export function DataContractBanner({
  totalPhotos,
  completeCount,
  violationsByField,
  schema,
}: {
  totalPhotos: number;
  completeCount?: number;
  violationsByField?: Record<string, number>;
  schema?: string;
}) {
  const violations = Object.entries(violationsByField ?? {})
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a);

  if (completeCount === undefined && violations.length === 0) return null;

  const complete = completeCount ?? 0;
  const allComplete = violations.length === 0 && complete === totalPhotos;

  return (
    <div className={allComplete ? styles.contractOk : styles.contractWarn} role="status">
      <ShieldAlert className={styles.icon} aria-hidden="true" />
      <div className={styles.contractBody}>
        <div className={styles.contractTitle}>
          Полнота полей: {complete.toLocaleString("ru-RU")} из {totalPhotos.toLocaleString("ru-RU")} записей
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
        </p>
      </div>
    </div>
  );
}
