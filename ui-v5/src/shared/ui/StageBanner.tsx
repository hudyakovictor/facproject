import { AlertTriangle } from "lucide-react";
import { isStage2, stageDescription, type AnalysisStage } from "../stage";
import styles from "./banners.module.css";

/**
 * Плашка о стадии, из которой получены данные.
 *
 * Показывается всегда, когда данные пришли не из Stage 2: пользователь должен
 * видеть, что сравнительных метрик в этом режиме не существует, а не догадываться
 * об этом по прочеркам в таблице.
 *
 * Текст берётся из поля `note` ответа API, если оно есть: backend формулирует
 * ограничение точнее, чем захардкоженная в интерфейсе строка, и при изменении
 * пайплайна текст обновится сам.
 */
export function StageBanner({ stage, note }: { stage: AnalysisStage; note?: string }) {
  if (isStage2(stage)) return null;
  return (
    <div className={styles.stageBanner} role="status">
      <AlertTriangle className={styles.icon} aria-hidden="true" />
      <div>
        <div className={styles.stageTitle}>Данные Stage 1 — инвентарь кадров</div>
        <p className={styles.stageText}>{note?.trim() || stageDescription(stage)}</p>
      </div>
    </div>
  );
}
