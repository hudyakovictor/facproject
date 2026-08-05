/**
 * Landmark Comparison Workspace (Iteration 08) — big modal popup.
 *
 * Renders two chronology-aligned landmark models (106 or 134 points) of two
 * photos from the same pose bin, with a mini timeline strip to scrub through
 * the bin, per-point displacement vectors and reviewer thresholds for the
 * general landmark shift (tolerance / suspect per model).
 *
 * The settings widget applies LIVE — there is no "Save" button.
 *
 * 🚨 Thresholds are reviewer references, not verdicts. Exceedance is a review
 * trigger only.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { image, landmarkCompare, morphingBins, type LandmarkComparePayload, type MorphBin } from "../../shared/api";
import { drawLandmarkComparison, type CompareDisplayMode } from "../../shared/landmarkRenderer";
import { LABEL, POSES, type Pose } from "../../shared/types";
import { logError } from "../../shared/logger";

const POSE_ORDER = POSES as readonly string[];
const REGIONS = ["contour", "brows", "eyes", "nose", "mouth", "cheeks", "inner_contour"];
const REGION_LABELS: Record<string, string> = {
  contour: "Контур", brows: "Брови", eyes: "Глаза", nose: "Нос",
  mouth: "Рот", cheeks: "Щёки", inner_contour: "Внутр. контур",
};

interface Props {
  initialPose?: string | null;
  initialA?: string | null;
  initialB?: string | null;
  onClose: () => void;
}

interface Thresholds { tol106: number; susp106: number; tol134: number; susp134: number }

const THRESH_KEY = "deeputin.landmark.thresholds.v1";
function loadThresholds(): Thresholds {
  try {
    const raw = localStorage.getItem(THRESH_KEY);
    if (raw) return { ...{ tol106: 0.02, susp106: 0.05, tol134: 0.02, susp134: 0.05 }, ...JSON.parse(raw) };
  } catch { /* defaults */ }
  return { tol106: 0.02, susp106: 0.05, tol134: 0.02, susp134: 0.05 };
}

export default function LandmarkCompareWorkspace({ initialPose, initialA, initialB, onClose }: Props) {
  const [bins, setBins] = useState<MorphBin[] | null>(null);
  const [pose, setPose] = useState<string>(initialPose && POSE_ORDER.includes(initialPose) ? initialPose : "frontal");
  const [count, setCount] = useState<106 | 134>(134);
  const [photoA, setPhotoA] = useState<string>(initialA || "");
  const [photoB, setPhotoB] = useState<string>(initialB || "");
  const [data, setData] = useState<LandmarkComparePayload | null>(null);
  const [thresholds, setThresholds] = useState<Thresholds>(loadThresholds);
  const [mode, setMode] = useState<CompareDisplayMode>("overlay");
  const [showVectors, setShowVectors] = useState(true);
  const [showLabels, setShowLabels] = useState(false);
  const [showCalibrated, setShowCalibrated] = useState(true);
  const [regions, setRegions] = useState<Set<string>>(new Set());
  const [camera, setCamera] = useState({ yaw: 0, elev: -6, dist: 3.4 });
  const [message, setMessage] = useState("");
  const [blinkPhase, setBlinkPhase] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragRef = useRef<{ x: number; y: number; yaw: number; elev: number } | null>(null);
  const dataRef = useRef(data);
  dataRef.current = data;

  useEffect(() => { localStorage.setItem(THRESH_KEY, JSON.stringify(thresholds)); }, [thresholds]);

  // ---- load bins ----
  useEffect(() => {
    let dead = false;
    morphingBins()
      .then(data => {
        if (dead) return;
        setBins(data.pose_bins);
        const bin = data.pose_bins.find(b => b.pose === pose) || data.pose_bins[4];
        const photos = bin.photos;
        setPhotoA(initialA && photos.some(p => p.id === initialA) ? initialA : photos[0]?.id || "");
        setPhotoB(initialB && photos.some(p => p.id === initialB) ? initialB : photos[1]?.id || photos[0]?.id || "");
      })
      .catch(error => setMessage(error instanceof Error ? error.message : String(error)));
    return () => { dead = true; };
  }, []);

  const photosOfBin = useMemo(() => bins?.find(b => b.pose === pose)?.photos || [], [bins, pose]);

  // ---- load comparison data ----
  useEffect(() => {
    if (!photoA || !photoB || photoA === photoB) return;
    let dead = false;
    setMessage("");
    landmarkCompare(photoA, photoB, count, "chronology")
      .then(payload => { if (!dead) setData(payload); })
      .catch(error => { if (!dead) { const text = error instanceof Error ? error.message : String(error); setMessage(text); logError("landmarks", `сравнение ${photoA} ↔ ${photoB}`, error); } });
    return () => { dead = true; };
  }, [photoA, photoB, count]);

  // ---- redraw ----
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data) return;
    const tolerance = count === 106 ? thresholds.tol106 : thresholds.tol134;
    const suspect = count === 106 ? thresholds.susp106 : thresholds.susp134;
    drawLandmarkComparison(canvas, data, {
      mode, showVectors, showLabels, showCalibrated, tolerance, suspect, regions, blinkPhase,
    }, camera);
  }, [data, count, thresholds, mode, showVectors, showLabels, showCalibrated, regions, camera, blinkPhase]);

  // ---- blink loop ----
  useEffect(() => {
    if (mode !== "blink") return;
    const timer = window.setInterval(() => setBlinkPhase(phase => (phase + 0.5) % 1), 750);
    return () => window.clearInterval(timer);
  }, [mode]);

  const switchPose = (next: string) => {
    setPose(next);
    const bin = bins?.find(b => b.pose === next);
    if (bin?.photos.length) {
      setPhotoA(bin.photos[0].id);
      setPhotoB(bin.photos[1]?.id || bin.photos[0].id);
    }
  };

  const pickPhoto = (side: "a" | "b", id: string) => {
    if (side === "a") setPhotoA(id); else setPhotoB(id);
  };

  const tolerance = count === 106 ? thresholds.tol106 : thresholds.tol134;
  const suspect = count === 106 ? thresholds.susp106 : thresholds.susp134;
  const setTol = (value: number) => count === 106 ? setThresholds(t => ({ ...t, tol106: value })) : setThresholds(t => ({ ...t, tol134: value }));
  const setSusp = (value: number) => count === 106 ? setThresholds(t => ({ ...t, susp106: value })) : setThresholds(t => ({ ...t, susp134: value }));

  const toggleRegion = (region: string) => {
    setRegions(current => {
      const next = new Set(current);
      if (next.has(region)) next.delete(region); else next.add(region);
      return next;
    });
  };

  // ---- exceedance list ----
  const exceedances = useMemo(() => {
    if (!data) return [];
    return data.points
      .filter(p => p.magnitude !== null && p.magnitude > tolerance)
      .sort((a, b) => (b.magnitude ?? 0) - (a.magnitude ?? 0))
      .slice(0, 60);
  }, [data, tolerance]);

  const onPointerDown = (event: React.PointerEvent) => {
    dragRef.current = { x: event.clientX, y: event.clientY, yaw: camera.yaw, elev: camera.elev };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    setCamera(c => ({ ...c, yaw: drag.yaw + (event.clientX - drag.x) * 0.4, elev: Math.max(-80, Math.min(80, drag.elev - (event.clientY - drag.y) * 0.3)) }));
  };
  const onPointerUp = () => { dragRef.current = null; };
  const onWheel = (event: React.WheelEvent) => {
    setCamera(c => ({ ...c, dist: Math.max(1.2, Math.min(12, c.dist + event.deltaY * 0.004)) }));
  };

  const indexOfA = photosOfBin.findIndex(p => p.id === photoA);
  const indexOfB = photosOfBin.findIndex(p => p.id === photoB);
  const step = (side: "a" | "b", delta: number) => {
    const index = side === "a" ? indexOfA : indexOfB;
    const next = photosOfBin[index + delta];
    if (next) pickPhoto(side, next.id);
  };

  return (
    <div className="workspace-modal landmark-modal">
      <header className="workspace-header">
        <div>
          <small>ITERATION 08 · LANDMARK COMPARISON</small>
          <b>Сравнение ключевых точек · {count} · chronology</b>
          <span>{data ? `${data.photo_a} ↔ ${data.photo_b} · RMS ${data.summary.rms?.toFixed(5) ?? "—"}` : "Загрузка…"}</span>
        </div>
        <button className="workspace-close" onClick={onClose} title="Закрыть">×</button>
      </header>
      <div className="workspace-body">
        <aside className="workspace-settings landmark-settings">
          <section>
            <h3>Модель</h3>
            <div className="mode-tabs">
              <button className={count === 106 ? "active" : ""} onClick={() => setCount(106)}>LDM 106</button>
              <button className={count === 134 ? "active" : ""} onClick={() => setCount(134)}>LDM 134</button>
            </div>
          </section>
          <section>
            <h3>Ракурс</h3>
            <div className="pose-grid">
              {POSE_ORDER.map(item => (
                <button key={item} className={pose === item ? "active" : ""} onClick={() => switchPose(item)}>
                  {LABEL[item as Pose]}
                </button>
              ))}
            </div>
          </section>
          <section>
            <h3>Пороги смещения · {count}</h3>
            <label className="filter-slider">
              <span>Допустимо (green→orange)</span>
              <input type="range" min={0.001} max={0.15} step={0.001} value={tolerance} onChange={event => setTol(Number(event.target.value))} />
              <b>{tolerance.toFixed(3)}</b>
            </label>
            <label className="filter-slider">
              <span>Подозрительно (orange→red)</span>
              <input type="range" min={0.002} max={0.25} step={0.001} value={suspect} onChange={event => setSusp(Number(event.target.value))} />
              <b>{suspect.toFixed(3)}</b>
            </label>
            <label className="filter-enable">
              <input type="checkbox" checked={showCalibrated} onChange={event => setShowCalibrated(event.target.checked)} />
              <b>Подсветить превышение cal. p95 {data?.summary.calibrated ? "" : "(нет Stage 2)"}</b>
            </label>
            {count === 106 && (
              <label className="filter-slider">
                <span>LDM134 пороги (для модели 134)</span>
                <small>tol {thresholds.tol134.toFixed(3)} · susp {thresholds.susp134.toFixed(3)}</small>
              </label>
            )}
          </section>
          <section>
            <h3>Отображение</h3>
            <div className="mode-tabs">
              <button className={mode === "overlay" ? "active" : ""} onClick={() => setMode("overlay")}>Наложение</button>
              <button className={mode === "side_by_side" ? "active" : ""} onClick={() => setMode("side_by_side")}>Рядом</button>
              <button className={mode === "blink" ? "active" : ""} onClick={() => setMode("blink")}>Мигание</button>
            </div>
            <label className="filter-enable">
              <input type="checkbox" checked={showVectors} onChange={event => setShowVectors(event.target.checked)} />
              <b>Векторы смещения</b>
            </label>
            <label className="filter-enable">
              <input type="checkbox" checked={showLabels} onChange={event => setShowLabels(event.target.checked)} />
              <b>Номера точек</b>
            </label>
          </section>
          <section>
            <h3>Зоны</h3>
            <div className="region-grid">
              {REGIONS.map(region => (
                <button key={region} className={regions.has(region) ? "active" : ""} onClick={() => toggleRegion(region)}>
                  {REGION_LABELS[region] || region}
                </button>
              ))}
            </div>
          </section>
          <section className="exceedance-section">
            <h3>Превышения (&gt; {tolerance.toFixed(3)}) · {exceedances.length}</h3>
            <div className="exceedance-list">
              {exceedances.slice(0, 30).map(point => (
                <div key={point.i} className={`exceedance ${point.magnitude !== null && point.magnitude > suspect ? "bad" : "warn"}`}>
                  <code>#{point.i}</code><span>{REGION_LABELS[point.region] || point.region}</span>
                  <b>{point.magnitude?.toFixed(5)}</b>
                  {point.calibration_p95 != null && <em>cal {point.calibration_p95.toFixed(5)}</em>}
                </div>
              ))}
              {exceedances.length === 0 && <em>Нет превышений порога</em>}
            </div>
          </section>
        </aside>
        <main className="workspace-main">
          <div className="landmark-canvas-wrap" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onWheel={onWheel}>
            <canvas ref={canvasRef} className="landmark-canvas" />
            <div className="canvas-badge">LDM {count} · {LABEL[pose as Pose]} · {data?.space ?? "chronology"}</div>
            {data && (
              <div className="canvas-stats">
                <span>RMS <b>{data.summary.rms?.toFixed(5) ?? "—"}</b></span>
                <span>p95 <b>{data.summary.p95?.toFixed(5) ?? "—"}</b></span>
                <span>max <b>{data.summary.max?.toFixed(5) ?? "—"}</b></span>
                <span>общих <b>{data.summary.common_visible}</b></span>
                {data.summary.calibrated && <span>cal. превыш. <b>{data.summary.exceeds_calibration_p95}</b></span>}
              </div>
            )}
          </div>
          <div className="mini-timeline">
            <button className="mini-nav" disabled={indexOfA <= 0} onClick={() => step("a", -1)} title="A ←">‹A</button>
            <div className="mini-strip">
              {photosOfBin.map(photo => (
                <button
                  key={photo.id}
                  className={[
                    photo.id === photoA ? "is-a" : "",
                    photo.id === photoB ? "is-b" : "",
                    (photo.id === photoA || photo.id === photoB) ? "active" : "",
                  ].join(" ")}
                  onClick={() => pickPhoto("a", photo.id)}
                  onContextMenu={event => { event.preventDefault(); pickPhoto("b", photo.id); }}
                  title={`${photo.date}\nЛКМ → A · ПКМ → B`}
                >
                  <img src={image(photo.id, "thumbnail")} alt="" loading="lazy" />
                  <small>{photo.date.slice(0, 7)}</small>
                </button>
              ))}
            </div>
            <button className="mini-nav" disabled={indexOfB >= photosOfBin.length - 1} onClick={() => step("b", 1)} title="B →">B›</button>
          </div>
          <div className="mini-hint">Левая кнопка — фото A · правая кнопка — фото B · колесо — масштаб</div>
          {message && <div className="workspace-error">{message}</div>}
        </main>
      </div>
    </div>
  );
}
