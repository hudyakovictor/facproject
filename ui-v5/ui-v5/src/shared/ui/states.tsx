import type { ReactNode } from "react";
import { AlertCircle, Inbox, Loader2, Lock } from "lucide-react";
import { Button } from "./primitives";
import { describeError } from "./errorDetail";
import styles from "./states.module.css";

/**
 * Три состояния экрана — загрузка, пусто, ошибка — должны выглядеть и читаться
 * по-разному.
 *
 * До этого пять экранов склеивали `isError || !data` в одну ветку, и HTTP 500
 * выводил текст «API не вернул минимум две записи». Пользователь не мог
 * отличить падение backend от нехватки данных, а причина отказа не показывалась
 * никогда.
 */

export function LoadingState({ text }: { text: string }) {
  return (
    <div className={styles.state} role="status" aria-live="polite">
      <Loader2 className={`${styles.icon} ${styles.spin}`} aria-hidden="true" />
      <p className={styles.text}>{text}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className={styles.state} role="status">
      <Inbox className={styles.icon} aria-hidden="true" />
      <p className={styles.title}>{title}</p>
      <p className={styles.text}>{description}</p>
      {action && <div className={styles.actions}>{action}</div>}
    </div>
  );
}

export function BlockedState({ title, description }: { title: string; description: string }) {
  return (
    <div className={styles.state} role="status">
      <Lock className={`${styles.icon} ${styles.warn}`} aria-hidden="true" />
      <p className={styles.title}>{title}</p>
      <p className={styles.text}>{description}</p>
    </div>
  );
}

/**
 * Ошибка показывает причину: код ответа, обращённый endpoint и текст `detail`
 * из FastAPI. Без этого диагностировать отказ по интерфейсу невозможно.
 */
export function ErrorState({
  title,
  error,
  onRetry,
}: {
  title: string;
  error: unknown;
  onRetry?: () => void;
}) {
  const detail = describeError(error);
  return (
    <div className={styles.state} role="alert">
      <AlertCircle className={`${styles.icon} ${styles.danger}`} aria-hidden="true" />
      <p className={styles.title}>{title}</p>
      {detail.status !== undefined && (
        <p className={styles.code}>
          HTTP {detail.status}
          {detail.endpoint ? ` · ${detail.endpoint}` : ""}
        </p>
      )}
      <p className={styles.text}>{detail.message}</p>
      {onRetry && (
        <div className={styles.actions}>
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Повторить запрос
          </Button>
        </div>
      )}
    </div>
  );
}
