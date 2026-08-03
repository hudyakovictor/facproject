import { createContext, useContext, useState, useCallback, ReactNode } from "react";
import Icon from "./Icon";

export type ToastType = "info" | "success" | "warning" | "critical";

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

interface NotificationContextValue {
  toasts: Toast[];
  notify: (type: ToastType, title: string, message?: string) => void;
  remove: (id: string) => void;
}

const NotificationContext = createContext<NotificationContextValue | null>(null);
let nextToastId = 0;

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback((type: ToastType, title: string, message?: string) => {
    const id = `toast-${++nextToastId}`;
    setToasts(prev => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 5000);
  }, []);

  const remove = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <NotificationContext.Provider value={{ toasts, notify, remove }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none w-80">
        {toasts.map(toast => (
          <div key={toast.id} className={`pointer-events-auto flex items-start gap-3 p-3 bg-[#0a0a0a] border-l-4 shadow-xl border border-r-[#333] border-y-[#333] ${getColor(toast.type)} scanlines`}>
            <div className="mt-0.5">{getIcon(toast.type)}</div>
            <div className="flex-1 font-mono text-[10px]">
              <div className="text-[#e2e2e8] font-bold tracking-forensic">{toast.title}</div>
              {toast.message && <div className="text-[#797876] mt-0.5 leading-snug">{toast.message}</div>}
            </div>
            <button onClick={() => remove(toast.id)} className="text-[#797876] hover:text-white transition-colors">
              <Icon name="x" size={14} />
            </button>
          </div>
        ))}
      </div>
    </NotificationContext.Provider>
  );
}

export function useNotify() {
  const ctx = useContext(NotificationContext);
  if (!ctx) throw new Error("useNotify must be within NotificationProvider");
  return ctx.notify;
}

function getColor(type: ToastType) {
  switch (type) {
    case "info": return "border-l-info";
    case "success": return "border-l-nominal";
    case "warning": return "border-l-warning";
    case "critical": return "border-l-critical";
  }
}

function getIcon(type: ToastType) {
  switch (type) {
    case "info": return <Icon name="info" size={14} color="#5591c7" />;
    case "success": return <Icon name="check" size={14} color="#6daa45" />;
    case "warning": return <Icon name="alert-triangle" size={14} color="#e8af34" />;
    case "critical": return <Icon name="alert-octagon" size={14} color="#ff3b30" />;
  }
}
