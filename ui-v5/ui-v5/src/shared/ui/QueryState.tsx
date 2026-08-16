import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { EmptyState, ErrorState, LoadingState } from "./states";

/**
 * Единая развилка «загрузка / ошибка / пусто / данные».
 *
 * Каждый экран воспроизводил её вручную, и половина делала это неверно: пять
 * страниц склеивали `isError || !data` в одну ветку, из-за чего HTTP 500
 * показывался текстом про нехватку записей. Обёртка задаёт один порядок
 * проверок, при котором ошибку невозможно перепутать с пустым результатом.
 *
 * Пустота определяется вызывающим кодом через `isEmpty`: «пусто» означает
 * разное на разных экранах — ноль записей, отсутствие пары, отсутствие
 * калибровки для бина.
 */
export function QueryState<TData, TError = unknown>({
  query,
  loadingText,
  errorTitle,
  isEmpty,
  emptyTitle,
  emptyDescription,
  emptyAction,
  children,
}: {
  query: UseQueryResult<TData, TError>;
  loadingText: string;
  errorTitle: string;
  isEmpty?: (data: TData) => boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  children: (data: TData) => ReactNode;
}) {
  /*
   * Порядок ветвей значим. Ошибка проверяется раньше отсутствия данных: при
   * отказе backend `data` тоже пуст, и обратный порядок превратил бы сбой сети
   * в сообщение «записей нет».
   */
  if (query.isError) {
    return (
      <ErrorState title={errorTitle} error={query.error} onRetry={() => void query.refetch()} />
    );
  }

  if (query.isLoading || query.data === undefined) {
    return <LoadingState text={loadingText} />;
  }

  if (isEmpty?.(query.data)) {
    return (
      <EmptyState
        title={emptyTitle ?? "Данных нет"}
        description={
          emptyDescription ??
          "API ответил успешно, но не вернул записей для этого экрана."
        }
        action={emptyAction}
      />
    );
  }

  return <>{children(query.data)}</>;
}
