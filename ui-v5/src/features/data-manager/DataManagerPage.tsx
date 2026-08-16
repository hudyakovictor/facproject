import React, { useState } from "react";
import { useTimeline } from "../../shared/api/queries";
import { type ResearchPhoto } from "../../shared/researchApi";
import { poseLabel, sortPoseBins } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";
import {
  UploadCloud,
  Search,
  Check,
} from "lucide-react";

interface DataRow {
  id: string;
  timestamp: string;
  year: number | null;
  poseBin: string;
  qualityQ: number | null;
  yaw: number | null;
  sourceUrl: string;
  sha256: string;
  filename: string;
  exifMatch: boolean;
  era: string;
  poseCode: string;
  hasSidecar: boolean;
  shaMatch: boolean;
  flagMessage?: string;
  flagTone?: "error" | "warn" | "neutral";
}

export const DataManagerPage: React.FC = () => {
  const [selectedRow, setSelectedRow] = useState<DataRow | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [filterPose, setFilterPose] = useState<string>("ALL");
  const [page, setPage] = useState<number>(0);
  const [pageSize, setPageSize] = useState<number>(50);

  const timelineQuery = useTimeline();
  const stage = resolveStage(timelineQuery.data);
  const rows: DataRow[] = (timelineQuery.data?.photos ?? []).map((p: ResearchPhoto) => {
    const isConflict = p.dateProvenanceStatus === "conflict";
    const noSidecar = p.analysisStage !== "stage2";
    return {
      id: p.id,
      timestamp: p.date ?? "дата отсутствует",
      year: p.date ? Number(p.date.slice(0, 4)) : null,
      poseBin: p.bucket,
      qualityQ: p.quality == null ? null : p.quality * 100,
      yaw: p.yaw,
      sourceUrl: `Stage 2 · ${p.sourceMode}`,
      sha256: "недоступен в API",
      filename: p.id,
      exifMatch: !isConflict,
      era: p.era,
      poseCode: p.bucket,
      hasSidecar: !noSidecar,
      shaMatch: false,
      flagMessage: isConflict
        ? "конфликт дат · EXIF ≠ имя"
        : p.flags.length
        ? p.flags.join(", ")
        : undefined,
      flagTone: isConflict ? "warn" : p.flags.length ? "error" : "neutral",
    };
  });

  const filteredRows = rows.filter((r) => {
    if (filterPose !== "ALL" && r.poseBin !== filterPose) return false;
    if (searchQuery && !r.filename.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const pageCount = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const pageStart = safePage * pageSize;
  const pageRows = filteredRows.slice(pageStart, pageStart + pageSize);

  const poseOptions = sortPoseBins(Array.from(new Set(rows.map((row) => row.poseBin))));

  const activeRow = selectedRow || rows[0];

  if (timelineQuery.isLoading) return <LoadingState text="Загрузка каталога данных…" />;
  if (timelineQuery.error) return <ErrorState title="Каталог данных недоступен" error={timelineQuery.error} onRetry={() => void timelineQuery.refetch()} />;
  if (!activeRow) return <EmptyState title="Записей нет" description="API вернул пустой список фотографий. Проверьте, что Stage 1 выполнен и каталог данных смонтирован." />;

  return (
    <div className="flex flex-col h-[calc(100vh-49px)] w-full bg-[#080d12] text-[#e2e8f0] overflow-hidden select-none font-sans">
      {/* 1. TOP STATS & ACTION BAR (Matching 04-data-manager.png) */}
      <div className="border-b border-[#1f2d3d] bg-[#0b1117] px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="font-mono text-sm font-bold text-cyan-300 uppercase">
            DEEPUTIN V5 · ДАННЫЕ И PROVENANCE · {stageLabel(stage)}
          </div>

          <div className="flex items-center gap-2">
            <select
              aria-label="Фильтр по ракурсу"
              value={filterPose}
              onChange={(e) => { setFilterPose(e.target.value); setPage(0); }}
              className="rounded bg-[#141e27] px-2.5 py-1 font-mono text-xs text-slate-200 border border-[#1f2d3d]"
            >
              <option value="ALL">РАКУРС: ВСЕ</option>
              {poseOptions.map((pose: string) => (
                <option key={pose} value={pose}>{poseLabel(pose)}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className="rounded bg-[#141e27] px-3 py-1 font-mono text-xs text-slate-300 border border-[#1f2d3d]">
            {rows.length.toLocaleString("ru-RU")} фото · <strong className="text-amber-400">Stage 2</strong> ·{" "}
            <strong className="text-rose-400">{rows.filter((r) => r.flagMessage).length} флагов</strong>
          </span>

          <div className="flex items-center gap-2">
            <button className="rounded bg-[#101820] px-3 py-1 font-mono text-xs text-cyan-300 border border-cyan-800 hover:bg-[#18232d] transition">
              [импорт]
            </button>
            <button className="rounded bg-[#101820] px-3 py-1 font-mono text-xs text-emerald-300 border border-emerald-800 hover:bg-[#18232d] transition">
              [проверить provenance]
            </button>
            <button className="rounded bg-[#101820] px-3 py-1 font-mono text-xs text-amber-300 border border-amber-800 hover:bg-[#18232d] transition">
              [пересчитать]
            </button>
          </div>
        </div>
      </div>

      <div className="px-6 py-2"><StageBanner stage={stage} note={timelineQuery.data?.note} /></div>

      {/* 2. MAIN WORKSPACE: TABLE LEFT (70%) + SIDECAR DRAWER RIGHT (30%) */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT AREA: DATA TABLE (70%) */}
        <div className="w-[70%] border-r border-[#1f2d3d] flex flex-col justify-between overflow-hidden">
          {/* Dropzone top bar */}
          <div className="border-b border-[#1f2d3d]/60 bg-[#080d12] px-4 py-2 flex items-center justify-between text-xs text-slate-400 font-mono">
            <div className="flex items-center gap-2">
              <UploadCloud className="h-4 w-4 text-cyan-400" />
              <span>перетащите фото или sidecar .json</span>
            </div>
            <div className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                placeholder="Поиск по имени файла..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-[#101820] rounded px-2 py-0.5 text-xs text-white border border-[#1f2d3d] focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          {/* Table Container */}
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left font-mono text-xs border-collapse">
              <thead className="sticky top-0 bg-[#0b1117] border-b border-[#1f2d3d] text-slate-400 uppercase text-[11px]">
                <tr>
                  <th className="py-2 px-3">№</th>
                  <th className="py-2 px-3">ID</th>
                  <th className="py-2 px-3">дата из имени</th>
                  <th className="py-2 px-3">эпоха</th>
                  <th className="py-2 px-3">бин ракурса</th>
                  <th className="py-2 px-3">q</th>
                  <th className="py-2 px-3">yaw</th>
                  <th className="py-2 px-3">sidecar</th>
                  <th className="py-2 px-3">SHA</th>
                  <th className="py-2 px-3">флаги</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1f2d3d]/50">
                {pageRows.map((r, i) => {
                  const isSelected = activeRow.id === r.id;
                  return (
                    <tr
                      key={r.id}
                      onClick={() => setSelectedRow(r)}
                      className={`cursor-pointer transition-colors ${
                        isSelected ? "bg-cyan-950/50 text-white" : "hover:bg-[#101820] text-slate-300"
                      }`}
                    >
                      <td className="py-2.5 px-3 text-slate-500">{pageStart + i + 1}</td>
                      <td className="py-2.5 px-3 font-bold text-cyan-300">{r.filename}</td>
                      <td className="py-2.5 px-3">
                        <span className="flex items-center gap-1">
                          {r.timestamp}
                          {r.exifMatch && <Check className="h-3.5 w-3.5 text-emerald-400 inline" aria-label="Дата без конфликта источников" />}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{r.year ?? "н/д"}</td>
                      <td className="py-2.5 px-3 text-cyan-400 font-bold">{poseLabel(r.poseCode)}</td>
                      <td className="py-2.5 px-3">{r.qualityQ == null ? <span className="text-slate-500">н/д</span> : (r.qualityQ / 100).toFixed(2)}</td>
                      <td className="py-2.5 px-3">{r.yaw == null ? <span className="text-slate-500">н/д</span> : r.yaw > 0 ? `+${r.yaw}°` : `${r.yaw}°`}</td>
                      <td className="py-2.5 px-3">
                        {r.hasSidecar ? (
                          <Check className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <span className="text-slate-500">н/д</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        {r.shaMatch ? (
                          <Check className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <span className="text-slate-500">н/д</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        {r.flagMessage ? (
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                              r.flagTone === "warn"
                                ? "bg-amber-950 text-amber-300 border border-amber-800"
                                : "bg-rose-950 text-rose-300 border border-rose-800"
                            }`}
                          >
                            {r.flagMessage}
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Footer — реальная, а не декоративная */}
          <div className="border-t border-[#1f2d3d] bg-[#0b1117] px-4 py-2 flex items-center justify-between font-mono text-xs text-slate-400">
            <span>
              {filteredRows.length === 0
                ? "0 записей"
                : `${(pageStart + 1).toLocaleString("ru-RU")}–${Math.min(pageStart + pageSize, filteredRows.length).toLocaleString("ru-RU")} из ${filteredRows.length.toLocaleString("ru-RU")}`}
            </span>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage(0)} disabled={safePage === 0} aria-label="Первая страница" className="hover:text-white px-1.5 py-0.5 rounded border border-[#1f2d3d] bg-[#101820] disabled:opacity-40">|&lt;&lt;</button>
              <button onClick={() => setPage((v) => Math.max(0, v - 1))} disabled={safePage === 0} aria-label="Предыдущая страница" className="hover:text-white px-1.5 py-0.5 rounded border border-[#1f2d3d] bg-[#101820] disabled:opacity-40">&lt;</button>
              <span className="text-cyan-300 font-bold">{safePage + 1}</span>
              <span>из</span>
              <span>{pageCount}</span>
              <button onClick={() => setPage((v) => Math.min(pageCount - 1, v + 1))} disabled={safePage >= pageCount - 1} aria-label="Следующая страница" className="hover:text-white px-1.5 py-0.5 rounded border border-[#1f2d3d] bg-[#101820] disabled:opacity-40">&gt;</button>
              <button onClick={() => setPage(pageCount - 1)} disabled={safePage >= pageCount - 1} aria-label="Последняя страница" className="hover:text-white px-1.5 py-0.5 rounded border border-[#1f2d3d] bg-[#101820] disabled:opacity-40">&gt;&gt;|</button>
            </div>
            <label className="flex items-center gap-2">
              <span>на странице</span>
              <select
                aria-label="Записей на странице"
                value={pageSize}
                onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
                className="rounded bg-[#101820] px-2 py-0.5 text-cyan-300 border border-[#1f2d3d]"
              >
                {[25, 50, 100, 200].map((size) => <option key={size} value={size}>{size}</option>)}
              </select>
            </label>
          </div>
        </div>

        {/* RIGHT AREA: SIDECAR INSPECTOR DRAWER (30%) - Matching 04-data-manager.png */}
        <div className="w-[30%] bg-[#0b1117] flex flex-col justify-between overflow-y-auto p-5 space-y-4">
          {/* Drawer Header */}
          <div className="flex items-center justify-between border-b border-[#1f2d3d] pb-2 font-mono text-xs">
            <span className="font-bold text-cyan-300">{activeRow.filename}</span>
            <button className="text-slate-500 hover:text-white transition">✕</button>
          </div>

          {/* Historical Preview Silhouette Image */}
          <div className="h-44 rounded bg-[#101820] border border-[#1f2d3d] overflow-hidden flex flex-col items-center justify-center relative p-3">
            <div className="w-full h-full rounded-sm bg-gradient-to-b from-[#18232d] via-[#101820] to-[#080d12] flex flex-col items-center justify-center relative">
              <span className="font-mono text-sm font-bold text-slate-200 uppercase">
                АРХИВНОЕ ПРЕВЬЮ
              </span>
              <span className="font-mono text-xs text-cyan-400 mt-1">{activeRow.timestamp}</span>
              <span className="font-mono text-[10px] text-slate-500 mt-1">{activeRow.sourceUrl}</span>
            </div>
          </div>

          {/* SIDECAR METADATA TABLE */}
          <div className="space-y-3">
            <div className="font-mono text-xs font-bold text-slate-300 uppercase">
              SIDECAR ({activeRow.filename.replace(".jpg", ".json")})
            </div>

            <div className="space-y-1.5 font-mono text-[11px] text-slate-300 border-b border-[#1f2d3d] pb-3">
              <div className="flex justify-between">
                <span className="text-slate-500">source_url</span>
                <span className="text-cyan-400 truncate max-w-[160px]">{activeRow.sourceUrl}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">acquired_at</span>
                <span className="text-slate-500">недоступен в API</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">collector</span>
                <span className="text-slate-500">недоступен в API</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">claimed_date</span>
                <span className="text-emerald-400 font-bold">{activeRow.timestamp}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">rights</span>
                <span className="text-slate-500">недоступно в API</span>
              </div>
            </div>

            {/* HASHES SECTION */}
            <div className="space-y-2">
              <div className="font-mono text-xs font-bold text-slate-300 uppercase">ХЕШИ</div>
              <div className="space-y-1 font-mono text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">image SHA-256</span>
                  <span className="text-slate-500 font-bold flex items-center gap-1">
                    {activeRow.sha256}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">sidecar SHA-256</span>
                  <span className="text-slate-500 font-bold flex items-center gap-1">
                    недоступен в API
                  </span>
                </div>
              </div>
            </div>

            {/* FLAGS SECTION */}
            <div className="space-y-2 pt-2 border-t border-[#1f2d3d]">
              <div className="font-mono text-xs font-bold text-slate-300 uppercase">ФЛАГИ</div>
              <div>
                {activeRow.flagMessage ? (
                  <span className="rounded bg-amber-950 px-2 py-1 font-mono text-[10px] text-amber-300 border border-amber-800">
                    {activeRow.flagMessage}
                  </span>
                ) : <span className="text-slate-500 font-mono text-[11px]">нет флагов</span>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
