import { Check, CircleSlash, Minus } from "lucide-react";
import { useCalibrationHealth, useTimeline } from "../../shared/api/queries";
import { resolveStage } from "../../shared/stage";
import styles from "./pipelineChips.module.css";

type ChipState = "done" | "absent" | "unknown";

/**
 * Чипы состояния пайплайна (§4.2 ТЗ): Stage 1 → Stage 2 → Калибровка → Stage 3.
 *
 * Состояние выводится только из того, что действительно вернул backend. Там,
 * где API не даёт ответа, чип показывает «н/д», а не зелёную галочку: ложная
 * отметка «готово» на стадии, которая не выполнялась, — это то же самое
 * приукрашивание данных, что и подстановка демонстрационных значений.
 */
function chipIcon(state: ChipState) {
  if (state === "done") return <Check className={styles.icon} aria-hidden="true" />;
  if (state === "absent") return <CircleSlash className={styles.icon} aria-hidden="true" />;
  return <Minus className={styles.icon} aria-hidden="true" />;
}

function Chip({ label, state, title }: { label: string; state: ChipState; title: string }) {
  return (
    <span className={`${styles.chip} ${styles[state]}`} title={title}>
      {chipIcon(state)}
      {label}
    </span>
  );
}

export function PipelineChips() {
  const timeline = useTimeline();
  const calibration = useCalibrationHealth();

  if (timeline.isLoading) return null;

  const stage = resolveStage(timeline.data);
  const photoCount = timeline.data?.photos.length ?? 0;

  const stage1: ChipState = photoCount > 0 ? "done" : timeline.error ? "unknown" : "absent";
  const stage2: ChipState = timeline.error ? "unknown" : stage === "stage2" ? "done" : "absent";

  const calibrationState: ChipState = calibration.isLoading
    ? "unknown"
    : calibration.error
      ? "unknown"
      : (calibration.data?.total_records ?? 0) > 0
        ? "done"
        : "absent";

  /**
   * Stage 3 не представлен ни одним полем в трёх доступных ответах. Пока
   * backend не отдаёт его статус (B-05 плана), честное значение — «н/д».
   */
  const stage3: ChipState = "unknown";

  return (
    <span className={styles.row} aria-label="Состояние пайплайна">
      <Chip
        label="Stage 1"
        state={stage1}
        title={
          stage1 === "done"
            ? `Инвентарь загружен: ${photoCount} кадров`
            : "Инвентарь Stage 1 недоступен"
        }
      />
      <Chip
        label="Stage 2"
        state={stage2}
        title={
          stage2 === "done"
            ? "Ответ содержит сравнительные метрики Stage 2"
            : "Stage 2 не выполнен: сравнительных метрик в ответе нет"
        }
      />
      <Chip
        label="Калибровка"
        state={calibrationState}
        title={
          calibrationState === "done"
            ? `Записей калибровки: ${calibration.data?.total_records}`
            : "Данные калибровки недоступны"
        }
      />
      <Chip label="Stage 3" state={stage3} title="API не сообщает статус Stage 3" />
    </span>
  );
}
