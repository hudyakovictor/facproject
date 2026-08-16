import { useState } from "react";
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
import { POSE_BINS, poseFullLabel } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { useAnalysisStore, type MetricKey } from "../../shared/state/analysisStore";
import { PipelineChips } from "./PipelineChips";
import { NAV_ROUTES } from "../../app/navigation";

const METRIC_ROWS: Array<[MetricKey, string, string]> = [
  ["quality", "Quality", "quality"],
  ["yaw", "Yaw", "yaw"],
  ["pitch", "Pitch", "pitch"],
  ["roll", "Roll", "roll"],
  ["boneScore", "Geometry / boneScore", "boneScore"],
  ["confidence", "Confidence", "confidence"],
];

const TRIGGER =
  "flex items-center gap-1.5 rounded bg-[#101820] px-2.5 py-1 text-[#cbd5e1] hover:bg-[#18232d] border border-[#1f2d3d]";

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
  const stage = resolveStage(timelineQuery.data);
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
    toggleMetric,
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
    <header className="sticky top-0 z-50 w-full border-b border-[#1f2d3d] bg-[#080d12]/95 backdrop-blur px-4 py-2 text-[#e2e8f0]">
      <div className="flex items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-mono font-bold tracking-wider text-cyan-400">
            <ShieldCheck className="h-4 w-4" />
            <span>DEEPUTIN v5.0</span>
          </div>
          {/*
            Метка стадии выводится из ответа API. Раньше здесь была строковая
            константа «STAGE 2», которая подписывала так и инвентарь Stage 1.
          */}
          <span className="rounded bg-[#141e27] px-2 py-0.5 font-mono text-[11px] text-cyan-300 border border-[#1f2d3d]">
            {timelineQuery.isLoading
              ? "RUN: загрузка"
              : `${stageLabel(stage)} · ${photos.length.toLocaleString("ru-RU")} фото`}
          </span>
          <PipelineChips />
        </div>

        <div className="flex items-center gap-1.5">
          {/* Ракурс */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setPoseMenuOpen(!poseMenuOpen)}
              aria-expanded={poseMenuOpen}
              className={TRIGGER}
            >
              <Eye className="h-3.5 w-3.5 text-cyan-400" />
              <span>Ракурс: {multiPose ? "все бины" : poseFullLabel(activePose)}</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>
            {poseMenuOpen && (
              <div className="absolute left-0 mt-1 w-72 rounded-md border border-[#1f2d3d] bg-[#0b1117] p-1 shadow-2xl z-50">
                <div className="px-2 py-1 text-[10px] font-mono uppercase text-slate-400">
                  Выбор 1 из 9 ракурсных корзин
                </div>
                {POSE_BINS.map((bin) => {
                  const count = counts[bin.id] ?? 0;
                  return (
                    <button
                      key={bin.id}
                      type="button"
                      onClick={() => {
                        setActivePose(bin.id);
                        setMultiPose(false);
                        setPoseMenuOpen(false);
                      }}
                      className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs ${
                        !multiPose && activePose === bin.id
                          ? "bg-cyan-950/80 text-cyan-300"
                          : "hover:bg-[#141e27] text-slate-300"
                      }`}
                    >
                      <span>{bin.fullLabel}</span>
                      <span
                        className={`font-mono text-[10px] ${count ? "text-slate-400" : "text-slate-600"}`}
                      >
                        {count}
                      </span>
                    </button>
                  );
                })}
                {unknownBins.length > 0 && (
                  <div className="mt-1 border-t border-[#1f2d3d] pt-1 px-2 py-1 text-[10px] text-amber-300">
                    Вне справочника: {unknownBins.join(", ")}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setMultiPose(true);
                    setPoseMenuOpen(false);
                  }}
                  className={`mt-1 flex w-full items-center gap-1.5 rounded border-t border-[#1f2d3d] px-2 py-1.5 text-left text-xs ${
                    multiPose ? "bg-cyan-950/80 text-cyan-300" : "hover:bg-[#141e27] text-slate-300"
                  }`}
                >
                  <Layers className="h-3 w-3" />
                  Показать все бины
                </button>
                <div className="px-2 pb-1 pt-1 text-[10px] text-slate-500">
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
              className={TRIGGER}
            >
              <Activity className="h-3.5 w-3.5 text-amber-400" />
              <span>
                Метрики {visibleMetrics.length}/{METRIC_ROWS.length}
              </span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>
            {metricsMenuOpen && (
              <div className="absolute left-0 mt-1 w-72 rounded-md border border-[#1f2d3d] bg-[#0b1117] p-2 shadow-2xl z-50">
                <div className="text-[10px] font-mono uppercase text-slate-400 mb-1">
                  Дорожки и доступность в ответе API
                </div>
                {METRIC_ROWS.map(([key, label, field]) => {
                  const available = photos.filter(
                    (photo) => photo[field as keyof typeof photo] != null,
                  ).length;
                  const checked = visibleMetrics.includes(key);
                  return (
                    <label
                      key={key}
                      className="flex cursor-pointer items-center justify-between gap-2 rounded px-1 py-1 text-xs hover:bg-[#141e27]"
                    >
                      <span className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={available === 0}
                          onChange={() => toggleMetric(key)}
                          className="accent-cyan-500"
                        />
                        <span className={available ? "text-slate-300" : "text-slate-500"}>
                          {label}
                        </span>
                      </span>
                      <span
                        className={`font-mono ${available ? "text-emerald-400" : "text-amber-400"}`}
                      >
                        {available}/{photos.length}
                      </span>
                    </label>
                  );
                })}
                <div className="mt-2 border-t border-[#1f2d3d] pt-2 text-[10px] text-amber-300">
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
                className="flex items-center gap-1.5 rounded bg-[#101820] px-2.5 py-1 text-[#cbd5e1] hover:bg-[#18232d] border border-cyan-800/80"
              >
                <SlidersHorizontal className="h-3.5 w-3.5 text-cyan-400" />
                <span>Фильтры и пороги</span>
              </button>
            </Popover.Trigger>
            <Popover.Portal>
              <Popover.Content
                className="w-80 rounded-lg border border-[#1f2d3d] bg-[#0b1117]/95 p-4 shadow-2xl backdrop-blur z-50 text-slate-200"
                sideOffset={8}
              >
                <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 mb-3">
                  <span className="font-mono text-xs font-bold text-cyan-300 uppercase">
                    Пороги отображения
                  </span>
                  <span className="text-[10px] text-slate-400">применяются ко всем экранам</span>
                </div>

                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-300">Минимальное качество (Q):</span>
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
                      <Slider.Track className="relative h-1.5 w-full grow rounded-full bg-[#1f2d3d]">
                        <Slider.Range className="absolute h-full rounded-full bg-cyan-500" />
                      </Slider.Track>
                      <Slider.Thumb className="block h-4 w-4 rounded-full bg-cyan-300 shadow-md hover:bg-white focus:outline-none" />
                    </Slider.Root>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-300">Порог активности рта:</span>
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
                      <Slider.Track className="relative h-1.5 w-full grow rounded-full bg-[#1f2d3d]">
                        <Slider.Range className="absolute h-full rounded-full bg-amber-500" />
                      </Slider.Track>
                      <Slider.Thumb className="block h-4 w-4 rounded-full bg-amber-300 shadow-md hover:bg-white focus:outline-none" />
                    </Slider.Root>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-300">Допуск угла Yaw/Pitch:</span>
                      <span className="font-mono text-emerald-400">≤ {poseAngleThreshold}°</span>
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
                      <Slider.Track className="relative h-1.5 w-full grow rounded-full bg-[#1f2d3d]">
                        <Slider.Range className="absolute h-full rounded-full bg-emerald-500" />
                      </Slider.Track>
                      <Slider.Thumb className="block h-4 w-4 rounded-full bg-emerald-300 shadow-md hover:bg-white focus:outline-none" />
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
              className={`${TRIGGER} ${findingsMode ? "border-rose-700 bg-rose-950/50" : ""}`}
            >
              <Flag className="h-3.5 w-3.5 text-rose-400" />
              <span>Находки {findingCount} ⚑</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>
            {findingsMenuOpen && (
              <div className="absolute right-0 mt-1 w-72 rounded-md border border-[#1f2d3d] bg-[#0b1117] p-2 shadow-2xl z-50">
                <div className="text-[10px] font-mono uppercase text-slate-400 mb-1.5">
                  Маркеры, требующие проверки
                </div>
                <div className="space-y-1.5 text-xs text-slate-300">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-2 rounded-full bg-rose-500" />
                      Кадров с находками
                    </span>
                    <span className="font-mono text-rose-400">
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
                      <span className="inline-block h-2 w-2 rounded-full bg-purple-500" />
                      Geometry mismatch
                    </span>
                    <span className="font-mono text-purple-400">
                      {
                        photos.filter(
                          (photo) => (photo.stage2StatusCounts?.geometric_mismatch ?? 0) > 0,
                        ).length
                      }
                    </span>
                  </div>
                </div>
                <label className="mt-2 flex cursor-pointer items-center gap-2 border-t border-[#1f2d3d] pt-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={findingsMode}
                    onChange={(event) => setFindingsMode(event.target.checked)}
                    className="accent-rose-500"
                  />
                  Режим находок: приглушать остальные кадры
                </label>
                <div className="pt-1 text-[10px] text-slate-500">
                  Маркер означает приоритет проверки, а не вывод о личности.
                </div>
              </div>
            )}
          </div>
        </div>

        <nav className="flex items-center gap-0.5 overflow-x-auto max-w-xl text-[11px]">
          {NAV_ROUTES.map((route) => (
            <Link
              key={route.to}
              to={route.to}
              className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
              activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
            >
              {route.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
