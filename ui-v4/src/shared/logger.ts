/**
 * Client-side event logger (Iteration 12).
 *
 * Ring buffer of local events (last 1000), live subscription for the Log
 * panel, automatic capture of uncaught errors / unhandled rejections, and
 * best-effort flush of client events to the server journal
 * (`POST /api/v1/logs/client`) so that browser-side failures are recorded
 * alongside server events.
 */
export type LogLevel = "debug" | "info" | "warn" | "error";

export interface LogEvent {
  id: string;
  ts: number; // epoch ms
  level: LogLevel;
  source: string;
  origin: "client" | "server";
  message: string;
  detail?: string | null;
  stack?: string | null;
  path?: string | null;
  run_id?: string | null;
}

type Listener = (events: LogEvent[]) => void;

const MAX_EVENTS = 1000;
const FLUSH_MAX = 50;
const FLUSH_DELAY_MS = 4000;

let events: LogEvent[] = [];
let seq = 0;
const listeners = new Set<Listener>();
let unflushed: LogEvent[] = [];
let flushTimer: number | null = null;
let flushing = false;

function emit(): void {
  const snapshot = [...events];
  listeners.forEach(listener => { try { listener(snapshot); } catch { /* listener must not break logging */ } });
}

export function subscribeLogs(listener: Listener): () => void {
  listeners.add(listener);
  listener([...events]);
  return () => { listeners.delete(listener); };
}

function push(level: LogLevel, source: string, message: string, extra?: Partial<Omit<LogEvent, "id" | "ts" | "level" | "source" | "message" | "origin">>): LogEvent {
  const event: LogEvent = {
    id: `c${Date.now().toString(36)}-${(seq++).toString(36)}`,
    ts: Date.now(),
    level,
    source,
    origin: "client",
    message: String(message).slice(0, 2000),
    detail: extra?.detail != null ? String(extra.detail).slice(0, 4000) : null,
    stack: extra?.stack ? String(extra.stack).slice(0, 4000) : null,
    path: extra?.path ? String(extra.path).slice(0, 300) : null,
    run_id: extra?.run_id ? String(extra.run_id).slice(0, 80) : null,
  };
  events = [...events.slice(-(MAX_EVENTS - 1)), event];
  unflushed = [...unflushed.slice(-(FLUSH_MAX - 1)), event];
  emit();
  scheduleFlush();
  return event;
}

export function log(level: LogLevel, source: string, message: string, extra?: Partial<Omit<LogEvent, "id" | "ts" | "level" | "source" | "message" | "origin">>): void {
  push(level, source, message, extra);
}

export function logError(source: string, message: string, error?: unknown): void {
  let detail: string | undefined;
  let stack: string | undefined;
  if (error instanceof Error) {
    detail = error.message;
    stack = error.stack;
  } else if (error !== undefined && error !== null) {
    detail = String(error);
  }
  push("error", source, message, { detail, stack });
}

export function getLocalLogs(): LogEvent[] {
  return [...events];
}

export function clearLocalLogs(): void {
  events = [];
  seq = 0;
  unflushed = [];
  emit();
}

/** Schedule a debounced flush of client events to the server journal. */
export function scheduleFlush(): void {
  if (flushTimer !== null) return;
  flushTimer = window.setTimeout(() => {
    flushTimer = null;
    void flushClientLogs();
  }, FLUSH_DELAY_MS);
}

export async function flushClientLogs(): Promise<void> {
  if (flushing || unflushed.length === 0) return;
  flushing = true;
  const batch = [...unflushed];
  try {
    const response = await fetch("/api/v1/logs/client", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ events: batch.map(({ id, ts, ...rest }) => ({ ts: new Date(ts).toISOString(), ...rest })) }),
    });
    if (response.ok) {
      const flushedIds = new Set(batch.map(event => event.id));
      unflushed = unflushed.filter(event => !flushedIds.has(event.id));
    }
    // on failure the batch stays queued for the next attempt
  } catch {
    // no re-logging: a failed flush must not create an infinite loop
  } finally {
    flushing = false;
  }
}

/** Install window-level error capture (call once at app startup). */
export function installGlobalErrorHandlers(): void {
  window.addEventListener("error", (event) => {
    push("error", "window", event.message || "uncaught error", {
      detail: event.error instanceof Error ? event.error.message : undefined,
      stack: event.error instanceof Error ? event.error.stack : undefined,
      path: event.filename ? `${event.filename}:${event.lineno}` : undefined,
    });
  });
  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    push("error", "unhandledrejection", reason instanceof Error ? reason.message : String(reason ?? "unhandled rejection"), {
      detail: reason instanceof Error ? reason.message : undefined,
      stack: reason instanceof Error ? reason.stack : undefined,
    });
  });
}
