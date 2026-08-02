import { Component, type ErrorInfo, type ReactNode } from "react";
import { t } from "../i18n";

interface Props {
  children: ReactNode;
  /** Метка компонента для сообщения и логов (например "MeshViewer"). */
  label: string;
  /** Необязательный внешний сброс (например закрыть оверлей вместо перерисовки). */
  onReset?: () => void;
}

interface State {
  error: Error | null;
}

/** 🚧 GATE → React Error Boundary (DEV_FIX_TZ P2.4 / 5.2-2.8).
 *
 * До этого в приложении не было ни одного boundary: любая необработанная
 * ошибка рендера (например неконсистентный меш из API или битые координаты)
 * убивала всё дерево и оставляла белый экран без возможности восстановления.
 *
 * Boundary НЕ прячет ошибку: он показывает её текст и имя компонента, чтобы
 * сбой попадал в отчёт, а не молча подменялся «пустым» состоянием — это
 * прямое требование `app6/AGENTS.md` (недопустима тихая подмена данных).
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Явный лог: сбой должен быть видим в консоли разработчика и в баг-репорте.
    console.error(`[ErrorBoundary:${this.props.label}]`, error, info.componentStack);
  }

  private handleReset = (): void => {
    this.setState({ error: null });
    this.props.onReset?.();
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div
        role="alert"
        className="h-full w-full overflow-auto bg-bg p-6 font-mono text-[11px] text-text"
      >
        <div className="max-w-2xl border border-critical bg-critical/10 p-4">
          <div className="font-display text-sm tracking-forensic text-critical mb-2">
            {t.errorBoundaryTitle} · {this.props.label}
          </div>
          <p className="text-text-muted mb-3">{t.errorBoundaryHint}</p>
          <pre className="whitespace-pre-wrap break-words bg-surface-2 border border-border p-2 text-[10px] text-text mb-3">
            {error.name}: {error.message}
          </pre>
          <button
            onClick={this.handleReset}
            aria-label={t.a11yRestartComponent}
            className="px-3 py-1.5 font-mono text-[10px] tracking-forensic border border-info/50 bg-info/15 hover:bg-info/30"
          >
            {t.errorBoundaryRetry}
          </button>
        </div>
      </div>
    );
  }
}
