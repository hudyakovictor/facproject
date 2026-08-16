// Global Console Error & Diagnostic Logger for DEEPUTIN UI v5
// Intercepts runtime errors, API exceptions, and validation flags

export type LogSeverity = "ERROR" | "WARN" | "INFO" | "SECURITY";

export interface ConsoleLogEntry {
  id: string;
  timestamp: string;
  severity: LogSeverity;
  source: string; // e.g. "3DDFA_v3", "API", "LOPO", "EXIF", "React"
  message: string;
  details?: string;
}

type LogSubscriber = (entries: ConsoleLogEntry[]) => void;

class ConsoleLogger {
  private entries: ConsoleLogEntry[] = [];

  private subscribers: Set<LogSubscriber> = new Set();

  constructor() {
    // Intercept browser runtime errors
    if (typeof window !== "undefined") {
      window.addEventListener("error", (event) => {
        this.addLog("ERROR", "WINDOW_RUNTIME", event.message, event.filename + ":" + event.lineno);
      });

      window.addEventListener("unhandledrejection", (event) => {
        this.addLog(
          "ERROR",
          "UNHANDLED_PROMISE",
          event.reason?.message || String(event.reason),
          event.reason?.stack || "No stack trace"
        );
      });
    }
  }

  public addLog(
    severity: LogSeverity,
    source: string,
    message: string,
    details?: string
  ): void {
    const entry: ConsoleLogEntry = {
      id: "log_" + Math.random().toString(36).slice(2, 9),
      timestamp: new Date().toLocaleTimeString("ru-RU"),
      severity,
      source,
      message,
      details,
    };

    this.entries = [entry, ...this.entries];
    this.notify();
  }

  public getEntries(): ConsoleLogEntry[] {
    return this.entries;
  }

  public clear(): void {
    this.entries = [];
    this.notify();
  }

  public subscribe(fn: LogSubscriber): () => void {
    this.subscribers.add(fn);
    fn(this.entries);
    return () => this.subscribers.delete(fn);
  }

  private notify(): void {
    this.subscribers.forEach((fn) => fn(this.entries));
  }
}

export const consoleLogger = new ConsoleLogger();
