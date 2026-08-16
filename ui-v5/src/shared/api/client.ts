import type { z } from "zod";
import { consoleLogger } from "../logger";

/**
 * Ошибка обращения к API с сохранённым контекстом: код, endpoint и `detail`
 * из FastAPI. Интерфейс обязан показывать причину отказа, а не сводить любую
 * неудачу к фразе «данных нет».
 */
export class ApiError extends Error {
  readonly status: number;
  readonly endpoint: string;
  readonly detail: string;

  constructor(status: number, endpoint: string, detail: string) {
    super(`API ${status} ${endpoint}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.endpoint = endpoint;
    this.detail = detail;
  }
}

/** Несоответствие ответа согласованной схеме. */
export class ContractError extends Error {
  readonly endpoint: string;
  readonly issues: string[];

  constructor(endpoint: string, issues: string[]) {
    super(`Ответ ${endpoint} не соответствует контракту: ${issues.join("; ")}`);
    this.name = "ContractError";
    this.endpoint = endpoint;
    this.issues = issues;
  }
}

const REQUEST_TIMEOUT_MS = 30_000;

function extractDetail(body: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (parsed.detail != null) return JSON.stringify(parsed.detail);
  } catch {
    /* тело не JSON — используем как есть */
  }
  return body.slice(0, 400) || "Ответ без описания причины.";
}

/**
 * Выполняет запрос и валидирует ответ схемой.
 *
 * Таймаут и `AbortController` обязательны: без них зависший backend оставляет
 * пользователя с вечным индикатором загрузки и без объяснения.
 */
export async function getValidated<T>(
  endpoint: string,
  schema: z.ZodType<T>,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let payload: unknown;

  try {
    const response = await fetch(endpoint, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) {
      const detail = extractDetail(await response.text());
      consoleLogger.addLog("ERROR", "API", `${response.status} ${endpoint}`, detail);
      throw new ApiError(response.status, endpoint, detail);
    }
    payload = await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    const aborted = error instanceof DOMException && error.name === "AbortError";
    const message = aborted
      ? `Превышено время ожидания ${REQUEST_TIMEOUT_MS / 1000} с`
      : error instanceof Error
        ? error.message
        : String(error);
    consoleLogger.addLog("ERROR", "API", `Сбой запроса ${endpoint}`, message);
    throw new ApiError(0, endpoint, message);
  } finally {
    clearTimeout(timer);
  }

  const result = schema.safeParse(payload);
  if (!result.success) {
    const issues = result.error.issues
      .slice(0, 10)
      .map((issue) => `${issue.path.join(".") || "<корень>"}: ${issue.message}`);
    consoleLogger.addLog(
      "ERROR",
      "API_CONTRACT",
      `Ответ ${endpoint} не соответствует схеме`,
      issues.join("\n"),
    );
    throw new ContractError(endpoint, issues);
  }
  return result.data;
}
