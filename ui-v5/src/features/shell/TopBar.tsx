import React, { useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import * as Slider from "@radix-ui/react-slider";
import {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  Boxes,
  ChevronDown,
  Database,
  Eye,
  Filter,
  Flag,
  Gauge,
  Layers3,
  Moon,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { researchTimeline } from "../../shared/researchApi";

interface TopBarProps {
  activePose: string;
  onPoseChange: (pose: string) => void;
  qualityThreshold: number;
  onQualityThresholdChange: (val: number) => void;
  mouthThreshold: number;
  onMouthThresholdChange: (val: number) => void;
  poseAngleThreshold: number;
  onPoseAngleThresholdChange: (val: number) => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  activePose,
  onPoseChange,
  qualityThreshold,
  onQualityThresholdChange,
  mouthThreshold,
  onMouthThresholdChange,
  poseAngleThreshold,
  onPoseAngleThresholdChange,
}) => {
  const [poseMenuOpen, setPoseMenuOpen] = useState(false);
  const [metricsMenuOpen, setMetricsMenuOpen] = useState(false);
  const [findingsMenuOpen, setFindingsMenuOpen] = useState(false);
  const timelineQuery = useQuery({ queryKey: ["research-timeline"], queryFn: researchTimeline });
  const photos = timelineQuery.data?.photos ?? [];
  const findingKeys = new Set(["coherent_jump_candidate", "geometric_mismatch", "change_point", "rapid_rate"]);
  const findingCount = photos.filter((photo) => photo.flags.length > 0 || Object.entries(photo.stage2StatusCounts).some(([key, count]) => count > 0 && findingKeys.has(key))).length;
  const metricCount = ["quality", "yaw", "pitch", "roll"].filter((key) => photos.some((photo) => photo[key as keyof typeof photo] != null)).length;
  const metricRows = [
    ["Quality", "quality"],
    ["Yaw", "yaw"],
    ["Pitch", "pitch"],
    ["Roll", "roll"],
    ["Geometry / boneScore", "boneScore"],
    ["Texture diagnostics", "textureMean"],
  ] as const;

  const poses = Object.entries(photos.reduce<Record<string, number>>((out, photo) => { out[photo.bucket] = (out[photo.bucket] ?? 0) + 1; return out; }, {})).map(([id, count]) => ({ id, label: id.replaceAll("_", " "), count }));

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#1f2d3d] bg-[#080d12]/95 backdrop-blur px-4 py-2 text-[#e2e8f0]">
      <div className="flex items-center justify-between gap-2 text-xs">
        {/* Left: Brand + Run info */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-mono font-bold tracking-wider text-cyan-400">
            <ShieldCheck className="h-4 w-4" />
            <span>DEEPUTIN v5.0</span>
          </div>
          <span className="rounded bg-[#141e27] px-2 py-0.5 font-mono text-[11px] text-cyan-300 border border-[#1f2d3d]">
            {timelineQuery.isLoading ? "RUN: загрузка" : `STAGE 2 · ${photos.length.toLocaleString("ru-RU")} фото`}
          </span>
          <span className="rounded bg-emerald-950/80 px-2 py-0.5 font-mono text-[11px] text-emerald-300 border border-emerald-800">
            {timelineQuery.data?.source_mode ?? "нет источника"}
          </span>
        </div>

        {/* Center: Expandable Dropdown Menus on top of Timeline */}
        <div className="flex items-center gap-1.5">
          {/* Pose Dropdown */}
          <div className="relative">
            <button
              onClick={() => setPoseMenuOpen(!poseMenuOpen)}
              className="flex items-center gap-1.5 rounded bg-[#101820] px-2.5 py-1 text-[#cbd5e1] hover:bg-[#18232d] border border-[#1f2d3d]"
            >
              <Eye className="h-3.5 w-3.5 text-cyan-400" />
              <span>Ракурс: {activePose}</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>
            {poseMenuOpen && (
              <div className="absolute left-0 mt-1 w-64 rounded-md border border-[#1f2d3d] bg-[#0b1117] p-1 shadow-2xl z-50">
                <div className="px-2 py-1 text-[10px] font-mono uppercase text-slate-400">
                  Выбор 1 из 9 ракурсных корзин
                </div>
                {poses.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      onPoseChange(p.id);
                      setPoseMenuOpen(false);
                    }}
                    className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs ${
                      activePose === p.id ? "bg-cyan-950/80 text-cyan-300" : "hover:bg-[#141e27] text-slate-300"
                    }`}
                  >
                    <span>{p.label}</span>
                    <span className="font-mono text-[10px] text-slate-400">{p.count}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Metrics Dropdown */}
          <div className="relative">
            <button
              onClick={() => setMetricsMenuOpen(!metricsMenuOpen)}
              className="flex items-center gap-1.5 rounded bg-[#101820] px-2.5 py-1 text-[#cbd5e1] hover:bg-[#18232d] border border-[#1f2d3d]"
            >
              <Activity className="h-3.5 w-3.5 text-amber-400" />
              <span>Метрики {metricCount}/4</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>
            {metricsMenuOpen && (
              <div className="absolute left-0 mt-1 w-56 rounded-md border border-[#1f2d3d] bg-[#0b1117] p-2 shadow-2xl z-50">
                <div className="text-[10px] font-mono uppercase text-slate-400 mb-1">Доступность по Stage 2</div>
                {metricRows.map(([label, key]) => {
                  const available = photos.filter((photo) => photo[key as keyof typeof photo] != null).length;
                  return <div key={key} className="flex items-center justify-between gap-2 py-1 text-xs"><span className={available ? "text-slate-300" : "text-slate-500"}>{label}</span><span className={`font-mono ${available ? "text-emerald-400" : "text-amber-400"}`}>{available}/{photos.length}</span></div>;
                })}
                <div className="mt-2 border-t border-[#1f2d3d] pt-2 text-[10px] text-amber-300">Недоступные поля не заменяются демонстрационными значениями.</div>
              </div>
            )}
          </div>

          {/* Filters Overlay Popover (Real-time Sliders over screen) */}
          <Popover.Root>
            <Popover.Trigger asChild>
              <button className="flex items-center gap-1.5 rounded bg-[#101820] px-2.5 py-1 text-[#cbd5e1] hover:bg-[#18232d] border border-cyan-800/80">
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
                    Панель калибровки в реальном времени
                  </span>
                      <span className="text-[10px] text-slate-400">значения из API</span>
                </div>

                <div className="space-y-4">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-300">Минимальное качество (Q):</span>
                      <span className="font-mono text-cyan-400">{Math.round(qualityThreshold * 100)}%</span>
                    </div>
                    <Slider.Root
                      className="relative flex h-5 w-full select-none items-center"
                      value={[qualityThreshold]}
                      onValueChange={(vals) => onQualityThresholdChange(vals[0])}
                      max={1}
                      min={0}
                      step={0.05}
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
                      onValueChange={(vals) => onMouthThresholdChange(vals[0] / 100)}
                      max={50}
                      min={10}
                      step={5}
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
                      onValueChange={(vals) => onPoseAngleThresholdChange(vals[0])}
                      max={12}
                      min={2}
                      step={1}
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

          {/* Findings Dropdown */}
          <div className="relative">
            <button
              onClick={() => setFindingsMenuOpen(!findingsMenuOpen)}
              className="flex items-center gap-1.5 rounded bg-[#101820] px-2.5 py-1 text-[#cbd5e1] hover:bg-[#18232d] border border-[#1f2d3d]"
            >
              <Flag className="h-3.5 w-3.5 text-rose-400" />
              <span>Находки {findingCount} ⚑</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>
            {findingsMenuOpen && (
              <div className="absolute left-0 mt-1 w-64 rounded-md border border-[#1f2d3d] bg-[#0b1117] p-2 shadow-2xl z-50">
                <div className="text-[10px] font-mono uppercase text-slate-400 mb-1.5">Маркеры аномалий</div>
                <div className="space-y-1.5 text-xs text-slate-300">
                  <div className="flex items-center justify-between"><span className="flex items-center gap-1.5"><span className="inline-block h-2 w-2 rounded-full bg-rose-500" />Flags / review</span><span className="font-mono text-rose-400">{photos.filter((photo) => photo.flags.length > 0).length}</span></div>
                  <div className="flex items-center justify-between"><span className="flex items-center gap-1.5"><span className="inline-block h-2 w-2 rounded-full bg-amber-500" />Coherent jump</span><span className="font-mono text-amber-400">{photos.filter((photo) => (photo.stage2StatusCounts.coherent_jump_candidate ?? 0) > 0).length}</span></div>
                  <div className="flex items-center justify-between"><span className="flex items-center gap-1.5"><span className="inline-block h-2 w-2 rounded-full bg-purple-500" />Geometry mismatch</span><span className="font-mono text-purple-400">{photos.filter((photo) => (photo.stage2StatusCounts.geometric_mismatch ?? 0) > 0).length}</span></div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Scrollable Quick Page Links for all 12 modules */}
        <nav className="flex items-center gap-0.5 overflow-x-auto max-w-xl text-[11px]">
          <Link
            to="/overview"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Обзор
          </Link>
          <Link
            to="/timeline"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Таймлайн
          </Link>
          <Link
            to="/data-manager"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Данные
          </Link>
          <Link
            to="/inspector"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Инспектор
          </Link>
          <Link
            to="/morphing"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Морфинг
          </Link>
          <Link
            to="/pair-analysis"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Сравнение
          </Link>
          <Link
            to="/clustering"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Кластеры
          </Link>
          <Link
            to="/calibration"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Калибровка
          </Link>
          <Link
            to="/hypotheses"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Гипотезы
          </Link>
          <Link
            to="/reports"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Отчеты
          </Link>
          <Link
            to="/articles"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Статьи
          </Link>
          <Link
            to="/monetization"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Монетизация
          </Link>
          <Link
            to="/audit"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            Аудит
          </Link>
          <Link
            to="/design-system"
            className="rounded px-2 py-1 text-slate-300 hover:bg-[#141e27] hover:text-white transition whitespace-nowrap"
            activeProps={{ className: "bg-cyan-950 text-cyan-300 border border-cyan-800" }}
          >
            UI-v5
          </Link>
        </nav>
      </div>
    </header>
  );
};
