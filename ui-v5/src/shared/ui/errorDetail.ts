/** Разбор ошибки запроса в отображаемые поля. Вынесено из states.tsx, чтобы
 * файл компонентов экспортировал только компоненты. */
export interface ErrorDetail {
  status?: number;
  endpoint?: string;
  message: string;
}

export function describeError(error: unknown): ErrorDetail {
  if (error && typeof error === "object") {
    const candidate = error as { status?: number; endpoint?: string; detail?: string; message?: string };
    if (typeof candidate.status === "number") {
      return {
        status: candidate.status,
        endpoint: candidate.endpoint,
        message: candidate.detail || candidate.message || "Ответ без описания причины.",
      };
    }
    if (typeof candidate.message === "string") return { message: candidate.message };
  }
  return { message: String(error ?? "Неизвестная ошибка.") };
}
