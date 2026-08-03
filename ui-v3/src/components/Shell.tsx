import type { ReactNode } from "react";
import type { RouteId, ToastItem } from "../lib/types";
import { Button, Chip, cx } from "./ui";

const NAV: Array<{ id: RouteId; label: string; section?: string }> = [
  { id: "overview", label: "Обзор", section: "Анализ" },
  { id: "timeline", label: "Хронология" },
  { id: "gallery", label: "Галерея" },
  { id: "inspector", label: "Инспектор" },
  { id: "pairs", label: "Пары" },
  { id: "calibration", label: "Калибровка", section: "Качество" },
  { id: "run", label: "Сводка прогона" },
  { id: "report", label: "Отчёт" },
  { id: "control", label: "Управление анализом", section: "Операции" },
  { id: "settings", label: "Настройки" },
];

export default function Shell({
  route, setRoute, backendUp, photoCount, anomalyCount, dataMode, onRefresh, refreshing, children, toasts, onDismissToast,
}: {
  route: RouteId;
  setRoute: (r: RouteId) => void;
  backendUp: boolean | null;
  photoCount: number;
  anomalyCount: number;
  dataMode: string;
  onRefresh: () => void;
  refreshing: boolean;
  children: ReactNode;
  toasts: ToastItem[];
  onDismissToast: (id: string) => void;
}) {
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">D3</div>
          <div>
            <div className="brand-title">DEEPUTIN</div>
            <div className="brand-sub">forensic workstation v3</div>
          </div>
        </div>

        <Chip kind={backendUp === false ? "bad" : backendUp ? "ok" : "warn"}>
          backend {backendUp === null ? "…" : backendUp ? "online" : "offline"}
        </Chip>
        <Chip kind="info">{photoCount} фото</Chip>
        <Chip kind={anomalyCount ? "warn" : ""}>{anomalyCount} аномалий</Chip>
        <Chip>{dataMode}</Chip>
        <Chip kind="ok">not a verdict</Chip>

        <div className="topbar-actions">
          <Button size="sm" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? "обновление…" : "обновить"}
          </Button>
        </div>
      </header>

      <aside className="sidebar">
        {NAV.map(item => (
          <div key={item.id}>
            {item.section && <div className="nav-section">{item.section}</div>}
            <button
              type="button"
              className={cx("nav-item", route === item.id && "active")}
              onClick={() => setRoute(item.id)}
            >
              <span className="nav-label">{item.label}</span>
            </button>
          </div>
        ))}
        <div className="spacer" />
        <div className="disclaimer" style={{ padding: "12px 10px" }}>
          Измерения ≠ идентификация.
          <br />
          candidate ≠ вердикт.
        </div>
      </aside>

      <main className="main">{children}</main>

      <footer className="statusline">
        <span>DEEPUTIN UI v3</span>
        <span className="faint">·</span>
        <span>режим: {route}</span>
        <span className="spacer" />
        <span className="faint">observation-only · dark forensic UI</span>
      </footer>

      <div className="toast-host" aria-live="polite">
        {toasts.map(t => (
          <div key={t.id} className={cx("toast", t.kind)}>
            <div className="row">
              <div style={{ flex: 1 }}>{t.text}</div>
              <Button size="sm" variant="ghost" onClick={() => onDismissToast(t.id)}>✕</Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
