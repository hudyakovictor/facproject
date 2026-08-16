import { useRef, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import * as Slider from "@radix-ui/react-slider";
import {
  Activity,
  ChevronDown,
  Eye,
  Flag,
  Layers,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useTimeline } from "../../shared/api/queries";
import { countFindings, isFinding } from "../../shared/findings";
import { POSE_BINS, poseFullLabel, poseLabel } from "../../shared/poseBins";
import { METRIC_CATALOG, availabilityOf } from "../../shared/metrics";
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
  const [metricsMenuOpen, setMetricsMenuOpen] = useState(false);
  const [findingsMenuOpen, setFindingsMenuOpen] = useState(false);

  const timelineQuery = useTimeline();
  const photos = timelineQuery.data?.photos ?? [];
  const findingCount = countFindings(photos);

  const {
    activePose,
    setActivePose,
    multiPose,
    setMultiPose,
    qualityThreshold,
    setQualityThreshold,
    mouthThreshold,
    setMouthThreshold,
    poseAngleThreshold,
    setPoseAngleThreshold,
    findingsMode,
    setFindingsMode,
    visibleMetrics,
    setVisibleMetrics,
    toggleMetric,
  } = useAnalysisStore();

  const beforeSoloRef = useRef<string[] | null>(null);
  const soloMetric = (id: string) => {
    if (visibleMetrics.length === 1 && visibleMetrics[0] === id && beforeSoloRef.current) {
      setVisibleMetrics(beforeSoloRef.current);
      beforeSoloRef.current = null;
      return;
    }
    beforeSoloRef.current = [...visibleMetrics];
    setVisibleMetrics([id]);
  };
  const moveMetric = (id: string, delta: number) => {
    const index = visibleMetrics.indexOf(id);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= visibleMetrics.length) return;
    const next = [...visibleMetrics];
    [next[index], next[target]] = [next[target], next[index]];
    setVisibleMetrics(next);
  };

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
        <div className="flex shrink-0 items-center gap-1.5 font-mono font-bold tracking-wider text-cyan-400">
          <ShieldCheck className="h-4 w-4" />
          <span>DEEPUTIN v5</span>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {/* Ракурс */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setPoseMenuOpen(!poseMenuOpen)}
              aria-expanded={poseMenuOpen}
            className={`${TRIGGER} px-2 py-1`}
            title={`Ракурс: ${multiPose ? "все бины" : poseFullLabel(activePose)}`}
            >
              <Eye className="h-3.5 w-3.5 text-cyan-400" />
              <span>Ракурс</span>
              <span className="font-mono text-[10px] text-cyan-300">{multiPose ? "все" : poseLabel(activePose)}</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
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

          {/* Метрики */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setMetricsMenuOpen(!metricsMenuOpen)}
              aria-expanded={metricsMenuOpen}
            className={`${TRIGGER} px-2 py-1`}
            >
              <Activity className="h-3.5 w-3.5 text-amber-400" />
              <span>Метрики</span>
              <span className="font-mono text-[10px] text-amber-300">{visibleMetrics.length}/{METRIC_CATALOG.length}</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>
            {metricsMenuOpen && (
              <div role="group" aria-label="Выбор метрик" className="absolute left-0 mt-1 w-72 rounded-md border border-line-default bg-surface-base p-2 shadow-2xl z-50">
                <div className="text-[10px] font-mono uppercase text-ink-muted mb-1">
                  Дорожки и доступность в ответе API
                </div>
                {METRIC_CATALOG.map((metric) => {
                  const available = availabilityOf(metric, photos);
                  const { id: key, label } = metric;
                  const checked = visibleMetrics.includes(key);
                  return (
                    <div
                      key={key}
                      className="flex cursor-pointer items-center justify-between gap-2 rounded px-1 py-1 text-xs hover:bg-surface-overlay"
                    >
                      <label className="flex min-w-0 flex-1 items-center gap-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={available === 0}
                          onChange={() => toggleMetric(key)}
                          className="accent-cyan-500"
                        />
                        <span className={available ? "text-ink-secondary" : "text-ink-muted"}>
                          {label}
                        </span>
                      </label>
                      <span
                        className={`font-mono ${available ? "text-green-400" : "text-amber-400"}`}
                      >
                        {available}/{photos.length}
                      </span>
                      {checked && (
                        <>
                          <button
                            type="button"
                            aria-label={`Показать только ${label}`}
                            className="rounded px-1 text-[10px] text-cyan-300 hover:bg-cyan-soft disabled:cursor-not-allowed disabled:opacity-30"
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              soloMetric(key);
                            }}
                          >
                            solo
                          </button>
                          <button
                            type="button"
                            aria-label={`Опустить дорожку ${label}`}
                            disabled={visibleMetrics.indexOf(key) >= visibleMetrics.length - 1}
                            className="rounded px-1 text-[10px] text-ink-muted hover:bg-surface-overlay disabled:cursor-not-allowed disabled:opacity-30"
                            onClick={(event) => {
                              event.preventDefault();
                              event.stopPropagation();
                              moveMetric(key, 1);
                            }}
                          >
                            ↓
                          </button>
                        </>
                      )}
                    </div>
                  );
                })}
                <div className="mt-2 border-t border-line-default pt-2 text-[10px] text-amber-300">
                  Недоступные поля не заменяются демонстрационными значениями.
                </div>
              </div>
            )}
          </div>

          {/* Пороги */}
          <Popover.Root>
            <Popover.Trigger asChild>
              <button
                type="button"
                className="flex items-center gap-1.5 rounded bg-surface-raised px-2.5 py-1 text-ink-secondary hover:bg-surface-subtle border border-cyan-600"
              >
                <SlidersHorizontal className="h-3.5 w-3.5 text-cyan-400" />
                <span>Фильтры</span>
              </button>
            </Popover.Trigger>
            <Popover.Portal>
              <Popover.Content
                className="w-80 rounded-lg border border-line-default bg-surface-base p-4 shadow-2xl backdrop-blur z-50 text-ink-primary"
                sideOffset={8}
              >
                <div className="flex items-center justify-between border-b border-line-default pb-2 mb-3">
                  <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
                    Пороги отображения
                  </span>
                  <span className="text-[10px] text-ink-muted">применяются ко всем экранам</span>
                </div>

                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-ink-secondary">Минимальное качество (Q):</span>
                      <span className="font-mono text-cyan-400">
                        {Math.round(qualityThreshold * 100)}%
                      </span>
                    </div>
                    <Slider.Root
                      className="relative flex h-5 w-full select-none items-center"
                      value={[qualityThreshold]}
                      onValueChange={(vals) => setQualityThreshold(vals[0])}
                      max={1}
                      min={0}
                      step={0.05}
                      aria-label="Минимальное качество"
                    >
                      <Slider.Track className="relative h-1.5 w-full grow rounded-full bg-line-default">
                        <Slider.Range className="absolute h-full rounded-full bg-cyan-500" />
                      </Slider.Track>
                      <Slider.Thumb className="block h-4 w-4 rounded-full bg-cyan-300 shadow-md hover:bg-surface-raised focus:outline-none" />
                    </Slider.Root>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-ink-secondary">Порог активности рта:</span>
                      <span className="font-mono text-amber-400">{mouthThreshold.toFixed(2)}</span>
                    </div>
                    <Slider.Root
                      className="relative flex h-5 w-full select-none items-center"
                      value={[mouthThreshold * 100]}
                      onValueChange={(vals) => setMouthThreshold(vals[0] / 100)}
                      max={50}
                      min={10}
                      step={5}
                      aria-label="Порог активности рта"
                    >
                      <Slider.Track className="relative h-1.5 w-full grow rounded-full bg-line-default">
                        <Slider.Range className="absolute h-full rounded-full bg-amber-500" />
                      </Slider.Track>
                      <Slider.Thumb className="block h-4 w-4 rounded-full bg-amber-300 shadow-md hover:bg-surface-raised focus:outline-none" />
                    </Slider.Root>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-ink-secondary">Допуск угла Yaw/Pitch:</span>
                      <span className="font-mono text-green-400">≤ {poseAngleThreshold}°</span>
                    </div>
                    <Slider.Root
                      className="relative flex h-5 w-full select-none items-center"
                      value={[poseAngleThreshold]}
                      onValueChange={(vals) => setPoseAngleThreshold(vals[0])}
                      max={12}
                      min={2}
                      step={1}
                      aria-label="Допуск угла"
                    >
                      <Slider.Track className="relative h-1.5 w-full grow rounded-full bg-line-default">
                        <Slider.Range className="absolute h-full rounded-full bg-green-500" />
                      </Slider.Track>
                      <Slider.Thumb className="block h-4 w-4 rounded-full bg-green-300 shadow-md hover:bg-surface-raised focus:outline-none" />
                    </Slider.Root>
                  </div>
                </div>
              </Popover.Content>
            </Popover.Portal>
          </Popover.Root>

          {/* Находки */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setFindingsMenuOpen(!findingsMenuOpen)}
              aria-expanded={findingsMenuOpen}
              className={`${TRIGGER} ${findingsMode ? "border-red-500 bg-red-soft" : ""}`}
            >
              <Flag className="h-3.5 w-3.5 text-red-400" />
              <span>Находки</span>
              <span className="font-mono text-[10px] text-red-300">{findingCount}</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
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

        <nav aria-label="Разделы" className="min-w-0 flex-1 flex items-center gap-0.5 overflow-x-auto text-[11px]">
          {NAV_ROUTES.map((route) => (
            <Link
              key={route.to}
              to={route.to}
              className="rounded px-2 py-1 text-ink-secondary hover:bg-surface-overlay hover:text-ink-primary transition whitespace-nowrap"
              activeProps={{ className: "bg-cyan-soft text-cyan-300 border border-cyan-600" }}
            >
              {route.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
