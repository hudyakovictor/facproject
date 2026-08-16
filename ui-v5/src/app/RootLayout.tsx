import { Outlet } from "@tanstack/react-router";
import { TopBar } from "../features/shell/TopBar";
import { ConsoleLogDrawer } from "../features/shell/ConsoleLogDrawer";
import { CommandPalette } from "../features/shell/CommandPalette";
import { StatusBar } from "../features/shell/StatusBar";
import { RouteErrorBoundary } from "../shared/ui/RouteErrorBoundary";
import { useUrlSync } from "../shared/state/useUrlSync";

export default function RootLayout() {
  /**
   * Единый источник истины для состояния анализа — `useAnalysisStore`, а его
   * зеркало в строке запроса делает экран воспроизводимым по ссылке. Прежние
   * `useState` для ракурса и трёх порогов жили здесь и передавались пропсами
   * только в `TopBar`, ни на один экран не влияя (BUG-1).
   */
  useUrlSync();

  return (
    <div className="min-h-screen w-full bg-[#080d12] text-[#e2e8f0] font-sans antialiased flex flex-col">
      <RouteErrorBoundary routeName="верхняя панель">
        <TopBar />
      </RouteErrorBoundary>

      <main className="flex-1 flex flex-col w-full">
        <Outlet />
      </main>

      {/*
        Правило 20 AGENTS.md: маркировка «не вердикт» видна постоянно. Она —
        часть нижней status bar (§4.3 ТЗ) вместе со сводкой контекста прогона.
      */}
      <RouteErrorBoundary routeName="строка состояния">
        <StatusBar />
      </RouteErrorBoundary>

      <CommandPalette />
      <ConsoleLogDrawer />
    </div>
  );
}
