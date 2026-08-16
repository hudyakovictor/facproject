import { AlertCircle, CircleDot, Eye, EyeOff, Loader2 } from "lucide-react";
import { useTimeline } from "../../shared/api/queries";
import { countFindings } from "../../shared/findings";
import { resolveStage, stageLabel } from "../../shared/stage";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { poseLabel } from "../../shared/poseBins";
import styles from "./statusBar.module.css";

/**
 * Нижняя status bar по §4.3 ТЗ.
 *
 * Несёт обязательную маркировку «ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ» (правило 20
 * AGENTS.md), которой раньше не было ни на одном из пятнадцати продуктовых
 * экранов, и сводку контекста: стадия пайплайна, режим источника, активный
 * ракурс, число находок, состояние backend.
 */
export function StatusBar() {
  const timeline = useTimeline();
  const { activePose, multiPose, blindMode, setBlindMode } = useAnalysisStore();

  const photos = timeline.data?.photos ?? [];
  const stage = resolveStage(timeline.data);
  const findings = photos.length ? countFindings(photos) : null;

  const connection = timeline.isLoading
    ? { icon: <Loader2 className={`${styles.icon} ${styles.spin}`} />, text: "Соединение…", tone: styles.pending }
    : timeline.error
      ? { icon: <AlertCircle className={styles.icon} />, text: "Backend недоступен", tone: styles.error }
      : { icon: <CircleDot className={styles.icon} />, text: "Backend доступен", tone: styles.ok };

  return (
    <footer className={styles.bar} role="contentinfo">
      <span className={styles.marker}>ОТОБРАЖЕНИЕ ДАННЫХ · НЕ ВЕРДИКТ</span>

      <span className={styles.divider} aria-hidden="true" />
      <span className={styles.item}>Стадия: {stageLabel(stage)}</span>

      {timeline.data?.source_mode && (
        <span className={styles.item}>Источник: {timeline.data.source_mode}</span>
      )}

      <span className={styles.item}>
        Ракурс: {multiPose ? "все бины" : poseLabel(activePose)}
      </span>

      {findings !== null && (
        <span className={styles.item}>Находки: {findings.toLocaleString("ru-RU")}</span>
      )}

      {photos.length > 0 && (
        <span className={styles.item}>Кадров: {photos.length.toLocaleString("ru-RU")}</span>
      )}

      <span className={styles.spacer} />

      <button
        type="button"
        onClick={() => setBlindMode(!blindMode)}
        aria-pressed={blindMode}
        className={blindMode ? styles.blindOn : styles.blindOff}
        title="Слепой режим скрывает идентифицирующие подписи для независимой оценки"
      >
        {blindMode ? <EyeOff className={styles.icon} /> : <Eye className={styles.icon} />}
        {blindMode ? "Слепой режим" : "Обычный режим"}
      </button>

      <span className={`${styles.item} ${connection.tone}`}>
        {connection.icon}
        {connection.text}
      </span>
    </footer>
  );
}
