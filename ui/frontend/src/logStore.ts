import { useSyncExternalStore } from "react";

export type UiLogLevel = "debug" | "info" | "warning" | "error";

export interface UiLogEntry {
	seq: number;
	ts: string;
	level: UiLogLevel;
	source: string;
	message: string;
}

const MAX_ENTRIES = 1500;
let seq = 0;
let entries: UiLogEntry[] = [];
const listeners = new Set<() => void>();

function emit() {
	for (const listener of listeners) listener();
}

export function normalizeLevel(level: string | undefined): UiLogLevel {
	const value = (level ?? "info").toLowerCase();
	if (value === "warn" || value === "warning") return "warning";
	if (value === "error" || value === "critical" || value === "fatal") return "error";
	if (value === "debug" || value === "trace") return "debug";
	return "info";
}

export function uiLogRaw(entry: Omit<UiLogEntry, "seq">) {
	entries = [...entries.slice(-(MAX_ENTRIES - 1)), { ...entry, seq: ++seq }];
	emit();
}

export function uiLog(level: UiLogLevel, source: string, message: string) {
	uiLogRaw({ ts: new Date().toISOString(), level, source, message });
}

export function clearUiLog() {
	entries = [];
	emit();
}

function subscribe(listener: () => void) {
	listeners.add(listener);
	return () => {
		listeners.delete(listener);
	};
}

export function useUiLogEntries(): UiLogEntry[] {
	return useSyncExternalStore(subscribe, () => entries);
}

let networkLoggingInstalled = false;
let requestSeq = 0;

/** Install one global fetch observer so every API failure is visible to a non-technical operator. */
export function installNetworkLogging() {
	if (networkLoggingInstalled || typeof window === "undefined") return;
	networkLoggingInstalled = true;
	const originalFetch = window.fetch.bind(window);
	window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
		const id = ++requestSeq;
		const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
		const rawUrl = input instanceof Request ? input.url : String(input);
		const url = rawUrl.startsWith(window.location.origin) ? rawUrl.slice(window.location.origin.length) : rawUrl;
		const isLogPoll = url.startsWith("/api/logs");
		const started = performance.now();
		if (!isLogPoll) uiLog("debug", "network", `#${id} → ${method} ${url}`);
		try {
			const response = await originalFetch(input, init);
			const elapsed = Math.round(performance.now() - started);
			if (!isLogPoll) {
				const level: UiLogLevel = response.ok ? (elapsed > 1500 ? "warning" : "info") : "error";
				uiLog(level, "network", `#${id} ← ${response.status} ${method} ${url} · ${elapsed} ms`);
			}
			return response;
		} catch (error) {
			const elapsed = Math.round(performance.now() - started);
			const aborted = error instanceof DOMException && error.name === "AbortError";
			if (!isLogPoll) uiLog(aborted ? "debug" : "error", "network", `#${id} × ${method} ${url} · ${elapsed} ms · ${String(error)}`);
			throw error;
		}
	};
}
