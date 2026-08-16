import { createRootRoute, createRoute, createRouter, redirect } from "@tanstack/react-router";
import DesignSystemPage from "../features/design-system/DesignSystemPage";
import { OverviewPage } from "../features/overview/OverviewPage";
import { TimelinePage } from "../features/timeline/TimelinePage";
import { DataManagerPage } from "../features/data-manager/DataManagerPage";
import { PhotoInspectorPage } from "../features/photo-inspector/PhotoInspectorPage";
import { MorphingPage } from "../features/morphing/MorphingPage";
import { PairAnalysisPage } from "../features/pair-analysis/PairAnalysisPage";
import { ClusteringPage } from "../features/clustering/ClusteringPage";
import { CalibrationPage } from "../features/calibration/CalibrationPage";
import { HypothesisValidationPage } from "../features/hypotheses/HypothesisValidationPage";
import { ReportsPage } from "../features/reports/ReportsPage";
import { MonetizationPage } from "../features/monetization/MonetizationPage";
import { AuditLogPage } from "../features/audit/AuditLogPage";
import { ArticlesPage } from "../features/articles/ArticlesPage";
import RootLayout from "./RootLayout";

const rootRoute = createRootRoute({ component: RootLayout });

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
  component: OverviewPage,
});

const timelineRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/timeline",
  component: TimelinePage,
});

const dataManagerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/data-manager",
  component: DataManagerPage,
});

const inspectorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inspector",
  component: PhotoInspectorPage,
});

const morphingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/morphing",
  component: MorphingPage,
});

const pairAnalysisRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/pair-analysis",
  component: PairAnalysisPage,
});

const clusteringRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/clustering",
  component: ClusteringPage,
});

const calibrationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/calibration",
  component: CalibrationPage,
});

const hypothesesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/hypotheses",
  component: HypothesisValidationPage,
});

const reportsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reports",
  component: ReportsPage,
});

const monetizationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/monetization",
  component: MonetizationPage,
});

const auditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/audit",
  component: AuditLogPage,
});

const articlesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/articles",
  component: ArticlesPage,
});

const designSystemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/design-system",
  component: DesignSystemPage,
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
  designSystemRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
