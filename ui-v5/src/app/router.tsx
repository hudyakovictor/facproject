import { lazy, Suspense, type ComponentType } from "react";
import { createRootRoute, createRoute, createRouter, redirect } from "@tanstack/react-router";
import RootLayout from "./RootLayout";
import { RouteErrorBoundary } from "../shared/ui/RouteErrorBoundary";
import { LoadingState } from "../shared/ui/states";
import { validateAnalysisSearch } from "../shared/state/urlState";

/**
 * Маршруты рабочей станции.
 *
 * Экраны загружаются лениво (`React.lazy`): единая сборка давала один чанк на
 * 642 kB, в который попадали и таймлайн со всеми расчётами, и витрина
 * дизайн-системы, которая рядовому пользователю не нужна вовсе. Разделение
 * убирает из первой загрузки код тринадцати неоткрытых разделов.
 *
 * Каждый экран обёрнут границей ошибок: исключение в разделе больше не гасит
 * весь интерфейс — панель, статус-бар и навигация остаются на месте.
 */
function screen(name: string, load: () => Promise<{ default: ComponentType }>) {
  const Lazy = lazy(load);
  return function RouteScreen() {
    return (
      <RouteErrorBoundary routeName={name}>
        <Suspense fallback={<LoadingState text={`Загрузка раздела «${name}»…`} />}>
          <Lazy />
        </Suspense>
      </RouteErrorBoundary>
    );
  };
}

const rootRoute = createRootRoute({
  component: RootLayout,
  /**
   * Состояние анализа живёт в строке запроса, чтобы ссылку можно было
   * переслать коллеге и увидеть тот же экран (§4 ТЗ). Невалидный параметр
   * отбрасывается, а не роняет навигацию.
   */
  validateSearch: validateAnalysisSearch,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/overview" });
  },
});

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/overview",
  component: screen("Обзор", () =>
    import("../features/overview/OverviewPage").then((m) => ({ default: m.OverviewPage })),
  ),
});

const timelineRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/timeline",
  component: screen("Таймлайн", () =>
    import("../features/timeline/TimelinePage").then((m) => ({ default: m.TimelinePage })),
  ),
});

const dataManagerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/data-manager",
  component: screen("Данные", () =>
    import("../features/data-manager/DataManagerPage").then((m) => ({
      default: m.DataManagerPage,
    })),
  ),
});

const inspectorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inspector",
  component: screen("Инспектор", () =>
    import("../features/photo-inspector/PhotoInspectorPage").then((m) => ({
      default: m.PhotoInspectorPage,
    })),
  ),
});

const morphingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/morphing",
  component: screen("Морфинг", () =>
    import("../features/morphing/MorphingPage").then((m) => ({ default: m.MorphingPage })),
  ),
});

const pairAnalysisRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/pair-analysis",
  component: screen("Сравнение", () =>
    import("../features/pair-analysis/PairAnalysisPage").then((m) => ({
      default: m.PairAnalysisPage,
    })),
  ),
});

const clusteringRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/clustering",
  component: screen("Кластеры", () =>
    import("../features/clustering/ClusteringPage").then((m) => ({ default: m.ClusteringPage })),
  ),
});

const calibrationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/calibration",
  component: screen("Калибровка", () =>
    import("../features/calibration/CalibrationPage").then((m) => ({
      default: m.CalibrationPage,
    })),
  ),
});

const hypothesesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/hypotheses",
  component: screen("Гипотезы", () =>
    import("../features/hypotheses/HypothesisValidationPage").then((m) => ({
      default: m.HypothesisValidationPage,
    })),
  ),
});

const reportsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reports",
  component: screen("Отчёты", () =>
    import("../features/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })),
  ),
});

const articlesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/articles",
  component: screen("Статьи", () =>
    import("../features/articles/ArticlesPage").then((m) => ({ default: m.ArticlesPage })),
  ),
});

const monetizationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/monetization",
  component: screen("Монетизация", () =>
    import("../features/monetization/MonetizationPage").then((m) => ({
      default: m.MonetizationPage,
    })),
  ),
});

const auditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/audit",
  component: screen("Аудит", () =>
    import("../features/audit/AuditLogPage").then((m) => ({ default: m.AuditLogPage })),
  ),
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: screen("Настройки", () =>
    import("../features/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })),
  ),
});

const designSystemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/design-system",
  component: screen("Дизайн-система", () => import("../features/design-system/DesignSystemPage")),
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  overviewRoute,
  timelineRoute,
  dataManagerRoute,
  inspectorRoute,
  morphingRoute,
  pairAnalysisRoute,
  clusteringRoute,
  calibrationRoute,
  hypothesesRoute,
  reportsRoute,
  articlesRoute,
  monetizationRoute,
  auditRoute,
  settingsRoute,
  designSystemRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
