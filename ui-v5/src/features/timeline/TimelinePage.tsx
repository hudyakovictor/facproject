import { useMemo, useRef, useState } from "react";
import { useTimeline } from "../../shared/api/queries";
import { Activity, ArrowLeftRight, Check, Filter, RefreshCw, Search, X } from "lucide-react";
import { type ResearchPhoto } from "../../shared/researchApi";
import { countFindings, isFinding, substantiveFlags } from "../../shared/findings";
import { poseLabel } from "../../shared/poseBins";
import { resolveStage, stageLabel } from "../../shared/stage";
import { StageBanner } from "../../shared/ui/StageBanner";
import { DataContractBanner } from "../../shared/ui/DataContractBanner";
import { EmptyState, ErrorState, LoadingState } from "../../shared/ui/states";
import { sortPhotosByTime } from "../../shared/time";
import { useAnalysisStore } from "../../shared/state/analysisStore";
import { PhotoImage } from "../../shared/ui/PhotoImage";
import { frameLabel, frameTitle } from "../../shared/blind";
import { METRIC_COLORS } from "../../shared/ui/tokenColors";

const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v));
const pct = (v: number | null | undefined) => v == null ? "н/д" : `${Math.round(v * 100)}%`;
const metric = (v: number | null | undefined) => v == null ? "н/д" : v.toFixed(1);

function photoTone(photo: ResearchPhoto) {
  if (substantiveFlags(photo).length) return "border-red-500 bg-red-soft";
  if (photo.evidenceState === "mixed") return "border-amber-500 bg-amber-soft";
  return "border-line-default bg-surface-base";
}

type Track = { key: "yaw" | "quality" | "pitch" | "roll"; label: string; range: string; color: string; value: (p: ResearchPhoto) => number | null; normalize: (v: number) => number };
const TRACKS: Track[] = [
  { key: "yaw", label: "POSE · YAW", range: "−90° · 0° · +90°", color: METRIC_COLORS.yaw, value: (p) => p.yaw, normalize: (v) => (v + 90) / 180 },
  { key: "quality", label: "QUALITY · Q", range: "0 · 0.5 · 1", color: METRIC_COLORS.quality, value: (p) => p.quality, normalize: (v) => v },
  { key: "pitch", label: "POSE · PITCH", range: "−45° · 0° · +45°", color: METRIC_COLORS.pitch, value: (p) => p.pitch, normalize: (v) => (v + 45) / 90 },
  { key: "roll", label: "POSE · ROLL", range: "−45° · 0° · +45°", color: METRIC_COLORS.roll, value: (p) => p.roll, normalize: (v) => (v + 45) / 90 },
];

/**
 * Экран таймлайна.
 *
 * Пропсы `activePose`/`qualityThreshold` убраны: их никто не передавал, и
 * умолчания «frontal»/0 маскировали разрыв — управление в верхней панели меняло
 * состояние родителя, а экран продолжал жить на значениях по умолчанию
 * (BUG-1). Теперь и панель, и экран читают один стор.
 */
export function TimelinePage() {
  const query = useTimeline();
  const viewportRef = useRef<HTMLDivElement>(null);
  const {
    activePose,
    qualityThreshold,
    search,
    setSearch,
    findingsMode,
    setFindingsMode,
    multiPose,
    setMultiPose,
    selectedPhoto: selected,
    setSelectedPhoto: setSelected,
    pairA: aId,
    pairB: bId,
    assignToPair,
    swapPair,
    clearPair,
    blindMode,
  } = useAnalysisStore();
  const [zoom, setZoom] = useState(1);

  const rawPhotos = useMemo(() => query.data?.photos ?? [], [query.data]);
  const stage = resolveStage(query.data);
  /**
   * Порядок задаём сами: полагаться на сортировку ответа нельзя, иначе шкала
   * инвертируется. Недатированные кадры выносим отдельно — приклеивать их к
   * началу шкалы значило бы утверждать дату, которой нет.
   */
  const { dated: photos, undated } = useMemo(() => sortPhotosByTime(rawPhotos), [rawPhotos]);
  const firstDate = photos[0]?.t ?? null;
  const lastDate = photos.at(-1)?.t ?? null;
  const dateRange = firstDate != null && lastDate != null ? Math.max(lastDate - firstDate, 1) : 1;
  const x = (photo: ResearchPhoto) =>
    firstDate == null || photo.t == null ? 0 : clamp((photo.t - firstDate) / dateRange, 0, 1);
  const filtered = useMemo(() => photos.filter((photo) => {
    const pose = multiPose || activePose === "all" || photo.bucket.toLowerCase() === activePose.toLowerCase();
    const q = search.toLowerCase();
    const text = [photo.id, photo.date, photo.bucket, photo.era, photo.fuzzy, ...photo.flags].join(" ").toLowerCase();
    return pose && (!q || text.includes(q)) && (photo.quality == null || photo.quality >= qualityThreshold);
  }), [photos, activePose, qualityThreshold, search, multiPose]);
  /**
   * Режим находок приглушает, а не скрывает (D23). Убирая кадры из вида,
   * интерфейс менял бы саму выборку: разрывы в шкале выглядели бы как отсутствие
   * съёмки, а не как результат фильтра. Приглушённые кадры остаются на месте и
   * читаются как контекст.
   */
  const dimmed = (photo: ResearchPhoto) => findingsMode && !isFinding(photo);
  /**
   * Слепой режим (§18.3): подписи заменяются псевдонимами, чтобы рецензент
   * оценивал геометрию, а не узнавал кадр по дате. Порядок псевдонимов берётся
   * из хронологии и потому устойчив между перерисовками.
   */
  const order = useMemo(() => new Map(photos.map((item, index) => [item.id, index])), [photos]);
  const label = (photo: ResearchPhoto) =>
    frameLabel({ id: photo.id, date: photo.date, order: order.get(photo.id) ?? 0 }, blindMode);
  const title = (photo: ResearchPhoto) =>
    frameTitle({ id: photo.id, date: photo.date, order: order.get(photo.id) ?? 0 }, blindMode);
  const selectedPhoto = photos.find((photo) => photo.id === selected) ?? null;
  const aPhoto = filtered.find((photo) => photo.id === aId) ?? null;
  const bPhoto = filtered.find((photo) => photo.id === bId) ?? null;
  const years = useMemo(() => Array.from(new Set(photos.map((p) => p.date?.slice(0, 4)).filter((y): y is string => Boolean(y)))), [photos]);
  const yearCounts = useMemo(() => years.map((year) => ({ year, count: photos.filter((p) => p.date?.startsWith(year)).length })), [photos, years]);
  const maxYearCount = Math.max(...yearCounts.map((item) => item.count), 1);
  const contentWidth = Math.max(1500, Math.round(1500 * zoom));
  const representative = filtered.length > 160 ? filtered.filter((_, i) => i % Math.ceil(filtered.length / 160) === 0) : filtered;

  /**
   * Инвариант 5 AGENTS.md: сравнивать можно только внутри одного бина ракурса.
   * Сама проверка живёт в сторе (`assignToPair`), чтобы её нельзя было обойти
   * назначением пары с другого экрана; здесь остаётся только показ причины.
   */
  const [pairRejection, setPairRejection] = useState<string | null>(null);
  const bucketOf = (id: string) => photos.find((item) => item.id === id)?.bucket;
  const selectPhoto = (photo: ResearchPhoto) => {
    setSelected(photo.id);
    setPairRejection(assignToPair(photo.id, photo.bucket, bucketOf));
  };
  const resetPair = () => {
    clearPair();
    setPairRejection(null);
  };
  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      setZoom((value) => clamp(value * (event.deltaY < 0 ? 1.18 : 0.86), 0.7, 8));
    } else {
      event.preventDefault();
      viewport.scrollLeft += event.deltaX || event.deltaY;
    }
  };

  const track = (item: Track) => {
    const points = filtered.map((photo) => {
      const value = item.value(photo);
      return value == null ? null : `${(x(photo) * 1000).toFixed(2)},${(92 - clamp(item.normalize(value), 0, 1) * 74).toFixed(2)}`;
    });
    const segments: string[] = [];
    let current: string[] = [];
    points.forEach((point) => { if (point) current.push(point); else if (current.length) { segments.push(current.join(" ")); current = []; } });
    if (current.length) segments.push(current.join(" "));
    return <div key={item.key} className="grid grid-cols-[138px_1fr] border-b border-line-subtle">
      <div className="flex h-[82px] flex-col justify-center border-r border-line-default bg-surface-canvas px-3 font-mono text-[10px] text-ink-muted"><span>{item.label}</span><span className="mt-1 text-[9px] text-ink-disabled">{item.range}</span></div>
      <div className="relative h-[82px] bg-[linear-gradient(90deg,var(--border-subtle)_1px,transparent_1px)] bg-[length:4%_100%]"><div className="absolute inset-x-0 top-1/2 border-t border-dashed border-line-subtle" /><svg className="absolute inset-0 h-full w-full" viewBox="0 0 1000 100" preserveAspectRatio="none"><g>{segments.map((path, i) => <polyline key={i} points={path} fill="none" stroke={item.color} strokeWidth="2" vectorEffect="non-scaling-stroke" />)}{filtered.map((photo) => { const value = item.value(photo); if (value == null) return null; return <circle key={photo.id} cx={x(photo) * 1000} cy={92 - clamp(item.normalize(value), 0, 1) * 74} r="3.2" fill="#081016" stroke={item.color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />; })}</g></svg></div>
    </div>;
  };

  if (query.isLoading) return <LoadingState text="Загрузка временной шкалы…" />;
  if (query.error) return <ErrorState title="Временная шкала недоступна" error={query.error} onRetry={() => void query.refetch()} />;
  if (rawPhotos.length === 0)
    return (
      <EmptyState
        title="Записей нет"
        description="API вернул пустой список фотографий. Проверьте, что Stage 1 выполнен и каталог данных смонтирован."
      />
    );
  if (photos.length === 0)
    return (
      <EmptyState
        title="Ни у одной записи нет даты"
        description={`Получено ${rawPhotos.length.toLocaleString("ru-RU")} записей, но ни одна не содержит времени съёмки — построить временную шкалу не по чему.`}
      />
    );

  return <main className="min-h-workspace w-full overflow-auto bg-surface-canvas text-ink-primary">
    <section className="min-w-[980px] border-b border-line-default bg-surface-base">
      <header className="flex items-center justify-between border-b border-line-default px-4 py-3"><div className="flex items-center gap-2"><Activity className="h-4 w-4 text-cyan-300" /><div><div className="font-mono text-sm font-bold text-cyan-300">ТАЙМЛАЙН · {stageLabel(stage)}</div><div className="mt-1 text-[11px] text-ink-muted">{photos.length.toLocaleString("ru-RU")} фото · {years[0]}—{years.at(-1)} · один активный ракурс: {poseLabel(activePose)}{undated.length > 0 && ` · без даты: ${undated.length.toLocaleString("ru-RU")}`}</div></div></div><div className="flex items-center gap-2"><button onClick={() => setFindingsMode(!findingsMode)} aria-pressed={findingsMode} className={`rounded border px-3 py-1.5 text-xs ${findingsMode ? "border-red-500 bg-red-soft text-red-300" : "border-line-default text-ink-secondary"}`}><Filter className="mr-1 inline h-3.5 w-3.5" />Находки · {countFindings(photos)}</button><button onClick={() => void query.refetch()} title="Обновить" aria-label="Обновить данные" className="rounded border border-line-default p-2 text-ink-secondary"><RefreshCw className="h-4 w-4" /></button></div></header>
      <div className="space-y-2 px-4 py-2"><StageBanner stage={stage} note={query.data?.note} /><DataContractBanner photos={rawPhotos} totalPhotos={rawPhotos.length} completeCount={query.data?.ui_fields_complete_photo_count} violationsByField={query.data?.ui_fields_violations_by_field} schema={query.data?.ui_fields_schema} />{pairRejection && <div role="alert" className="rounded border border-amber-500 bg-amber-soft px-3 py-2 text-xs text-amber-300">{pairRejection}</div>}{undated.length > 0 && <div className="rounded border border-line-default bg-surface-raised px-3 py-2 text-[11px] text-ink-muted">{undated.length.toLocaleString("ru-RU")} кадров без даты не размещены на шкале: подставлять им время начала диапазона означало бы утверждать дату, которой нет.</div>}</div>
      <div className="flex items-center gap-2 border-b border-line-default px-4 py-2"><label className="flex w-72 items-center gap-2 rounded border border-line-default bg-surface-raised px-2 text-xs text-ink-muted"><Search className="h-3.5 w-3.5" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="ID, дата, flag…" className="w-full bg-transparent py-1.5 text-ink-primary outline-none" /></label><button onClick={() => setMultiPose(!multiPose)} className={`rounded border px-3 py-1.5 text-xs ${multiPose ? "border-cyan-500 bg-cyan-soft text-cyan-300" : "border-line-default text-ink-secondary"}`}>{multiPose ? "Все ракурсы" : "Один ракурс"}</button><button onClick={() => { setZoom(1); if (viewportRef.current) viewportRef.current.scrollLeft = 0; }} className="rounded border border-line-default px-3 py-1.5 text-xs text-ink-secondary">Fit</button><span className="ml-auto font-mono text-[10px] text-ink-muted">Колесо — горизонталь · Ctrl/⌘+колесо — масштаб · клик — A/B</span></div>
      <div ref={viewportRef} onWheel={handleWheel} className="overflow-x-auto overscroll-contain" style={{ scrollbarColor: "var(--border-strong) var(--surface-canvas)" }}>
        <div style={{ minWidth: contentWidth }}>
          <div className="grid grid-cols-[138px_1fr] border-b border-line-subtle"><div className="flex h-10 items-center border-r border-line-default bg-surface-canvas px-3 font-mono text-[10px] text-ink-muted">ЭПОХИ / ГОДЫ</div><div className="relative h-10">{years.map((year) => { const ratio = clamp((Date.parse(`${year}-01-01`) - (firstDate ?? 0)) / dateRange, 0, 1); return <span key={year} className="absolute top-1.5 -translate-x-1/2 font-mono text-[10px] text-ink-muted" style={{ left: `${ratio * 100}%` }}>{year}</span>; })}</div></div>
          {TRACKS.map(track)}
          <div className="grid grid-cols-[138px_1fr] border-b border-line-subtle"><div className="flex h-[112px] flex-col justify-center border-r border-line-default bg-surface-canvas px-3 font-mono text-[10px] text-ink-muted"><span>PHOTO ROW</span><span className="mt-1 text-[9px] text-ink-disabled">одна фотография = одна X</span></div><div className="relative h-[112px]">{filtered.map((photo) => <span key={`dot-${photo.id}`} className={`absolute bottom-5 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-cyan-600 ${dimmed(photo) ? "opacity-20" : ""}`} style={{ left: `${x(photo) * 100}%` }} />)}{aPhoto && bPhoto && <div className="absolute top-1 h-1 border-x border-t border-amber-300" style={{ left: `${Math.min(x(aPhoto), x(bPhoto)) * 100}%`, width: `${Math.abs(x(aPhoto) - x(bPhoto)) * 100}%` }} />}{representative.map((photo) => <button key={photo.id} onClick={() => selectPhoto(photo)} title={title(photo)} className={`absolute top-5 w-16 -translate-x-1/2 overflow-hidden rounded border transition-opacity ${photoTone(photo)} ${selected === photo.id ? "z-20 ring-2 ring-cyan-300" : "z-10"} ${dimmed(photo) ? "opacity-25" : ""}`} style={{ left: `${x(photo) * 100}%` }}><PhotoImage photoId={photo.id} alt={`Превью ${photo.id}`} className="aspect-square w-full" /><span className="block truncate px-1 py-0.5 text-[8px] text-ink-muted">{label(photo)}</span></button>)}</div></div>
          <div className="grid grid-cols-[138px_1fr] border-b border-line-subtle"><div className="flex h-12 items-center border-r border-line-default bg-surface-canvas px-3 font-mono text-[10px] text-ink-muted">EVENTS / A·B / FLAGS</div><div className="relative h-12">{filtered.filter(isFinding).map((photo) => <button key={photo.id} onClick={() => selectPhoto(photo)} title={photo.flags.join(", ") || photo.fuzzy} className={`absolute top-3 h-4 w-4 -translate-x-1/2 rotate-45 border ${photo.flags.length ? "border-red-300 bg-red-500" : "border-amber-300 bg-amber-600"}`} style={{ left: `${x(photo) * 100}%` }} />)}{aPhoto && <span className="absolute top-1 -translate-x-1/2 font-mono text-[9px] text-cyan-300" style={{ left: `${x(aPhoto) * 100}%` }}>A</span>}{bPhoto && <span className="absolute top-1 -translate-x-1/2 font-mono text-[9px] text-violet-300" style={{ left: `${x(bPhoto) * 100}%` }}>B</span>}</div></div>
          <div className="grid grid-cols-[138px_1fr] border-b border-line-subtle"><div className="flex h-10 items-center border-r border-line-default bg-surface-canvas px-3 font-mono text-[10px] text-ink-muted">COVERAGE</div><div className="relative flex h-10 items-end gap-px">{yearCounts.map((item) => <div key={item.year} title={`${item.year}: ${item.count} фото`} className="flex-1 bg-cyan-600/70" style={{ height: `${Math.max(5, item.count / maxYearCount * 100)}%` }} />)}</div></div>
          <div className="grid grid-cols-[138px_1fr]"><div className="flex h-12 items-center border-r border-line-default bg-surface-canvas px-3 font-mono text-[10px] text-ink-muted">DENSITY NAVIGATOR</div><div className="relative flex h-12 items-end gap-px px-1">{yearCounts.map((item) => <div key={item.year} className="flex-1 bg-surface-active" style={{ height: `${Math.max(4, item.count / maxYearCount * 100)}%` }} />)}<div className="pointer-events-none absolute inset-y-1 left-0 right-0 border border-cyan-400/70 bg-cyan-400/5" /></div></div>
        </div>
      </div>
      <footer className="grid gap-2 border-t border-line-default px-4 py-2 text-[10px] text-ink-muted md:grid-cols-4"><span>После фильтров: {filtered.length.toLocaleString("ru-RU")}</span><span>Yaw: {photos.filter((p) => p.yaw != null).length} · Quality: {photos.filter((p) => p.quality != null).length}</span><span>Pairs: {photos.reduce((n, p) => n + (p.stage2PairCount ?? 0), 0).toLocaleString("ru-RU")}</span><span className="text-amber-300">Недоступные значения показываются как «н/д»</span></footer>
    </section>
    {selectedPhoto && <aside className="fixed right-4 top-20 z-30 w-[min(430px,calc(100vw-2rem))] rounded-lg border border-cyan-600 bg-surface-base p-4 shadow-2xl"><div className="flex items-start justify-between"><div><div className="font-mono text-xs font-bold text-cyan-300">КАРТОЧКА КАДРА · {blindMode ? label(selectedPhoto) : selectedPhoto.id}</div><div className="mt-1 text-xs text-ink-muted">{blindMode ? "дата скрыта слепым режимом" : (selectedPhoto.date ?? "дата отсутствует")} · {poseLabel(selectedPhoto.bucket)}</div></div><button onClick={() => setSelected(null)} aria-label="Закрыть карточку"><X className="h-4 w-4 text-ink-muted" /></button></div><PhotoImage photoId={selectedPhoto.id} alt={`Фото ${selectedPhoto.id}`} variant="contain" className="mt-3 max-h-44 w-full rounded border border-line-subtle" /><div className="mt-4 grid grid-cols-2 gap-2 font-mono text-[11px]">{([["quality", pct(selectedPhoto.quality)], ["yaw", metric(selectedPhoto.yaw)], ["pitch", metric(selectedPhoto.pitch)], ["roll", metric(selectedPhoto.roll)], ["evidence", selectedPhoto.evidenceState ?? "н/д"], ["measurement", selectedPhoto.measurementStatus], ["pairs", selectedPhoto.stage2PairCount ?? "н/д"], ["provenance", selectedPhoto.dateProvenanceStatus ?? "н/д"]] as [string, string | number][]).map(([key, value]) => <div key={key} className="rounded border border-line-subtle p-2"><div className="text-ink-muted">{key}</div><div className="mt-1 text-ink-primary">{String(value)}</div></div>)}</div>{selectedPhoto.uiContractViolations && selectedPhoto.uiContractViolations.length > 0 && <div className="mt-3 rounded border border-amber-500 bg-amber-soft p-2 text-[11px] text-amber-300"><div className="text-ink-muted">Недоступные поля этой записи</div><div className="mt-1 font-mono">{selectedPhoto.uiContractViolations.join(", ")}</div></div>}<div className="mt-3 rounded border border-line-subtle p-2 text-xs"><div className="text-ink-muted">Находки и ограничения</div><div className="mt-1 text-ink-primary">{substantiveFlags(selectedPhoto).length ? substantiveFlags(selectedPhoto).join(", ") : (selectedPhoto.fuzzy || "нет")}</div></div><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => selectPhoto(selectedPhoto)} className="rounded border border-cyan-600 px-2 py-1 text-xs text-cyan-300">{aId === selectedPhoto.id ? <><Check className="mr-1 inline h-3 w-3" />A назначен</> : bId === selectedPhoto.id ? <><Check className="mr-1 inline h-3 w-3" />B назначен</> : "Назначить A/B"}</button><button onClick={swapPair} disabled={!aId || !bId} className="rounded border border-line-default px-2 py-1 text-xs text-ink-secondary disabled:opacity-40"><ArrowLeftRight className="mr-1 inline h-3 w-3" />Поменять A и B</button><button onClick={resetPair} disabled={!aId && !bId} className="rounded border border-line-default px-2 py-1 text-xs text-ink-secondary disabled:opacity-40">Сбросить пару</button></div></aside>}
  </main>;
}
