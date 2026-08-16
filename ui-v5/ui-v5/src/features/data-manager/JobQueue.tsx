import { useState } from "react";
import { Play, Ban } from "lucide-react";
import { useCancelJob, useJobs, useSubmitJob } from "../../shared/api/queries";
import { describeError } from "../../shared/ui/errorDetail";
import styles from "./dataManager.module.css";

/**
 * Очередь извлечения (§7.7 ТЗ) поверх `/api/v1/jobs`.
 *
 * Четыре эндпоинта заданий существовали в backend и не вызывались ни разу.
 *
 * Отдельного внимания требует статус `blocked`: backend возвращает его, когда
 * весов 3DDFA_V3 или torch/cv2 в окружении нет, — задание не выполнено и не
 * упало, оно невозможно. Показывать его как ошибку значит предлагать «повторить»
 * то, что не заработает; показывать как успех — лгать. Поэтому у него
 * собственное оформление и текст с причиной.
 */

const STATUS_LABEL: Record<string, string> = {
  queued: "в очереди",
  running: "выполняется",
  complete: "завершено",
  blocked: "невозможно",
  failed: "сбой",
  cancelled: "отменено",
};

function statusClass(status: string): string {
  if (status === "complete") return styles.jobOk;
  if (status === "failed") return styles.jobFail;
  if (status === "blocked") return styles.jobBlocked;
  if (status === "running" || status === "queued") return styles.jobActive;
  return styles.jobIdle;
}

export function JobQueue() {
  const jobs = useJobs();
  const submit = useSubmitJob();
  const cancel = useCancelJob();
  const [limit, setLimit] = useState(10);
  const [expanded, setExpanded] = useState<string | null>(null);

  const list = jobs.data?.jobs ?? [];

  return (
    <section className={styles.queue}>
      <header className={styles.queueHead}>
        <h3 className={styles.panelTitle}>Очередь извлечения</h3>
        <label className={styles.queueLimit}>
          Пробный прогон, кадров
          <input
            type="number"
            min={1}
            max={1000}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value) || 1)}
          />
        </label>
        <button
          type="button"
          className={styles.primaryButton}
          disabled={submit.isPending}
          onClick={() => submit.mutate({ kind: "extract", limit })}
        >
          <Play className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />
          {submit.isPending ? "Отправка…" : "Запустить извлечение"}
        </button>
      </header>

      <p className={styles.queueNote}>
        Извлечение выполняется backend отдельным заданием и записывает результат в
        каталог Stage 1. Интерфейс не выполняет расчёт и не может завершить его сам.
      </p>

      {submit.isError && (
        <p className={styles.queueError} role="alert">
          Не удалось поставить задание: {describeError(submit.error).message}
        </p>
      )}
      {cancel.isError && (
        <p className={styles.queueError} role="alert">
          Не удалось отменить: {describeError(cancel.error).message}
        </p>
      )}

      {jobs.isLoading && <p className={styles.queueNote}>Загрузка очереди…</p>}
      {jobs.isError && (
        <p className={styles.queueError} role="alert">
          Очередь недоступна: {describeError(jobs.error).message}
        </p>
      )}

      {!jobs.isLoading && !jobs.isError && list.length === 0 && (
        <p className={styles.queueNote}>Заданий нет.</p>
      )}

      <ul className={styles.jobList}>
        {list.map((job) => {
          const total = job.progress?.total ?? 0;
          const done = job.progress?.done ?? 0;
          const percent = total > 0 ? Math.round((done / total) * 100) : null;
          const active = job.status === "queued" || job.status === "running";
          return (
            <li key={job.id} className={styles.jobItem}>
              <div className={styles.jobRow}>
                <span className={`${styles.jobStatus} ${statusClass(job.status ?? "")}`}>
                  {job.status ? STATUS_LABEL[job.status] ?? job.status : "—"}
                </span>
                <span className={styles.jobKind}>{job.kind ?? ""}</span>
                <span className={styles.jobProgress}>
                  {/* Процент показывается только когда известен размер работы. */}
                  {total > 0 ? `${done} из ${total}${percent === null ? "" : ` · ${percent}%`}` : "объём неизвестен"}
                </span>
                <button
                  type="button"
                  className={styles.linkButton}
                  onClick={() => setExpanded(expanded === job.id ? null : job.id)}
                  aria-expanded={expanded === job.id}
                >
                  журнал
                </button>
                {active && (
                  <button
                    type="button"
                    className={styles.linkButton}
                    onClick={() => cancel.mutate(job.id)}
                  >
                    <Ban className="mr-1 inline h-3 w-3" aria-hidden="true" />
                    отменить
                  </button>
                )}
              </div>

              {job.status === "blocked" && (
                <p className={styles.jobBlockedNote}>
                  Задание невозможно выполнить в этом окружении:{" "}
                  {job.error ?? "backend не сообщил причину"}. Это не сбой расчёта —
                  расчёт не запускался.
                </p>
              )}
              {job.status === "failed" && job.error && (
                <p className={styles.queueError}>{job.error}</p>
              )}

              {expanded === job.id && (
                <pre className={styles.jobLog}>
                  {job.logs.length > 0 ? job.logs.join("\n") : "Записей нет."}
                </pre>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
