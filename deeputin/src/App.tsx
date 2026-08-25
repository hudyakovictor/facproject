import { useEffect, useMemo, useState } from 'react';

import {
  ComparePage,
  comparePage,
  MethodologyPage,
  methodologyPage,
  PhotoDetailPage,
  photoDetailPage,
  PublicationsPage,
  publicationsPage,
  ReportPage,
  reportPage,
  ResearchPage,
  researchPage,
  TimelinePage,
  timelinePage,
} from '@/pages';
import type { PageEntry, PageId } from '@/shared/contracts';

const pages: readonly PageEntry[] = [
  { definition: timelinePage, component: TimelinePage },
  { definition: photoDetailPage, component: PhotoDetailPage },
  { definition: comparePage, component: ComparePage },
  { definition: researchPage, component: ResearchPage },
  { definition: methodologyPage, component: MethodologyPage },
  { definition: reportPage, component: ReportPage },
  { definition: publicationsPage, component: PublicationsPage },
];

const groupLabels = {
  analytics: 'Аналитика',
  research: 'Исследование и контроль',
  output: 'Сборка результата',
} as const;

function pageIdFromHash(): PageId {
  if (typeof window === 'undefined') {
    return 'timeline';
  }

  const hash = window.location.hash.replace(/^#\/?/, '');
  const route = hash.split('?')[0];
  return pages.some(({ definition }) => definition.id === route) ? (route as PageId) : 'timeline';
}

function updateHash(pageId: PageId) {
  if (typeof window !== 'undefined' && window.location.hash !== `#/${pageId}`) {
    window.history.pushState(null, '', `#/${pageId}`);
  }
}

export function App() {
  const [activePageId, setActivePageId] = useState<PageId>(pageIdFromHash);
  const [locationKey, setLocationKey] = useState(() =>
    typeof window === 'undefined' ? '#/timeline' : window.location.hash || '#/timeline',
  );

  useEffect(() => {
    const handleNavigation = () => {
      setActivePageId(pageIdFromHash());
      setLocationKey(window.location.hash || '#/timeline');
    };
    window.addEventListener('hashchange', handleNavigation);
    window.addEventListener('popstate', handleNavigation);
    return () => {
      window.removeEventListener('hashchange', handleNavigation);
      window.removeEventListener('popstate', handleNavigation);
    };
  }, []);

  const activePage = useMemo(
    () => pages.find(({ definition }) => definition.id === activePageId) ?? pages[0],
    [activePageId],
  );
  const ActivePage = activePage.component;

  const navigate = (pageId: PageId) => {
    setActivePageId(pageId);
    updateHash(pageId);
    setLocationKey(`#/${pageId}`);
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="wordmark" href="#/timeline" onClick={() => navigate('timeline')}>
          DEEPUTIN <span>/ FORENSIC WORKBENCH</span>
        </a>

        <nav className="top-navigation" aria-label="Разделы рабочей станции">
          <ul className="top-navigation-list">
            {pages.map(({ definition }) => {
              const isActive = definition.id === activePageId;
              return (
                <li key={definition.id}>
                  <button
                    className="nav-button"
                    type="button"
                    aria-current={isActive ? 'page' : undefined}
                    onClick={() => navigate(definition.id)}
                  >
                    {definition.title}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="topbar-status" aria-label="Режим интерфейса">
          <span className="status-dot" aria-hidden="true" />
          <span>SOURCE ON DEMAND</span>
          <span className="topbar-divider" aria-hidden="true" />
          <span>NOT A VERDICT</span>
        </div>
      </header>

      <div className="workspace">
        <main className="content">
          <div className="page-bar">
            <div>
              <p className="micro-label">{groupLabels[activePage.definition.group]}</p>
              <h1>{activePage.definition.title}</h1>
            </div>
            <div className="page-bar-meta">
              <span className="page-key">route: {activePage.definition.id}</span>
              <span className="page-state">ON-DEMAND DATA</span>
            </div>
          </div>
          <ActivePage key={locationKey} />
        </main>
      </div>
    </div>
  );
}
