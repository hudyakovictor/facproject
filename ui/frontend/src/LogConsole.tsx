import { useEffect, useRef, useState } from "react";
import { loadLogs } from "./api";
import { clearUiLog, normalizeLevel, uiLog, uiLogRaw, useUiLogEntries } from "./logStore";
import type { UiLogLevel } from "./logStore";

const LEVELS: UiLogLevel[] = ["debug", "info", "warning", "error"];

export function LogConsole() {
	const entries = useUiLogEntries();
	const [open, setOpen] = useState(false);
	const [minLevel, setMinLevel] = useState<UiLogLevel>("debug");
	const [filter, setFilter] = useState("");
	const [paused, setPaused] = useState(false);
	const [backendOk, setBackendOk] = useState<boolean | null>(null);
	const afterRef = useRef(0);
	const bodyRef = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		const onError = (event: ErrorEvent) => uiLog("error", "window", event.message);
		const onRejection = (event: PromiseRejectionEvent) => uiLog("error", "promise", String(event.reason));
		window.addEventListener("error", onError);
		window.addEventListener("unhandledrejection", onRejection);
		uiLog("info", "console", "Консоль логов запущена");
		return () => {
			window.removeEventListener("error", onError);
			window.removeEventListener("unhandledrejection", onRejection);
		};
	}, []);

	useEffect(() => {
		if (paused) return;
		let stopped = false;
		const tick = async () => {
			try {
				const result = await loadLogs(afterRef.current);
				if (stopped) return;
				for (const item of result.entries) {
					uiLogRaw({
						ts: item.ts ?? new Date().toISOString(),
						level: normalizeLevel(item.level),
						source: `backend·${item.logger ?? "root"}`,
						message: [item.message ?? "", item.event ? `event=${item.event}` : "", item.run_id ? `run=${item.run_id}` : ""].filter(Boolean).join(" "),
					});
				}
				if (result.entries.length > 0) afterRef.current = result.last_seq;
				setBackendOk(true);
			} catch {
				if (!stopped) setBackendOk(false);
			}
		};
		void tick();
		const id = window.setInterval(() => {
			void tick();
		}, 2000);
		return () => {
			stopped = true;
			window.clearInterval(id);
		};
	}, [paused]);

	useEffect(() => {
		if (open && !paused && bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
	}, [entries, open, paused]);

	const min = LEVELS.indexOf(minLevel);
	const q = filter.trim().toLowerCase();
	const visible = entries.filter((e) => LEVELS.indexOf(e.level) >= min && (!q || `${e.source} ${e.message}`.toLowerCase().includes(q)));
	const errorCount = entries.filter((e) => e.level === "error").length;

	useEffect(() => {
		if (errorCount > 0) setOpen(true);
	}, [errorCount]);

	function exportLogs() {
		const payload = JSON.stringify({ exported_at: new Date().toISOString(), location: window.location.href, user_agent: navigator.userAgent, entries }, null, 2);
		const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
		const anchor = document.createElement("a");
		anchor.href = url; anchor.download = `deeputin-ui-logs-${new Date().toISOString().replace(/[:.]/g, "-")}.json`; anchor.click();
		URL.revokeObjectURL(url);
		uiLog("info", "console", `Экспортировано ${entries.length} записей`);
	}

	async function copyErrors() {
		const errors = entries.filter((e) => e.level === "error" || e.level === "warning");
		await navigator.clipboard.writeText(errors.map((e) => `${e.ts} ${e.level.toUpperCase()} ${e.source} ${e.message}`).join("\n"));
		uiLog("info", "console", `Скопировано предупреждений и ошибок: ${errors.length}`);
	}

	return (
		<div className={`log-console ${open ? "open" : ""}`}>
			<div className="log-console-header">
				<button className="log-console-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
					{open ? "▾" : "▴"} Консоль
				</button>
				<span className="log-console-counts">
					{entries.length} записей
					{errorCount > 0 && <b className="log-console-errors"> · {errorCount} ошибок</b>}
				</span>
				{backendOk === false && <span className="log-console-warn">бэкенд-логи недоступны (нет /api/logs — перезапустите backend с обновлением)</span>}
				{open && (
					<>
						<select value={minLevel} onChange={(e) => setMinLevel(e.target.value as UiLogLevel)} aria-label="Минимальный уровень">
							{LEVELS.map((l) => (
								<option key={l} value={l}>
									{l}+
								</option>
							))}
						</select>
						<input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Фильтр…" aria-label="Фильтр логов" />
						<button onClick={() => setPaused(!paused)}>{paused ? "Продолжить" : "Пауза"}</button>
						<button onClick={copyErrors}>Копировать ошибки</button>
						<button onClick={exportLogs}>Экспорт JSON</button>
						<button onClick={clearUiLog}>Очистить</button>
					</>
				)}
			</div>
			{open && (
				<div className="log-console-body" ref={bodyRef} role="log" aria-live="polite">
					{visible.length === 0 && <p className="log-console-empty">Пока нет записей под текущий фильтр.</p>}
					{visible.map((e) => (
						<div key={e.seq} className={`log-line level-${e.level}`}>
							<time>{e.ts.slice(11, 19)}</time>
							<i>{e.level}</i>
							<em>{e.source}</em>
							<span>{e.message}</span>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
