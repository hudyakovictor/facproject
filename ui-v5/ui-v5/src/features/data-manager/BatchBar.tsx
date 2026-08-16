import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import type { ResearchPhoto } from "../../shared/researchApi";
import { useDeletePhotoDerivatives } from "../../shared/api/queries";
import { describeError } from "../../shared/ui/errorDetail";
import { consoleLogger } from "../../shared/logger";
import { buildCsv } from "./exportRows";
import styles from "./dataManager.module.css";

/**
 * Пакетные операции над выбранными кадрами (§7.6 ТЗ).
 *
 * Раздел требует, чтобы удаление показывало зависимости, не трогало
 * неизменяемые артефакты Stage 1 без отдельного порядка, требовало
 * подтверждения вводом и создавало запись в журнале. Здесь выполнимо не всё:
 * зависимостей (какие пары и отчёты ссылаются на кадр) backend не отдаёт.
 *
 * Поэтому предупреждение говорит именно то, что известно: удаляются
 * производные Stage 1, исходный файл остаётся, а список зависимых пар и
 * отчётов интерфейс проверить не может. Умолчать об этом значило бы позволить
 * оператору считать операцию безопасной, не зная её последствий.
 */

export interface BatchBarProps {
  selected: readonly ResearchPhoto[];
  visibleColumns: readonly string[];
  onClearSelection: () => void;
}

const CONFIRM_WORD = "УДАЛИТЬ";

export function BatchBar({ selected, visibleColumns, onClearSelection }: BatchBarProps) {
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const remove = useDeletePhotoDerivatives();

  if (selected.length === 0) return null;

  const exportSelection = () => {
    const csv = buildCsv(selected, visibleColumns);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `selection-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    consoleLogger.addLog(
      "INFO",
      "DATA",
      `Экспорт выборки: ${selected.length} записей`,
      visibleColumns.join(", "),
    );
  };

  const runDelete = async () => {
    let ok = 0;
    const failures: string[] = [];
    for (const photo of selected) {
      try {
        await remove.mutateAsync(photo.id);
        ok += 1;
      } catch (error) {
        failures.push(`${photo.id}: ${describeError(error).message}`);
      }
    }
    // Журнал операции обязателен: пакетное действие должно оставлять след.
    consoleLogger.addLog(
      failures.length ? "ERROR" : "INFO",
      "DATA",
      `Удаление производных Stage 1: успешно ${ok}, отказов ${failures.length}`,
      failures.join("\n") || "—",
    );
    setDone(
      failures.length
        ? `Удалено ${ok}, отказов ${failures.length}. ${failures[0]}`
        : `Удалены производные Stage 1 для ${ok} кадров. Исходные файлы не затронуты.`,
    );
    setConfirming(false);
    setTyped("");
    onClearSelection();
  };

  return (
    <div className={styles.batchBar} role="region" aria-label="Действия над выборкой">
      <span className={styles.batchCount}>Выбрано: {selected.length}</span>

      <button type="button" className={styles.linkButton} onClick={exportSelection}>
        Экспорт CSV
      </button>

      <button
        type="button"
        className={styles.dangerButton}
        onClick={() => setConfirming(true)}
      >
        Удалить производные Stage 1
      </button>

      <button type="button" className={styles.linkButton} onClick={onClearSelection}>
        Снять выбор
      </button>

      {done && (
        <p className={styles.batchDone} role="status">
          {done}
        </p>
      )}

      {confirming && (
        <div className={styles.confirmBox} role="alertdialog" aria-label="Подтверждение удаления">
          <p className={styles.confirmTitle}>
            <AlertTriangle className="mr-1 inline h-4 w-4" aria-hidden="true" />
            Будут удалены производные Stage 1 для {selected.length} кадров
          </p>
          <ul className={styles.confirmList}>
            <li>Исходные файлы изображений backend не трогает.</li>
            <li>
              Удаляются каталоги результатов извлечения: меши, ландмарки, маски,
              текстуры.
            </li>
            <li>
              Зависимости (пары, прогоны и отчёты, ссылающиеся на эти кадры) API не
              отдаёт — интерфейс не может показать, что именно перестанет
              воспроизводиться.
            </li>
            <li>Действие необратимо: повторное извлечение требует запуска задания.</li>
          </ul>
          <label className={styles.confirmField}>
            Введите <b>{CONFIRM_WORD}</b> для подтверждения
            <input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              aria-label={`Введите ${CONFIRM_WORD} для подтверждения`}
            />
          </label>
          <div className={styles.confirmActions}>
            <button
              type="button"
              className={styles.dangerButton}
              disabled={typed.trim() !== CONFIRM_WORD || remove.isPending}
              onClick={() => void runDelete()}
            >
              {remove.isPending ? "Удаление…" : "Подтвердить удаление"}
            </button>
            <button
              type="button"
              className={styles.linkButton}
              onClick={() => {
                setConfirming(false);
                setTyped("");
              }}
            >
              Отмена
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
