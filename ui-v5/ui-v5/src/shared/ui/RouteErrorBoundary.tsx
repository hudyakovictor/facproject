import { Component, type ErrorInfo, type ReactNode } from "react";
import { consoleLogger } from "../logger";
import { ErrorState } from "./states";

interface Props {
  /** Название экрана, чтобы в сообщении было видно, что именно упало. */
  routeName: string;
  children: ReactNode;
}

interface State {
  error: unknown;
}

/**
 * Граница ошибок на уровне маршрута.
 *
 * Раньше границ не было ни одной: исключение в любом компоненте разрушало всё
 * дерево React и оставляло пустой чёрный экран без единого слова о причине.
 * Для рабочей станции это худший из возможных исходов — эксперт не может
 * отличить сбой интерфейса от отсутствия данных.
 *
 * Границa локальна: падение одного экрана не уносит верхнюю панель, статус-бар
 * и навигацию, поэтому пользователь может уйти на другой раздел.
 */
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: unknown): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    consoleLogger.addLog(
      "ERROR",
      "REACT_RENDER",
      `Сбой экрана «${this.props.routeName}»: ${error.message}`,
      info.componentStack ?? error.stack ?? undefined,
    );
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <ErrorState
          title={`Экран «${this.props.routeName}» не отрисован`}
          error={this.state.error}
          onRetry={this.reset}
        />
      );
    }
    return this.props.children;
  }
}
