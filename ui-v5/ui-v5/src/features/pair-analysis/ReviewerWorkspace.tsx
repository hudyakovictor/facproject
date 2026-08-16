import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "../../shared/ui/primitives";
import { consoleLogger } from "../../shared/logger";
import {
  ALTERNATIVES,
  PAIR_DECISIONS,
  buildPairReview,
  pairReviewBlockers,
  type PairDecisionId,
} from "./pairReview";
import styles from "./pair.module.css";

/**
 * Рабочее место рецензента пары (§11.10).
 *
 * Требования спеки: наблюдение, уверенность, проверенные альтернативы,
 * решение, запрос перекадрирования или проверки источника, второй рецензент,
 * разрешение разногласий, экспорт карточки пары.
 *
 * 🚨 WARNING: перечень решений намеренно не содержит «тот же человек» или
 * «разные люди». Пара кадров такого вывода не даёт ни при каких значениях
 * метрик — она даёт основание считать наблюдение кандидатом на изменение либо
 * признать его неубедительным. Формулировки взяты из словаря статусов Stage 2.
 */

export function ReviewerWorkspace({ photoA, photoB }: { photoA: string; photoB: string }) {
  const [decision, setDecision] = useState<PairDecisionId | null>(null);
  const [observation, setObservation] = useState("");
  const [confidence, setConfidence] = useState<"low" | "medium" | "high">("low");
  const [alternatives, setAlternatives] = useState<string[]>([]);
  const [reviewer, setReviewer] = useState("");
  const [secondReviewer, setSecondReviewer] = useState("");

  const blockers = pairReviewBlockers({ decision, observation, reviewer, alternatives });

  const toggleAlternative = (id: string) =>
    setAlternatives((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );

  const exportCard = () => {
    if (decision === null || blockers.length > 0) return;
    const record = buildPairReview({
      photoA,
      photoB,
      decision,
      observation,
      confidence,
      alternatives,
      reviewer,
      secondReviewer,
    });
    const blob = new Blob([JSON.stringify(record, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `pair_${photoA}__${photoB}.review.json`;
    link.click();
    URL.revokeObjectURL(url);
    consoleLogger.addLog(
      "INFO",
      "pair",
      `Карточка пары ${photoA} / ${photoB} выгружена`,
      `решение: ${decision} · уверенность: ${confidence}`,
    );
  };

  return (
    <section className={styles.panel} aria-label="Рабочее место рецензента">
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>РЕЦЕНЗИРОВАНИЕ ПАРЫ</span>
      </div>

      <div className={styles.modeBar} role="radiogroup" aria-label="Решение по паре">
        {PAIR_DECISIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={decision === item.id}
            onClick={() => setDecision(item.id)}
            className={styles.modeButton}
          >
            {item.label}
          </button>
        ))}
      </div>

      <label className={styles.field}>
        Наблюдение
        <textarea
          rows={3}
          value={observation}
          onChange={(event) => setObservation(event.target.value)}
          placeholder="что именно видно на кадрах и в метриках"
        />
      </label>

      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>Проверенные альтернативные объяснения</legend>
        <div className={styles.checkGrid}>
          {ALTERNATIVES.map((item) => (
            <label key={item.id} className={styles.checkboxRow}>
              <input
                type="checkbox"
                checked={alternatives.includes(item.id)}
                onChange={() => toggleAlternative(item.id)}
              />
              {item.label}
            </label>
          ))}
        </div>
      </fieldset>

      <div className={styles.rangeRow}>
        <label className={styles.field}>
          Уверенность
          <select
            value={confidence}
            onChange={(event) => setConfidence(event.target.value as "low" | "medium" | "high")}
          >
            <option value="low">низкая</option>
            <option value="medium">средняя</option>
            <option value="high">высокая</option>
          </select>
        </label>
        <label className={styles.field}>
          Рецензент
          <input type="text" value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
        </label>
        <label className={styles.field}>
          Второй рецензент
          <input
            type="text"
            value={secondReviewer}
            onChange={(event) => setSecondReviewer(event.target.value)}
            placeholder="необязательно"
          />
        </label>
      </div>

      {blockers.length > 0 && <p className={styles.warn}>Не хватает: {blockers.join(", ")}.</p>}

      <div className={styles.sliderRow}>
        <Button size="sm" onClick={exportCard} disabled={blockers.length > 0}>
          <Download className="h-3.5 w-3.5" /> Выгрузить карточку пары
        </Button>
      </div>

      <p className={styles.note}>
        Решение не отправляется на сервер: эндпоинта рецензирования пар в API нет
        (задача B-01). В списке решений нет «тот же человек» и «разные люди» —
        пара кадров такого вывода не даёт.
      </p>
    </section>
  );
}
