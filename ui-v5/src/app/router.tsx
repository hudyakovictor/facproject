import { createRootRoute, createRoute, createRouter, redirect } from "@tanstack/react-router";
import DesignSystemPage from "../features/design-system/DesignSystemPage";
import RootLayout from "./RootLayout";

const rootRoute = createRootRoute({ component: RootLayout });

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/design-system" });
  },
});

const designSystemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/design-system",
  component: DesignSystemPage,
});

const routeTree = rootRoute.addChildren([indexRoute, designSystemRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
