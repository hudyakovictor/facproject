import { Outlet } from '@tanstack/react-router';

export function RootLayout() {
  return (
    <div className="app-root">
      <header className="app-header">
        <div className="app-header-brand">
          <span className="app-header-logo">◆</span>
          <span className="app-header-title">DEEPUTIN</span>
          <span className="app-header-version">v7</span>
        </div>
        <nav className="app-header-nav">
          <a href="/timeline" className="app-header-nav-item active">Таймлайн</a>
        </nav>
        <div className="app-header-status">
          <span className="app-header-status-dot" />
          <span>STAGE 1 · ИНВЕНТАРЬ</span>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
