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
  Bug,
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
          <span className="inline-flex items-center gap-1 rounded bg-rose-950 px-1.5 py-0.5 text-[10px] font-bold text-rose-300 border border-rose-800">
            <AlertCircle className="h-3 w-3" />
            ERROR
          </span>
        );
      case "WARN":
        return (
          <span className="inline-flex items-center gap-1 rounded bg-amber-950 px-1.5 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-800">
            <AlertTriangle className="h-3 w-3" />
            WARN
          </span>
        );
      case "SECURITY":
        return (
          <span className="inline-flex items-center gap-1 rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] font-bold text-emerald-300 border border-emerald-800">
            <ShieldCheck className="h-3 w-3" />
            SECURITY
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded bg-cyan-950 px-1.5 py-0.5 text-[10px] font-bold text-cyan-300 border border-cyan-800">
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
  };

  const handleTestError = () => {
    consoleLogger.addLog(
      "ERROR",
      "UI_VALIDATION",
      "Имитация сетевого сбоя: таймаут ответа от /api/v1/photos/DEEPUTIN_2010_1025_006/mesh",
      "Failed to fetch resource from server. Check CORS or uvicorn port 8000."
    );
  };

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 font-mono text-xs select-none">
      {/* EXPANDED LOG PANEL */}
      {isOpen && (
        <div className="h-64 bg-[#0b1117] border-t-2 border-cyan-700/80 shadow-2xl flex flex-col text-[#e2e8f0]">
          {/* Top Panel Controls */}
          <div className="flex items-center justify-between border-b border-[#1f2d3d] px-4 py-2 bg-[#080d12]">
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
                      ? "bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold"
                      : "bg-[#141e27] text-slate-400"
                  }`}
                >
                  Все ({entries.length})
                </button>
                <button
                  onClick={() => setFilterSeverity("ERROR")}
                  className={`px-2 py-0.5 rounded transition ${
                    filterSeverity === "ERROR"
                      ? "bg-rose-950 text-rose-300 border border-rose-800 font-bold"
                      : "bg-[#141e27] text-slate-400"
                  }`}
                >
                  Ошибки ({errorCount})
                </button>
                <button
                  onClick={() => setFilterSeverity("WARN")}
                  className={`px-2 py-0.5 rounded transition ${
                    filterSeverity === "WARN"
                      ? "bg-amber-950 text-amber-300 border border-amber-800 font-bold"
                      : "bg-[#141e27] text-slate-400"
                  }`}
                >
                  Предупреждения ({warnCount})
                </button>
                <button
                  onClick={() => setFilterSeverity("SECURITY")}
                  className={`px-2 py-0.5 rounded transition ${
                    filterSeverity === "SECURITY"
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold"
                      : "bg-[#141e27] text-slate-400"
                  }`}
                >
                  Провенанс ({securityCount})
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Search filter input */}
              <div className="flex items-center gap-1 bg-[#101820] rounded px-2 py-0.5 border border-[#1f2d3d]">
                <Search className="h-3 w-3 text-slate-400" />
                <input
                  type="text"
                  placeholder="Фильтр лога..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-transparent text-white text-[11px] focus:outline-none w-28"
                />
              </div>

              <button
                onClick={handleTestError}
                className="flex items-center gap-1 rounded bg-rose-950 px-2 py-1 text-[11px] text-rose-300 border border-rose-800 hover:bg-rose-900 transition"
                title="Сгенерировать тестовую ошибку"
              >
                <Bug className="h-3 w-3" />
                <span>+Тест ошибки</span>
              </button>

              <button
                onClick={handleExportJson}
                className="flex items-center gap-1 rounded bg-[#101820] px-2 py-1 text-[11px] text-cyan-300 border border-cyan-800 hover:bg-[#18232d] transition"
                title="Экспортировать дамп"
              >
                <Download className="h-3 w-3" />
                <span>JSON-дамп</span>
              </button>

              <button
                onClick={() => consoleLogger.clear()}
                className="flex items-center gap-1 rounded bg-[#101820] px-2 py-1 text-[11px] text-slate-400 border border-[#1f2d3d] hover:text-white transition"
                title="Очистить консоль"
              >
                <Trash2 className="h-3 w-3" />
                <span>Очистить</span>
              </button>

              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded text-slate-400 hover:text-white transition"
              >
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Log Entries Table Area */}
          <div className="flex-1 overflow-y-auto p-3 space-y-1.5 bg-[#080d12]">
            {filteredEntries.length === 0 ? (
              <div className="text-center text-slate-500 py-8">
                Нет логов, соответствующих выбранному фильтру.
              </div>
            ) : (
              filteredEntries.map((e) => (
                <div
                  key={e.id}
                  className="flex items-start justify-between gap-3 rounded bg-[#0b1117] p-2 border border-[#1f2d3d] hover:border-slate-600 transition"
                >
                  <div className="flex items-start gap-2.5">
                    <span className="text-slate-500 whitespace-nowrap">{e.timestamp}</span>
                    {getSeverityBadge(e.severity)}
                    <span className="rounded bg-[#141e27] px-1.5 py-0.5 text-[10px] text-cyan-300 font-bold whitespace-nowrap border border-[#1f2d3d]">
                      [{e.source}]
                    </span>
                    <div>
                      <span className="text-white font-bold">{e.message}</span>
                      {e.details && (
                        <div className="text-[11px] text-slate-400 mt-0.5 font-mono">
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
        className={`h-9 w-full bg-[#080d12] border-t border-[#1f2d3d] px-4 flex items-center justify-between cursor-pointer hover:bg-[#0b1117] transition ${
          errorCount > 0 ? "bg-rose-950/40 border-rose-800" : ""
        }`}
      >
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 font-bold text-slate-300">
            {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
            <Terminal className="h-4 w-4 text-cyan-400" />
            <span>КОНСОЛЬ ОШИБОК И ЛОГОВ</span>
          </span>

          <span className="flex items-center gap-2 text-[11px]">
            <span
              className={`rounded px-2 py-0.5 font-bold ${
                errorCount > 0
                  ? "bg-rose-950 text-rose-300 border border-rose-700 animate-pulse"
                  : "bg-[#141e27] text-slate-400"
              }`}
            >
              Ошибок: {errorCount}
            </span>
            <span className="rounded bg-[#141e27] px-2 py-0.5 text-amber-300 font-bold border border-[#1f2d3d]">
              Предупреждений: {warnCount}
            </span>
            <span className="rounded bg-[#141e27] px-2 py-0.5 text-cyan-300 border border-[#1f2d3d]">
              Инфо/Провенанс: {infoCount + securityCount}
            </span>
          </span>
        </div>

        <div className="flex items-center gap-3 text-slate-400 text-[11px]">
          <span className="text-emerald-400">STAGE 1 INTEGRITY: OK</span>
          <span>|</span>
          <span>Нажмите для {isOpen ? "сворачивания" : "раскрытия"} консоли</span>
        </div>
      </div>
    </div>
  );
};
