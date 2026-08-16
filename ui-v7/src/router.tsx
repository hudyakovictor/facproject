import { createRootRoute, createRoute, createRouter, redirect } from '@tanstack/react-router';
import { RootLayout } from './app/RootLayout';
import { TimelinePage } from './features/timeline/TimelinePage';

const rootRoute = createRootRoute({
  component: RootLayout,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/timeline' });
  },
});

const timelineRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/timeline',
  component: TimelinePage,
});

const routeTree = rootRoute.addChildren([indexRoute, timelineRoute]);

export type RouteTree = typeof routeTree;

export const router = createRouter({ routeTree });
