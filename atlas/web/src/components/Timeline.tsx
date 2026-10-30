import { memo, useEffect, useMemo, useRef, useState } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Download,
  Settings2,
  Plus,
  FileDown,
  Camera,
  ChevronDown,
  X,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";
import { useStore, morphSegment, poseLabels } from "../store";
import { post, pngFromSVG } from "../api";
import type { Photo, Metric, MetricRow } from "../types";
import type { HeatStats } from "../heat";
import { Slider, JobProgress } from "./ui";
export const dateLabel = (d: string | null) =>
  d ? d.split("-").reverse().join(".") : "Без даты";
function interval(a: Photo, b: Photo) {
  if (!a.date || !b.date) return "дата?";
  const x = new Date(a.date),
    y = new Date(b.date);
  const months =
    (y.getFullYear() - x.getFullYear()) * 12 + y.getMonth() - x.getMonth();
  if (months < 1) return "+" + Math.round((+y - +x) / 86400000) + " дн";
  return (
    "+" +
    (months >= 12 ? Math.floor(months / 12) + " г " : "") +
    (months % 12 ? (months % 12) + " мес" : "")
  );
}
export function usePlayback() {
  const playing = useStore((s) => s.playing);
  useEffect(() => {
    if (!playing) return;
    let raf = 0,
      last = performance.now(),
      acc = 0;
    const tick = (now: number) => {
      const state = useStore.getState();
      acc += now - last;
      last = now;
      if (acc >= 1000 / 30) {
        const total = state.duration * Math.max(1, state.route.length - 1);
        const head = state.playhead + acc / 1000 / total;
        acc = 0;
        if (head >= 1) {
          state.set({ playhead: 1, playing: false });
          return;
        }
        state.set({ playhead: head });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
}
function valuesFor(
  metric: Metric,
  photos: Photo[],
  rows: MetricRow[],
  mode: string,
) {
  return photos.map((p, i) => {
    const value = rows.find((r) => r.id === p.id)?.metrics[metric.id];
    if (mode === "z") return value?.z ?? null;
    if (mode === "delta") {
      const prev =
        i > 0
          ? rows.find((r) => r.id === photos[i - 1].id)?.metrics[metric.id]
              ?.value
          : null;
      return prev != null && value?.value != null ? value.value - prev : null;
    }
    return value?.value ?? null;
  });
}
const colors = [
  "#5bd7bb",
  "#b29ced",
  "#e8b76d",
  "#7dbff0",
  "#e693b0",
  "#96ce81",
];
export const MetricTrack = memo(function MetricTrack({
  metric,
  photos,
  rows,
  x,
  width,
  headX,
  mode,
  index,
  morphing,
}: {
  metric: Metric;
  photos: Photo[];
  rows: MetricRow[];
  x: number[];
  width: number;
  headX: number;
  mode: string;
  index: number;
  morphing: boolean;
}) {
  const vals = useMemo(
    () => valuesFor(metric, photos, rows, mode),
    [metric, photos, rows, mode],
  );
  const valid = vals.filter((v) => v !== null) as number[],
    lo = valid.length ? Math.min(...valid) : 0,
    hi = valid.length ? Math.max(...valid) : 1,
    pad = Math.max((hi - lo) * 0.35, Math.abs(hi) * 0.005, 0.00001);
  const y = (v: number) => 35 - ((v - lo + pad) / (hi - lo + pad * 2)) * 28;
  const stroke = colors[index % colors.length];
  const select = useStore((s) => s.selectPhoto);
  const paths = vals
    .map((v, i) =>
      v === null
        ? ""
        : `${i && vals[i - 1] !== null ? "L" : "M"}${x[i]},${y(v)}`,
    )
    .join(" ");
  let cur: string = "—";
  for (let i = 0; i < x.length; i++) {
    if (headX >= x[i] && vals[i] != null) {
      cur = vals[i]!.toFixed(mode === "z" ? 2 : 4);
      if (morphing && i < x.length - 1 && vals[i + 1] != null) {
        const f = (headX - x[i]) / (x[i + 1] - x[i]);
        cur =
          "≈" +
          (vals[i]! * (1 - f) + vals[i + 1]! * f).toFixed(mode === "z" ? 2 : 4);
      }
    }
  }
  return (
    <div className="metric-track" style={{ width }}>
      <div className="track-label" title={metric.title}>
        <i style={{ background: stroke }} />
        <span>
          {metric.title}
          <small>
            {mode === "z"
              ? "Робастный z · MAD"
              : mode === "delta"
                ? "Δ к предыдущему"
                : metric.unit}
          </small>
        </span>
      </div>
      <svg width={width} height={48} className="track-svg">
        <line x1={174} x2={width - 35} y1={24} y2={24} stroke="#25323e" />
        {mode === "z" &&
          [
            -(metric.poses[photos[0]?.pose]?.thresholds.warn || 2),
            metric.poses[photos[0]?.pose]?.thresholds.warn || 2,
          ].map((v) => (
            <line
              key={v}
              x1={174}
              x2={width - 35}
              y1={y(v)}
              y2={y(v)}
              stroke="#b58b4a"
              strokeOpacity={0.35}
              strokeDasharray="3 5"
            />
          ))}
        <path
          d={paths}
          fill="none"
          stroke={stroke}
          strokeWidth={1.8}
          strokeDasharray={morphing ? "5 4" : undefined}
        />
        {vals.map((v, i) =>
          v !== null ? (
            <g
              key={photos[i].id}
              className="clickable"
              onClick={(e) =>
                select(photos[i].id, e.ctrlKey || e.metaKey, e.shiftKey)
              }
            >
              <circle cx={x[i]} cy={y(v)} r={10} fill="transparent" />
              <circle
                cx={x[i]}
                cy={y(v)}
                r={
                  Math.abs(
                    rows.find((r) => r.id === photos[i].id)?.metrics[metric.id]
                      ?.z || 0,
                  ) > (metric.poses[photos[i].pose]?.thresholds.alert || 3)
                    ? 4
                    : 3
                }
                fill={stroke}
                stroke={
                  Math.abs(
                    rows.find((r) => r.id === photos[i].id)?.metrics[metric.id]
                      ?.z || 0,
                  ) > (metric.poses[photos[i].pose]?.thresholds.alert || 3)
                    ? "#f1b95f"
                    : "none"
                }
                strokeWidth={2}
              />
              <title>
                {dateLabel(photos[i].date)} · {v.toFixed(5)} ·{" "}
                {poseLabels[photos[i].pose]}
              </title>
            </g>
          ) : null,
        )}
        {!valid.length && (
          <text x={width / 2} y={27} fill="#63798c" fontSize={10}>
            {mode === "z"
              ? "Нужно ≥3 фото одного ракурса; MAD не должен быть нулевым"
              : "Нет данных для этого ракурса / модели"}
          </text>
        )}
        <line
          x1={headX}
          x2={headX}
          y1={0}
          y2={48}
          stroke="#62d9bd"
          strokeOpacity={0.8}
        />
      </svg>
      <span className="track-value" style={{ color: stroke }}>
        {cur}
      </span>
    </div>
  );
});
export const Timeline = memo(function Timeline({
  sceneId,
  stats,
  variant = "metrics",
  paneHeight = 450,
}: {
  sceneId: string;
  stats: HeatStats | null;
  variant?: "morph" | "metrics";
  paneHeight?: number;
}) {
  const photos = useStore((s) => s.photos),
    group = useStore((s) => s.group),
    activeId = useStore((s) => s.activeId),
    route = useStore((s) => s.route),
    mode = useStore((s) => s.mode),
    head = useStore((s) => s.playhead),
    playing = useStore((s) => s.playing),
    duration = useStore((s) => s.duration),
    fps = useStore((s) => s.fps),
    easing = useStore((s) => s.easing),
    table = useStore((s) => s.metrics),
    visible = useStore((s) => s.visibleMetrics),
    trackMode = useStore((s) => s.timelineMode),
    timeAxis = useStore((s) => s.timeAxis),
    heat = useStore((s) => s.heat),
    jobs = useStore((s) => s.jobs),
    edges = useStore((s) => s.edges),
    set = useStore((s) => s.set),
    select = useStore((s) => s.selectPhoto),
    notify = useStore((s) => s.notify);
  const ps = useMemo(
    () =>
      photos
        .filter(
          (p) =>
            (group === "__all" || p.group === group) && p.status === "ready",
        )
        .sort(
          (a, b) =>
            (a.date || "9999").localeCompare(b.date || "9999") ||
            a.name.localeCompare(b.name),
        ),
    [photos, group],
  );
  const container = useRef<HTMLDivElement>(null);
  const [availableWidth, setWidth] = useState(600);
  const [scrollTop, setScrollTop] = useState(0);
  const [chooser, setChooser] = useState(false);
  const [settings, setSettings] = useState(false);
  const [resolution, setResolution] = useState(512);
  const [query, setQuery] = useState("");
  const [trackHeight, setTrackHeight] = useState(144);
  useEffect(() => {
    if (!container.current) return;
    const ob = new ResizeObserver((es) => setWidth(es[0].contentRect.width));
    ob.observe(container.current);
    return () => ob.disconnect();
  }, []);
  const width = Math.max(
    availableWidth,
    ps.length * (variant === "morph" ? 104 : 90) +
      (variant === "morph" ? 20 : 200),
  );
  const times = ps.map((p) => (p.date ? Date.parse(p.date) : NaN)),
    validTimes = times.every(Number.isFinite) && times.at(-1)! > times[0];
  const x = ps.map(
    (p, i) =>
      (variant === "morph" ? 58 : 190) +
      (width - (variant === "morph" ? 116 : 240)) *
        (timeAxis && validTimes
          ? (times[i] - times[0]) / (times.at(-1)! - times[0])
          : ps.length > 1
            ? i / (ps.length - 1)
            : 0.5),
  );
  const seg =
    mode === "morph"
      ? morphSegment(route, head)
      : { a: activeId, b: activeId, t: 0 };
  const aIndex = ps.findIndex((p) => p.id === seg.a),
    bIndex = ps.findIndex((p) => p.id === seg.b),
    t = easing === "smooth" ? seg.t * seg.t * (3 - 2 * seg.t) : seg.t;
  const cursor = (x[aIndex] || 190) * (1 - t) + (x[bIndex] || 190) * t;
  const connected =
    variant === "metrics" &&
    edges.some((e) => e.target === sceneId && e.targetHandle === "series") &&
    edges.some((e) => e.target === "metrics" && e.targetHandle === "landmarks");
  const tracks = useMemo(
    () =>
      table.catalog.filter((m) =>
        visible ? visible.includes(m.id) : m.model === "3ddfa_v3",
      ),
    [table.catalog, visible],
  );
  const displayHeight =
    variant === "metrics" ? Math.max(96, paneHeight - 180) : trackHeight;
  const rowHeight = 48,
    start = Math.max(0, Math.floor(scrollTop / rowHeight) - 1),
    end = Math.min(
      tracks.length,
      start + Math.ceil(displayHeight / rowHeight) + 2,
    );
  const lastJob = jobs.find((j) => j.kind === "morph");
  const play = () => {
    if (playing) {
      set({ playing: false });
      return;
    }
    let r = route;
    if (r.length < 2) {
      const i = ps.findIndex((p) => p.id === activeId);
      r = ps
        .slice(
          Math.max(0, Math.min(i, ps.length - 2)),
          Math.max(0, Math.min(i, ps.length - 2)) + 2,
        )
        .map((p) => p.id);
    }
    if (r.length < 2) {
      notify("Для морфинга нужны два обработанных фото");
      return;
    }
    set({
      route: r,
      mode: "morph",
      playing: true,
      playhead: mode === "photo" || head >= 1 ? 0 : head,
    });
  };
  const exportVideo = async () => {
    if (route.length < 2) {
      notify("Выберите 2–10 фото: Ctrl/⌘ + клик");
      return;
    }
    try {
      const ref =
        heat.reference === "first"
          ? ps[0]?.id
          : heat.reference === "previous"
            ? ps[Math.max(0, aIndex - 1)]?.id
            : heat.reference;
      await post("/morph", {
        photo_ids: route,
        seconds: duration,
        fps,
        resolution,
        easing,
        heatmap: heat.enabled,
        vmin: heat.vmin,
        vmax: stats?.hi || heat.vmax,
        gamma: heat.gamma,
        opacity: heat.opacity,
        palette: heat.palette,
        inverse: heat.inverse,
        reference_id: ref,
        metric: heat.metric,
        low: heat.low,
        mid: heat.mid,
        high: heat.high,
        midPosition: heat.midPosition,
        texture: heat.texture,
        outsideOpacity: heat.outsideOpacity,
        onlyAbove: heat.onlyAbove,
        smoothing: heat.smoothing,
        yaw:
          heat.view === "left"
            ? -35
            : heat.view === "right"
              ? 35
              : heat.view === "profile"
                ? 85
                : 0,
      });
      notify("MP4 поставлен в очередь. Можно продолжать работу.");
    } catch (e) {
      notify(String(e));
    }
  };
  const exportPNG = async () => {
    const w = 1200,
      h = tracks.length * 65 + 50;
    const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
    let body = "";
    tracks.forEach((m, j) => {
      const vals = valuesFor(m, ps, table.rows, trackMode),
        nums = vals.filter((v) => v !== null) as number[],
        lo = Math.min(...nums),
        hi = Math.max(...nums),
        y = (v: number) => j * 65 + 42 - ((v - lo) / (hi - lo || 1)) * 28;
      body += `<text x="16" y="${j * 65 + 24}" fill="#c6d3df" font-size="13">${esc(m.title)}</text><path d="${vals.map((v, i) => (v === null ? "" : `${i ? "L" : "M"}${250 + (i * (w - 290)) / Math.max(1, ps.length - 1)},${y(v)}`)).join(" ")}" fill="none" stroke="${colors[j % colors.length]}" stroke-width="2"/>`;
    });
    try {
      await pngFromSVG(
        `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="100%" height="100%" fill="#131e28"/>${body}<text x="16" y="${h - 10}" fill="#8295a7" font-size="11">ATLAS · ${esc(group)} · config ${table.config_version} · ${trackMode}</text></svg>`,
        "atlas-metrics.png",
      );
    } catch (e) {
      notify("Не удалось экспортировать PNG");
    }
  };
  return (
    <section
      className={
        "timeline nodrag nowheel " +
        (variant === "morph" ? "morph-only" : "metrics-only")
      }
      data-testid={variant === "morph" ? "morph-panel" : "metrics-timeline"}
    >
      <div className="transport">
        <div className="transport-left">
          <button
            className={"play-button " + (playing ? "playing" : "")}
            title={playing ? "Пауза" : "Воспроизвести морфинг"}
            aria-label="Воспроизвести морфинг"
            onClick={play}
          >
            {playing ? (
              <Pause size={17} />
            ) : (
              <Play size={17} fill="currentColor" />
            )}
          </button>
          <button
            className="icon-btn"
            title="Предыдущий кадр"
            onClick={() =>
              select(
                ps[Math.max(0, ps.findIndex((p) => p.id === activeId) - 1)]?.id,
              )
            }
          >
            <SkipBack size={14} />
          </button>
          <button
            className="icon-btn"
            title="Следующий кадр"
            onClick={() =>
              select(
                ps[
                  Math.min(
                    ps.length - 1,
                    ps.findIndex((p) => p.id === activeId) + 1,
                  )
                ]?.id,
              )
            }
          >
            <SkipForward size={14} />
          </button>
          <span className="time-code">
            {mode === "morph"
              ? (head * duration * Math.max(1, route.length - 1)).toFixed(1)
              : "0.0"}{" "}
            <span>
              / {(duration * Math.max(1, route.length - 1)).toFixed(1)} c
            </span>
          </span>
          <span className="chip">3D-морфинг</span>
          <button
            className="subtle-button"
            onClick={() => setSettings(!settings)}
          >
            <Settings2 size={12} />
            {route.length} кадра <ChevronDown size={12} />
          </button>
        </div>
        <div className="transport-right">
          {variant === "metrics" && (
            <>
              <div className="segmented small">
                <button
                  className={!timeAxis ? "active" : ""}
                  onClick={() => set({ timeAxis: false })}
                >
                  По кадрам
                </button>
                <button
                  className={timeAxis ? "active" : ""}
                  onClick={() => set({ timeAxis: true })}
                >
                  По времени
                </button>
              </div>
              <button
                className="subtle-button"
                onClick={() => setChooser(!chooser)}
                data-role="tracks"
              >
                <Plus size={13} /> Дорожки{" "}
                <span className="count">{tracks.length}</span>
              </button>
              <button
                className="subtle-button"
                onClick={() =>
                  set({ settingsOpen: !useStore.getState().settingsOpen })
                }
              >
                Параметры сцены
              </button>
            </>
          )}
          {variant === "morph" && (
            <button className="primary small" onClick={exportVideo}>
              <Download size={13} /> MP4
            </button>
          )}
        </div>
      </div>
      {settings && variant === "morph" && (
        <div className="morph-settings">
          <div className="flex between">
            <strong>Маршрут и экспорт</strong>
            <button className="icon-btn" onClick={() => setSettings(false)}>
              <X size={13} />
            </button>
          </div>
          <div className="route-chips">
            {route.map((id, i) => (
              <div key={id} className="route-chip">
                <span>{ps.findIndex((p) => p.id === id) + 1}</span>
                <button
                  disabled={i === 0}
                  title="Раньше в маршруте"
                  onClick={() => {
                    const r = [...route];
                    [r[i - 1], r[i]] = [r[i], r[i - 1]];
                    set({ route: r, playing: false, playhead: 0 });
                  }}
                >
                  <ArrowLeft size={11} />
                </button>
                <button
                  disabled={i === route.length - 1}
                  title="Позже в маршруте"
                  onClick={() => {
                    const r = [...route];
                    [r[i], r[i + 1]] = [r[i + 1], r[i]];
                    set({ route: r, playing: false, playhead: 0 });
                  }}
                >
                  <ArrowRight size={11} />
                </button>
              </div>
            ))}
          </div>
          <label className="inline-field">
            Точное число кадров{" "}
            <input
              type="number"
              min={2}
              max={10}
              value={route.length}
              onChange={(e) => {
                const n = +e.target.value;
                if (n < 2 || n > 10 || n > ps.length) {
                  notify(
                    "Выберите от 2 до " + Math.min(10, ps.length) + " фото",
                  );
                  return;
                }
                set({
                  route: ps.slice(0, n).map((p) => p.id),
                  mode: "morph",
                  playhead: 0,
                  playing: false,
                });
              }}
            />
          </label>
          <Slider
            label="Переход, с"
            value={duration}
            min={0.2}
            max={6}
            step={0.1}
            onChange={(duration) => set({ duration })}
          />
          <Slider
            label="Кадров в секунду"
            value={fps}
            min={6}
            max={60}
            step={1}
            onChange={(fps) => set({ fps })}
          />
          <div className="flex gap">
            <select
              value={resolution}
              onChange={(e) => setResolution(+e.target.value)}
            >
              {[256, 512, 768, 1024].map((n) => (
                <option key={n} value={n}>
                  {n} × {n}
                </option>
              ))}
            </select>
            <select
              value={easing}
              onChange={(e) => set({ easing: e.target.value as any })}
            >
              <option value="smooth">Ease-in-out</option>
              <option value="linear">Линейно</option>
            </select>
          </div>
          <p className="micro muted">
            Фиксированная камера · реальная 3D-геометрия. Текущие пороги
            сохраняются вместе с видео.
          </p>
        </div>
      )}
      {chooser && variant === "metrics" && (
        <div className="track-chooser">
          <div className="flex between">
            <strong>Дорожки метрик</strong>
            <button className="icon-btn" onClick={() => setChooser(false)}>
              <X size={13} />
            </button>
          </div>
          <Slider
            label="Высота области графиков"
            value={trackHeight}
            min={96}
            max={480}
            step={48}
            onChange={setTrackHeight}
          />
          <input
            className="search"
            placeholder="Название или модель…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="chooser-list">
            {table.catalog
              .filter((m) =>
                (m.title + " " + m.model)
                  .toLowerCase()
                  .includes(query.toLowerCase()),
              )
              .map((m) => (
                <label className="check-row" key={m.id}>
                  <input
                    type="checkbox"
                    checked={tracks.some((t) => t.id === m.id)}
                    onChange={(e) =>
                      set({
                        visibleMetrics: e.target.checked
                          ? [...tracks.map((t) => t.id), m.id]
                          : tracks
                              .filter((t) => t.id !== m.id)
                              .map((t) => t.id),
                      })
                    }
                  />
                  <span>
                    {m.title}
                    <small>
                      {m.model}
                      {m.model !== "3ddfa_v3" ? " · не подключена" : ""}
                    </small>
                  </span>
                </label>
              ))}
          </div>
          <div className="flex between">
            <button
              className="text-button"
              onClick={() => set({ visibleMetrics: null })}
            >
              Сбросить
            </button>
            <a href="/api/export/metrics.csv" className="text-button">
              <FileDown size={12} /> CSV
            </a>
            <button className="text-button" onClick={exportPNG}>
              <Camera size={12} /> PNG
            </button>
          </div>
        </div>
      )}
      <div className="timeline-mode">
        <span className="eyebrow">ФОТО → ГЕОМЕТРИЯ → МЕТРИКИ</span>
        <div className="segmented small">
          {[
            ["value", "Значение"],
            ["z", "MAD z"],
            ["delta", "Δ пред."],
          ].map(([v, l]) => (
            <button
              key={v}
              className={trackMode === v ? "active" : ""}
              onClick={() => set({ timelineMode: v as any })}
            >
              {l}
            </button>
          ))}
        </div>
      </div>
      <div className="timeline-scroll" ref={container}>
        <div className="timeline-inner" style={{ width }}>
          {variant === "morph" ? (
            <div className="photo-track">
              <div className="photo-track-label">
                <span>Фотографии</span>
                <small>
                  {ps.length} в серии · {route.length} в маршруте
                </small>
                {mode === "morph" && (
                  <span className="interpolated-label">интерполяция</span>
                )}
              </div>
              <div
                className="time-axis-line"
                style={{ left: 190, right: 50 }}
              />
              {ps.slice(0, -1).map((p, i) => (
                <button
                  key={p.id}
                  className="transition-hit"
                  title="Морфинг этой пары"
                  style={{
                    left: x[i] + 43,
                    width: Math.max(10, x[i + 1] - x[i] - 86),
                  }}
                  onClick={() =>
                    set({
                      route: [p.id, ps[i + 1].id],
                      mode: "morph",
                      playhead: 0.5,
                      playing: false,
                    })
                  }
                >
                  <span>{interval(p, ps[i + 1])}</span>
                  <i />
                  <span className="transition-play">▷</span>
                </button>
              ))}
              {ps.map((p, i) => (
                <button
                  key={p.id}
                  className={
                    "photo-keyframe " +
                    (route.includes(p.id) ? "route-selected " : "") +
                    (p.id === activeId && mode === "photo" ? "current" : "")
                  }
                  style={{ left: x[i] - 39 }}
                  onClick={(e) =>
                    select(p.id, e.ctrlKey || e.metaKey, e.shiftKey)
                  }
                  onDoubleClick={() => set({ photoEditor: p.id })}
                  title={
                    dateLabel(p.date) +
                    " · " +
                    poseLabels[p.pose] +
                    " · двойной клик: дата и углы"
                  }
                >
                  <div className="keyframe-image">
                    <img src={p.thumbnail} />
                    <span className="frame-number">{i + 1}</span>
                    {mode === "morph" && (seg.a === p.id || seg.b === p.id) && (
                      <span className="endpoint">
                        {seg.a === p.id ? "A" : "B"}
                      </span>
                    )}
                  </div>
                  <span className="frame-date">{dateLabel(p.date)}</span>
                  <small>{poseLabels[p.pose]}</small>
                </button>
              ))}
              <div className="timeline-playhead" style={{ left: cursor }}>
                <i />
              </div>
            </div>
          ) : (
            <div className="metric-date-axis">
              <span>Дата / кадр</span>
              {ps.map((p, i) => (
                <button
                  key={p.id}
                  style={{ left: x[i] - 35 }}
                  onClick={() => select(p.id)}
                  title={p.name}
                >
                  {dateLabel(p.date)}
                </button>
              ))}
              <i style={{ left: cursor }} />
            </div>
          )}
          {variant === "morph" && (
            <div className="scrub-row">
              <span className="mini muted">
                {mode === "morph"
                  ? Math.round(t * 100) + "% перехода"
                  : "Исходный кадр"}
              </span>
              <input
                aria-label="Позиция морфинга"
                type="range"
                min={0}
                max={1}
                step={0.001}
                value={head}
                onChange={(e) => {
                  if (route.length < 2) {
                    notify("Выберите хотя бы два кадра");
                    return;
                  }
                  set({
                    mode: "morph",
                    playhead: +e.target.value,
                    playing: false,
                  });
                }}
              />
            </div>
          )}
          {connected ? (
            <div
              className="metric-tracks"
              style={{ height: displayHeight, maxHeight: displayHeight }}
              onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
            >
              <div
                style={{
                  height: tracks.length * rowHeight,
                  position: "relative",
                }}
              >
                {tracks.slice(start, end).map((m, j) => (
                  <div
                    key={m.id}
                    style={{
                      position: "absolute",
                      left: 0,
                      top: (start + j) * rowHeight,
                      width: "100%",
                    }}
                  >
                    <MetricTrack
                      metric={m}
                      photos={ps}
                      rows={table.rows}
                      x={x}
                      width={width}
                      headX={cursor}
                      mode={trackMode}
                      index={start + j}
                      morphing={mode === "morph"}
                    />
                  </div>
                ))}
              </div>
              {!tracks.length && (
                <div className="no-tracks">
                  Добавьте дорожки метрик кнопкой «Дорожки»
                </div>
              )}
            </div>
          ) : (
            <div className="no-tracks">Подключите series из реестра метрик</div>
          )}
          <div className="quality-track">
            <span>
              Резкость <small>контроль качества</small>
            </span>
            <svg width={width} height={28}>
              {ps.map((p, i) => (
                <g key={p.id}>
                  <rect
                    x={x[i] - 19}
                    y={9}
                    width={38}
                    height={10}
                    rx={2}
                    fill="#20303e"
                  />
                  {Array.from({
                    length: Math.max(
                      1,
                      Math.min(10, Math.round((p.meta?.sharpness || 0) / 40)),
                    ),
                  }).map((_, j) => (
                    <rect
                      key={j}
                      x={x[i] - 17 + j * 3.5}
                      y={10}
                      width={2.5}
                      height={8}
                      fill="#638b9d"
                    />
                  ))}
                </g>
              ))}
              <line x1={cursor} x2={cursor} y1={0} y2={28} stroke="#5bd7bb" />
            </svg>
          </div>
        </div>
      </div>
      <footer className="timeline-footer">
        <span>
          Клик — кадр <b>·</b> переход — морфинг пары <b>·</b> Ctrl/⌘ — маршрут{" "}
          <b>·</b> Shift — диапазон
        </span>
        <a href="/api/export/metrics.csv" title="Выгрузить CSV">
          <FileDown size={12} /> CSV
        </a>
      </footer>
      {variant === "morph" &&
        lastJob &&
        ["queued", "running", "failed"].includes(lastJob.status) && (
          <JobProgress job={lastJob} />
        )}{" "}
      {variant === "morph" && lastJob?.status === "completed" && (
        <div className="export-ready">
          <span>
            <span className="status-dot" /> Видео готово ·{" "}
            {lastJob.result.frames} кадров
          </span>
          <a href={lastJob.result.url}>
            <Download size={12} /> Скачать MP4
          </a>
          <a href={lastJob.result.manifest_url}>Параметры JSON</a>
        </div>
      )}
    </section>
  );
});
