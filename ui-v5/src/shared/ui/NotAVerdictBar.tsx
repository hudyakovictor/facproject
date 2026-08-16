import styles from "./notAVerdict.module.css";

/**
 * Постоянная маркировка «ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ».
 *
 * Правило 20 AGENTS.md требует, чтобы эта отметка была видна всегда, а не
 * появлялась на отдельных экранах. До этого она встречалась ровно один раз —
 * в витрине дизайн-системы, и отсутствовала на всех пятнадцати продуктовых
 * экранах. Это нарушение не косметическое: инструмент судебной экспертизы не
 * имеет права выглядеть как источник заключения.
 *
 * В Фазе 2 полоса станет частью полноценной нижней status bar (§4.3 ТЗ);
 * маркировка переедет туда без изменения смысла.
 */
export function NotAVerdictBar({
  sourceMode,
  stageLabel,
  findingCount,
}: {
  sourceMode?: string;
  stageLabel?: string;
  findingCount?: number;
}) {
  return (
    <div className={styles.bar} role="note">
      <span className={styles.marker}>ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ</span>
      <span className={styles.spacer} />
      {stageLabel && <span className={styles.item}>Стадия: {stageLabel}</span>}
      {sourceMode && <span className={styles.item}>Источник: {sourceMode}</span>}
      {findingCount !== undefined && (
        <span className={styles.item}>Находки: {findingCount.toLocaleString("ru-RU")}</span>
      )}
    </div>
  );
}
