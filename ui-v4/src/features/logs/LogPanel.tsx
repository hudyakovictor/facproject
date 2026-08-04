/**
 * Log panel (Iteration 12) — slide-out side panel showing the event journal.
 *
 * Two tabs:
 *   «Клиент» — live events from this browser session (ring buffer, captured
 *   automatically: uncaught errors, unhandled rejections, failed API calls,
 *   explicit logs from components), with export/clear local.
 *   «Сервер» — the append-only backend journal (API errors, run/report
 *   events, client events mirrored by the flush), with refresh and .jsonl
 *   download.
 */
import { useEffect, useMemo, useState } from "react";
import { apiBase } from "../../shared/api";

interface ServerLogEvent {
  schema?: string;
  ts: string;
  level: string;
  source: string;
  origin?: string;
  message: string;
  detail?: string | null;
  stack?: string | null;
  path?: string | null;
  run_id?: string | null;
  job_id?: string | null;
}
import { clearLocalLogs, getLocalLogs, subscribeLogs, type LogEvent } from "../../shared/logger";

interface Props {
  open: boolean;
  onClose: () => void;
}

const LEVELS = ["all", "error", "warn", "info", "debug"] as const;
const LEVEL_CLASS: Record<string, string> = { error: "err", warn: "warn", info: "info", debug: "dbg" };

function formatTime(ts: number | string): string {
  const date = typeof ts === "number" ? new Date(ts) : new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  return date.toLocaleTimeString("ru-RU", { hour12: false }) + "." + String(date.getMilliseconds()).padStart(3, "0").slice(0, 2);
}

function EventRow({ event, defaultOpen }: { event: LogEvent | ServerLogEvent; defaultOpen?: boolean }) {
  const [expanded, setExpanded] = useState(Boolean(defaultOpen && (event.detail || event.stack)));
  const hasExtra = Boolean(event.detail || event.stack);
  const level = "level" in event ? event.level : "info";
  return (
    <article className={`log-row ${LEVEL_CLASS[level] || "info"}`}>
      <div className="log-row-head" onClick={() => hasExtra && setExpanded(value => !value)}>
        <time>{formatTime(event.ts)}</time>
        <i className="log-level">{level}</i>
        <b className="log-source">{event.source}</b>
        <span className="log-msg">{event.message}</span>
        {hasExtra && <em className="log-expand">{expanded ? "−" : "+"}</em>}
      </div>
      {expanded && (
        <div className="log-row-detail">
          {event.path && <code>path: {event.path}</code>}
          {"run_id" in event && event.run_id && <code>run: {event.run_id}</code>}
          {"origin" in event && event.origin && <code>origin: {event.origin}</code>}
          {event.detail && <pre>{event.detail}</pre>}
          {event.stack && <pre className="log-stack">{event.stack}</pre>}
        </div>
      )}
    </article>
  );
}

export default function LogPanel({ open, onClose }: Props) {
  const [localEvents, setLocalEvents] = useState<LogEvent[]>(getLocalLogs);
  const [serverEvents, setServerEvents] = useState<ServerLogEvent[]>([]);
  const [tab, setTab] = useState<"client" | "server">("client");
  const [level, setLevel] = useState<string>("all");
  const [source, setSource] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    const unsubscribe = subscribeLogs(setLocalEvents);
    return unsubscribe;
  }, [open]);

  const fetchServer = async () => {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`${apiBase()}/api/v1/logs?limit=1000`, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json() as { events: ServerLogEvent[] };
      setServerEvents(payload.events || []);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (open && tab === "server") void fetchServer();
  }, [open, tab]);

  const sources = useMemo(() => {
    const set = new Set<string>();
    (tab === "client" ? localEvents : serverEvents).forEach(event => set.add(event.source));
    return [...set].sort();
  }, [tab, localEvents, serverEvents]);

  const filtered = useMemo(() => {
    const rows = tab === "client" ? localEvents : serverEvents;
    const needle = search.trim().toLowerCase();
    return rows.filter(event => {
      if (level !== "all" && event.level !== level) return false;
      if (source !== "all" && event.source !== source) return false;
      if (needle && !(event.message + " " + (event.detail ?? "")).toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [tab, localEvents, serverEvents, level, source, search]);

  const exportLocal = () => {
    const blob = new Blob([JSON.stringify(localEvents, null, 1)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `deeputin_client_log_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  if (!open) return null;

  return (
    <div className="log-backdrop" onClick={onClose}>
      <aside className="log-panel" onClick={event => event.stopPropagation()}>
        <header className="log-panel-head">
          <div>
            <small>ITERATION 12 · EVENT LOG</small>
            <b>Журнал событий</b>
            <span>все ошибки фиксируются здесь · клиент + сервер</span>
          </div>
          <button className="log-close" onClick={onClose} title="Закрыть">×</button>
        </header>
        <div className="log-tabs">
          <button className={tab === "client" ? "active" : ""} onClick={() => setTab("client")}>
            Клиент <em>{localEvents.length}</em>
          </button>
          <button className={tab === "server" ? "active" : ""} onClick={() => setTab("server")}>
            Сервер <em>{serverEvents.length}</em>
          </button>
          <span className={`log-live ${localEvents.some(event => event.level === "error") ? "has-error" : ""}`}>● LIVE</span>
        </div>
        <div className="log-toolbar">
          <select value={level} onChange={event => setLevel(event.target.value)}>
            {LEVELS.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={source} onChange={event => setSource(event.target.value)}>
            <option value="all">все источники</option>
            {sources.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="поиск по тексту…" />
        </div>
        {message && <div className="log-message">{message}</div>}
        <div className="log-list">
          {filtered.length === 0 && <div className="log-empty">Событий нет</div>}
          {filtered.map(event => <EventRow key={"id" in event ? event.id : `${event.ts}-${event.message.slice(0, 20)}`} event={event} />)}
        </div>
        <footer className="log-panel-foot">
          {tab === "client" ? (
            <>
              <button className="ghost" onClick={exportLocal}>⬇ Экспорт JSON</button>
              <button className="ghost" onClick={() => { clearLocalLogs(); }}>✕ Очистить локальные</button>
              <span className="log-hint">локальный журнал сессии</span>
            </>
          ) : (
            <>
              <button className="ghost" disabled={busy} onClick={() => void fetchServer()}>{busy ? "Чтение…" : "⟳ Обновить"}</button>
              <a className="ghost log-download" href={`${apiBase()}/api/v1/logs/export`} download>⬇ Скачать журнал (.jsonl)</a>
              <span className="log-hint">append-only журнал сервера</span>
            </>
          )}
        </footer>
      </aside>
    </div>
  );
}
