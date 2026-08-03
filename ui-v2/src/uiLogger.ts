export type UiLogLevel = "info" | "warn" | "error";

export interface UiLogEntry {
  timestamp: string;
  level: UiLogLevel;
  message: string;
  context?: string;
  details?: unknown;
}

const STORAGE_KEY = "deeputin.ui.log.v1";
const MAX_ENTRIES = 500;

function readEntries(): UiLogEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

export function writeUiLog(level: UiLogLevel, message: string, context?: string, details?: unknown): void {
  const entry: UiLogEntry = { timestamp: new Date().toISOString(), level, message, context, details };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...readEntries(), entry].slice(-MAX_ENTRIES)));
  } catch { /* Logging must never break the UI. */ }
  const prefix = `[UI:${level.toUpperCase()}]${context ? ` [${context}]` : ""}`;
  if (level === "error") console.error(prefix, message, details);
  else if (level === "warn") console.warn(prefix, message, details);
  else console.info(prefix, message, details);
}

export function getUiLogs(): UiLogEntry[] { return readEntries(); }

export function clearUiLogs(): void {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* noop */ }
}

export function installUiLogging(): () => void {
  const onError = (event: ErrorEvent) => writeUiLog("error", event.message || "Неизвестная ошибка JavaScript", "window.error", { source: event.filename, line: event.lineno, column: event.colno });
  const onRejection = (event: PromiseRejectionEvent) => writeUiLog("error", String(event.reason?.message ?? event.reason ?? "Отклонённое Promise"), "unhandledrejection");
  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);
  return () => { window.removeEventListener("error", onError); window.removeEventListener("unhandledrejection", onRejection); };
}
