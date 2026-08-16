import React, { useEffect, useState } from "react";
import { consoleLogger, type ConsoleLogEntry, type LogSeverity } from "../../shared/logger";
import {
  Terminal,
  AlertTriangle,
  AlertCircle,
  Info,
  ShieldCheck,
  ChevronUp,
  ChevronDown,
  Trash2,
  Download,
  Search,
} from "lucide-react";

export const ConsoleLogDrawer: React.FC = () => {
  const [entries, setEntries] = useState<ConsoleLogEntry[]>([]);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  useEffect(() => {
    return consoleLogger.subscribe((logs) => {
      setEntries(logs);
    });
  }, []);

  const errorCount = entries.filter((e) => e.severity === "ERROR").length;
  const warnCount = entries.filter((e) => e.severity === "WARN").length;
  const infoCount = entries.filter((e) => e.severity === "INFO").length;
  const securityCount = entries.filter((e) => e.severity === "SECURITY").length;

  const filteredEntries = entries.filter((e) => {
    if (filterSeverity !== "ALL" && e.severity !== filterSeverity) return false;
    if (
      searchQuery &&
      !e.message.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !e.source.toLowerCase().includes(searchQuery.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  const getSeverityBadge = (severity: LogSeverity) => {
    switch (severity) {
      case "ERROR":
        return (
          <span className="inline-flex items-center gap-1 rounded bg-red-soft px-1.5 py-0.5 text-[10px] font-bold text-red-300 border border-red-500">
            <AlertCircle className="h-3 w-3" />
            ERROR
          </span>
        );
      case "WARN":
        return (
          <span className="inline-flex items-center gap-1 rounded bg-amber-soft px-1.5 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-500">
            <AlertTriangle className="h-3 w-3" />
            WARN
          </span>
        );
      case "SECURITY":
        return (
          <span className="inline-flex items-center gap-1 rounded bg-green-soft px-1.5 py-0.5 text-[10px] font-bold text-green-300 border border-green-500">
            <ShieldCheck className="h-3 w-3" />
            SECURITY
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded bg-cyan-soft px-1.5 py-0.5 text-[10px] font-bold text-cyan-300 border border-cyan-600">
            <Info className="h-3 w-3" />
            INFO
          </span>
        );
    }
  };

  const handleExportJson = () => {
    const dataStr = JSON.stringify(entries, null, 2);
    const blob = new Blob([dataStr], { type: "application/json;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", `deeputin_console_error_log_${Date.now()}.json`);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 font-mono text-xs select-none">
      {/* EXPANDED LOG PANEL */}
      {isOpen && (
        <div className="h-64 bg-surface-base border-t-2 border-cyan-600 shadow-2xl flex flex-col text-ink-primary">
          {/* Top Panel Controls */}
          <div className="flex items-center justify-between border-b border-line-default px-4 py-2 bg-surface-canvas">
            <div className="flex items-center gap-2">
              <span className="font-bold text-cyan-300 uppercase flex items-center gap-1.5">
                <Terminal className="h-4 w-4 text-cyan-400" />
                КОНСОЛЬ ОШИБОК И ЛОГОВ РАБОЧЕЙ СТАНЦИИ
              </span>

              <div className="flex items-center gap-1 ml-4 text-[11px]">
                <button
                  onClick={() => setFilterSeverity("ALL")}
                  className={`px-2 py-0.5 rounded transition ${
                    filterSeverity === "ALL"
                      ? "bg-cyan-soft text-cyan-300 border border-cyan-600 font-bold"
                      : "bg-surface-overlay text-ink-muted"
                  }`}
                >
                  Все ({entries.length})
                </button>
                <button
                  onClick={() => setFilterSeverity("ERROR")}
                  className={`px-2 py-0.5 rounded transition ${
                    filterSeverity === "ERROR"
                      ? "bg-red-soft text-red-300 border border-red-500 font-bold"
                      : "bg-surface-overlay text-ink-muted"
                  }`}
                >
                  Ошибки ({errorCount})
                </button>
                <button
                  onClick={() => setFilterSeverity("WARN")}
                  className={`px-2 py-0.5 rounded transition ${
                    filterSeverity === "WARN"
                      ? "bg-amber-soft text-amber-300 border border-amber-500 font-bold"
                      : "bg-surface-overlay text-ink-muted"
                  }`}
                >
                  Предупреждения ({warnCount})
                </button>
                <button
                  onClick={() => setFilterSeverity("SECURITY")}
                  className={`px-2 py-0.5 rounded transition ${
                    filterSeverity === "SECURITY"
                      ? "bg-green-soft text-green-300 border border-green-500 font-bold"
                      : "bg-surface-overlay text-ink-muted"
                  }`}
                >
                  Провенанс ({securityCount})
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Search filter input */}
              <div className="flex items-center gap-1 bg-surface-raised rounded px-2 py-0.5 border border-line-default">
                <Search className="h-3 w-3 text-ink-muted" />
                <input
                  type="text"
                  placeholder="Фильтр лога..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Поиск по журналу"
                  className="bg-transparent text-ink-primary text-[11px] focus:outline-none w-28"
                />
              </div>

              <button
                onClick={handleExportJson}
                className="flex items-center gap-1 rounded bg-surface-raised px-2 py-1 text-[11px] text-cyan-300 border border-cyan-600 hover:bg-surface-subtle transition"
                title="Экспортировать дамп"
              >
                <Download className="h-3 w-3" />
                <span>JSON-дамп</span>
              </button>

              <button
                onClick={() => consoleLogger.clear()}
                className="flex items-center gap-1 rounded bg-surface-raised px-2 py-1 text-[11px] text-ink-muted border border-line-default hover:text-ink-primary transition"
                title="Очистить консоль"
              >
                <Trash2 className="h-3 w-3" />
                <span>Очистить</span>
              </button>

              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded text-ink-muted hover:text-ink-primary transition"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Log Entries Table Area */}
          <div className="flex-1 overflow-y-auto p-3 space-y-1.5 bg-surface-canvas">
            {filteredEntries.length === 0 ? (
              <div className="text-center text-ink-muted py-8">
                Нет логов, соответствующих выбранному фильтру.
              </div>
            ) : (
              filteredEntries.map((e) => (
                <div
                  key={e.id}
                  className="flex items-start justify-between gap-3 rounded bg-surface-base p-2 border border-line-default hover:border-line-strong transition"
                >
                  <div className="flex items-start gap-2.5">
                    <span className="text-ink-muted whitespace-nowrap">{e.timestamp}</span>
                    {getSeverityBadge(e.severity)}
                    <span className="rounded bg-surface-overlay px-1.5 py-0.5 text-[10px] text-cyan-300 font-bold whitespace-nowrap border border-line-default">
                      [{e.source}]
                    </span>
                    <div>
                      <span className="text-ink-primary font-bold">{e.message}</span>
                      {e.details && (
                        <div className="text-[11px] text-ink-muted mt-0.5 font-mono">
                          └─ {e.details}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* COLLAPSED BOTTOM BAR (Always visible clickable footer) */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        className={`h-9 w-full bg-surface-canvas border-t border-line-default px-4 flex items-center justify-between cursor-pointer hover:bg-surface-base transition ${
          errorCount > 0 ? "bg-red-soft border-red-500" : ""
        }`}
      >
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 font-bold text-ink-secondary">
            {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            <Terminal className="h-4 w-4 text-cyan-400" />
            <span>КОНСОЛЬ ОШИБОК И ЛОГОВ</span>
          </span>

          <span className="flex items-center gap-2 text-[11px]">
            <span
              className={`rounded px-2 py-0.5 font-bold ${
                errorCount > 0
                  ? "bg-red-soft text-red-300 border border-red-500 animate-pulse"
                  : "bg-surface-overlay text-ink-muted"
              }`}
            >
              Ошибок: {errorCount}
            </span>
            <span className="rounded bg-surface-overlay px-2 py-0.5 text-amber-300 font-bold border border-line-default">
              Предупреждений: {warnCount}
            </span>
            <span className="rounded bg-surface-overlay px-2 py-0.5 text-cyan-300 border border-line-default">
              Инфо/Провенанс: {infoCount + securityCount}
            </span>
          </span>
        </div>

        <div className="flex items-center gap-3 text-ink-muted text-[11px]">
          <span className="text-green-400">STAGE 1 INTEGRITY: OK</span>
          <span>|</span>
          <span>Нажмите для {isOpen ? "сворачивания" : "раскрытия"} консоли</span>
        </div>
      </div>
    </div>
  );
};
