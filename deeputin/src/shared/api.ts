export interface ApiErrorDetails {
  status: number | null;
  detail: string;
}

export class ApiRequestError extends Error {
  readonly status: number | null;
  readonly detail: string;

  constructor({ status, detail }: ApiErrorDetails) {
    super(detail);
    this.name = 'ApiRequestError';
    this.status = status;
    this.detail = detail;
  }
}

function readDetail(payload: unknown, status: number | null): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
  }

  if (status === 404) {
    return 'Источник не найден по этому API endpoint.';
  }

  if (status === 409) {
    return 'Stage ещё не готов: источник вернул HTTP 409.';
  }

  if (status === 422) {
    return 'Источник отклонил параметры запроса: проверьте возвращённые идентификаторы и scope.';
  }

  if (status !== null) {
    return `API вернул ошибку HTTP ${status}.`;
  }

  return 'Источник данных недоступен.';
}

async function readPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  const text = await response.text();
  if (!text.trim()) return null;

  if (contentType.includes('application/json')) {
    try {
      return JSON.parse(text) as unknown;
    } catch {
      return { detail: text };
    }
  }

  return { detail: text };
}

async function requestResponse(path: string, options: RequestInit): Promise<Response> {
  try {
    const headers = new Headers(options.headers);
    headers.set('Accept', 'application/json');
    return await fetch(path, {
      ...options,
      headers,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }

    throw new ApiRequestError({
      status: null,
      detail: 'Не удалось соединиться с API. Проверьте доступность рассчитанного источника.',
    });
  }
}

export function unwrapArtifactPayload<T = unknown>(response: T): T {
  if (typeof response !== 'object' || response === null || Array.isArray(response)) {
    return response;
  }
  const record = response as Record<string, unknown>;
  if ('name' in record && 'format' in record && 'payload' in record) {
    return record.payload as T;
  }
  return response;
}

export async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await requestResponse(path, options);
  const payload = await readPayload(response);

  if (!response.ok) {
    throw new ApiRequestError({
      status: response.status,
      detail: readDetail(payload, response.status),
    });
  }

  return payload as T;
}

export async function requestText(path: string, options: RequestInit = {}): Promise<string> {
  const response = await requestResponse(path, options);
  const text = await response.text();

  if (!response.ok) {
    let payload: unknown = text;
    if ((response.headers.get('content-type') ?? '').includes('application/json')) {
      try {
        payload = JSON.parse(text) as unknown;
      } catch {
        payload = { detail: text };
      }
    }
    throw new ApiRequestError({
      status: response.status,
      detail: readDetail(payload, response.status),
    });
  }

  return text;
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}
