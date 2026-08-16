import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "../../shared/ui/primitives";
import { consoleLogger } from "../../shared/logger";
import { DECISIONS, buildReview, reviewBlockers, type DecisionId } from "./review";
import styles from "./inspector.module.css";

/**
 * Ручной контроль качества кадра (§10.5).
 *
 * Спека заканчивается требованием «no silent mutation Stage 1»: вердикт
 * эксперта не должен менять артефакты извлечения. Эндпоинта для сохранения
 * отзыва в API нет (задача B-01), поэтому форма ничего не отправляет — она
 * собирает решение в файл `{id}.review.json` рядом с исследователем.
 *
 * 🚨 WARNING: кнопки «принять»/«отклонить» намеренно не пишут в Stage 1 даже
 * когда эндпоинт появится: отзыв — отдельный слой поверх неизменяемого
 * результата извлечения. Иначе повторный прогон молча затрёт решение эксперта,
 * а расхождение обнаружится только в отчёте.
 */

export function ManualQA({ photoId }: { photoId: string }) {
  const [decision, setDecision] = useState<DecisionId | null>(null);
  const [comment, setComment] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [createsIssue, setCreatesIssue] = useState(false);
  const blockers = reviewBlockers({ decision, comment, reviewer });

  const save = () => {
    if (decision === null || blockers.length > 0) return;
    const record = buildReview({ photoId, decision, comment, reviewer, createsIssue });
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${photoId}.review.json`;
    link.click();
    URL.revokeObjectURL(url);
    consoleLogger.addLog(
      "INFO",
      "inspector",
      `Отзыв по кадру ${photoId} сохранён в файл`,
      `решение: ${decision}${createsIssue ? " · создать задачу" : ""}`,
    );
  };

  return (
    <section className={styles.panel} aria-label="Ручной контроль качества">
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>РУЧНОЙ КОНТРОЛЬ КАЧЕСТВА</span>
      </div>

      <div className={styles.qaDecisions} role="radiogroup" aria-label="Решение">
        {DECISIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={decision === item.id}
            onClick={() => setDecision(item.id)}
            className={styles.layerButton}
          >
            {item.label}
          </button>
        ))}
      </div>

      <label className={styles.qaField}>
        Рецензент
        <input
          type="text"
          value={reviewer}
          onChange={(event) => setReviewer(event.target.value)}
          placeholder="кто принял решение"
        />
      </label>

      <label className={styles.qaField}>
        Комментарий
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          rows={3}
          placeholder="причина решения, наблюдения, что проверить повторно"
        />
      </label>

      <label className={styles.qaCheckbox}>
        <input
          type="checkbox"
          checked={createsIssue}
          onChange={(event) => setCreatesIssue(event.target.checked)}
        />
        Создать задачу по кадру
      </label>

      {blockers.length > 0 && (
        <p className={styles.warn}>Не хватает: {blockers.join(", ")}.</p>
      )}

      <div className={styles.controlRow}>
        <Button size="sm" onClick={save} disabled={blockers.length > 0}>
          <Download className="h-3.5 w-3.5" /> Сохранить отзыв в файл
        </Button>
      </div>

      <p className={styles.layerNote}>
        Отзыв не меняет результат Stage 1 и не отправляется на сервер: эндпоинта
        рецензирования в API нет (задача B-01). Файл сохраняется локально и
        прикладывается к прогону вручную.
      </p>
    </section>
  );
}
