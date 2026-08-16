import { useState } from "react";
import { Layers } from "lucide-react";
import { Link, useLocation } from "@tanstack/react-router";
import { useTimeline } from "../../shared/api/queries";
import { isFinding } from "../../shared/findings";
import { POSE_BINS } from "../../shared/poseBins";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { NAV_ROUTES } from "../../app/navigation";

const TRIGGER =
  "flex items-center gap-1.5 rounded bg-surface-raised px-2.5 py-1 text-ink-secondary hover:bg-surface-subtle border border-line-default";

/**
 * Верхняя панель рабочей станции.
 *
 * Панель больше не получает состояние пропсами из `RootLayout`: раньше выбор
 * ракурса и три порога жили в `useState` родителя и опускались только сюда, а
 * страницы вели собственные одноимённые `useState`. Управление в шапке при этом
 * не влияло ни на один экран (BUG-1). Теперь единственный источник истины —
 * `useAnalysisStore`, который читают и панель, и страницы.
 */
export function TopBar() {
  const [poseMenuOpen, setPoseMenuOpen] = useState(false);
  const [findingsMenuOpen, setFindingsMenuOpen] = useState(false);
  const location = useLocation();

  const timelineQuery = useTimeline();
  const photos = timelineQuery.data?.photos ?? [];

  const {
    activePose,
    setActivePose,
    multiPose,
    setMultiPose,
    findingsMode,
    setFindingsMode,
  } = useAnalysisStore();

  /** Счётчики по каноническим девяти бинам, включая пустые: отсутствие кадров
   *  в бине — это тоже факт о датасете, скрывать его нельзя. */
  const counts = photos.reduce<Record<string, number>>((out, photo) => {
    out[photo.bucket] = (out[photo.bucket] ?? 0) + 1;
    return out;
  }, {});
  const unknownBins = Object.keys(counts).filter(
    (id) => !POSE_BINS.some((bin) => bin.id === id),
  );

  return (
    <header className="sticky top-0 z-50 w-full border-b border-line-default bg-surface-canvas px-3 py-1.5 text-ink-primary backdrop-blur">
      <div className="flex min-w-0 items-center gap-2 text-xs">
        <div className="flex shrink-0 items-center font-mono font-bold tracking-wider text-cyan-400">
          <span>DEEPUTIN</span>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {/* Ракурс */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setPoseMenuOpen(!poseMenuOpen)}
              aria-expanded={poseMenuOpen}
              className={`${TRIGGER} px-2 py-1`}
              title="Выбор ракурсной корзины"
            >
              <span>Ракурс</span>
            </button>
            {poseMenuOpen && (
              <div role="group" aria-label="Выбор ракурса" className="absolute left-0 mt-1 w-72 rounded-md border border-line-default bg-surface-base p-1 shadow-2xl z-50">
                <div className="px-2 py-1 text-[10px] font-mono uppercase text-ink-muted">
                  Выбор 1 из 9 ракурсных корзин
                </div>
                {POSE_BINS.map((bin) => {
                  const count = counts[bin.id] ?? 0;
                  return (
                    <button
                      key={bin.id}
                      type="button"
                      disabled={count === 0}
                      onClick={() => {
                        setActivePose(bin.id);
                        setMultiPose(false);
                        setPoseMenuOpen(false);
                      }}
                      className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs ${
                        !multiPose && activePose === bin.id
                          ? "bg-cyan-soft text-cyan-300"
                          : "hover:bg-surface-overlay text-ink-secondary"
                      }`}
                    >
                      <span>{bin.fullLabel}</span>
                      <span
                        className={`font-mono text-[10px] ${count ? "text-ink-muted" : "text-ink-disabled"}`}
                      >
                        {count}
                      </span>
                    </button>
                  );
                })}
                {unknownBins.length > 0 && (
                  <div className="mt-1 border-t border-line-default pt-1 px-2 py-1 text-[10px] text-amber-300">
                    Вне справочника: {unknownBins.join(", ")}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setMultiPose(true);
                    setPoseMenuOpen(false);
                  }}
                  className={`mt-1 flex w-full items-center gap-1.5 rounded border-t border-line-default px-2 py-1.5 text-left text-xs ${
                    multiPose ? "bg-cyan-soft text-cyan-300" : "hover:bg-surface-overlay text-ink-secondary"
                  }`}
                >
                  <Layers className="h-3 w-3" />
                  Показать все бины
                </button>
                <div className="px-2 pb-1 pt-1 text-[10px] text-ink-muted">
                  Сравнение пары A/B остаётся внутри одного бина.
                </div>
              </div>
            )}
          </div>

          {/* Находки */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setFindingsMenuOpen(!findingsMenuOpen)}
              aria-expanded={findingsMenuOpen}
              className={`${TRIGGER} ${findingsMode ? "border-red-500 bg-red-soft" : ""}`}
            >
              <span>Находки</span>
            </button>
            {findingsMenuOpen && (
              <div className="absolute right-0 mt-1 w-72 rounded-md border border-line-default bg-surface-base p-2 shadow-2xl z-50">
                <div className="text-[10px] font-mono uppercase text-ink-muted mb-1.5">
                  Маркеры, требующие проверки
                </div>
                <div className="space-y-1.5 text-xs text-ink-secondary">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
                      Кадров с находками
                    </span>
                    <span className="font-mono text-red-400">
                      {photos.filter(isFinding).length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
                      Coherent jump
                    </span>
                    <span className="font-mono text-amber-400">
                      {
                        photos.filter(
                          (photo) => (photo.stage2StatusCounts?.coherent_jump_candidate ?? 0) > 0,
                        ).length
                      }
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-2 rounded-full bg-violet-400" />
                      Geometry mismatch
                    </span>
                    <span className="font-mono text-violet-400">
                      {
                        photos.filter(
                          (photo) => (photo.stage2StatusCounts?.geometric_mismatch ?? 0) > 0,
                        ).length
                      }
                    </span>
                  </div>
                </div>
                <label className="mt-2 flex cursor-pointer items-center gap-2 border-t border-line-default pt-2 text-xs text-ink-secondary">
                  <input
                    type="checkbox"
                    checked={findingsMode}
                    onChange={(event) => setFindingsMode(event.target.checked)}
                    className="accent-red-500"
                  />
                  Режим находок: приглушать остальные кадры
                </label>
                <div className="pt-1 text-[10px] text-ink-muted">
                  Маркер означает приоритет проверки, а не вывод о личности.
                </div>
              </div>
            )}
          </div>
        </div>

        <nav aria-label="Разделы" className="ml-auto flex min-w-0 items-center gap-1 overflow-x-auto text-[11px]">
          {NAV_ROUTES.some((route) => route.to === location.pathname) && (
            <span className="shrink-0 rounded border border-cyan-600 bg-cyan-soft px-2 py-1 text-cyan-300 whitespace-nowrap" aria-current="page">
              {NAV_ROUTES.find((route) => route.to === location.pathname)?.label}
            </span>
          )}
          {NAV_ROUTES.filter((route) => route.to !== location.pathname).map((route) => (
            <Link
              key={route.to}
              to={route.to}
              className="shrink-0 rounded px-2 py-1 text-ink-muted hover:bg-surface-overlay hover:text-ink-primary whitespace-nowrap"
            >
              {route.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
