import { Outlet } from '@tanstack/react-router';

export function RootLayout() {
  return (
    <div className="app-root">
      <header className="app-header">
        <div className="app-header-brand">
          <span className="app-header-title">DEEPUTIN</span>
        </div>
        <nav className="app-header-nav">
          <a href="/timeline" className="app-header-nav-item active">Таймлайн</a>
        </nav>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
