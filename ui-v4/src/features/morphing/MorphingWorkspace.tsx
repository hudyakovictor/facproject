/**
 * Morphing Workspace (Iteration 09) — big modal popup.
 *
 * Shows textured 3D models of any two photos from the same pose bin in the
 * bin's canonical (chronology-aligned) position and morphs between them
 * (geometry + texture interpolation). Also supports a chronological sequence
 * playback across all photos of the selected bin.
 *
 * The left-hand settings widget applies LIVE — there is no "Save" button:
 * every slider/selector changes the rendering immediately.
 *
 * 🚨 Morphing is visualization-only. Interpolated frames are never sent to
 * Stage 2 and never interpreted as measurements.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { image, morphingBins, morphingPhoto, photoLandmarks, type MorphBin, type MorphPhoto, type MorphPhotoPayload } from "../../shared/api";
import { MorphRenderer, type MorphMeshData } from "../../shared/morphRenderer";
import { LABEL, POSES, type Pose } from "../../shared/types";

const POSE_ORDER = POSES as readonly string[];

interface Props {
  initialPose?: string | null;
  initialA?: string | null;
  initialB?: string | null;
  onClose: () => void;
}

interface LoadedPhoto {
  payload: MorphPhotoPayload;
  mesh: MorphMeshData;
  textureUrl: string | null;
  landmarks?: { a106?: Float32Array; a134?: Float32Array };
}

export default function MorphingWorkspace({ initialPose, initialA, initialB, onClose }: Props) {
  const [bins, setBins] = useState<MorphBin[] | null>(null);
  const [pose, setPose] = useState<string>(initialPose && POSE_ORDER.includes(initialPose) ? initialPose : "frontal");
  const [mode, setMode] = useState<"chronology" | "manual">("chronology");
  const [photoA, setPhotoA] = useState<string>(initialA || "");
  const [photoB, setPhotoB] = useState<string>(initialB || "");
  const [blend, setBlend] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1.2);
  const [loop, setLoop] = useState(true);
  const [wireframe, setWireframe] = useState(false);
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [spin, setSpin] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<MorphRenderer | null>(null);
  const cacheRef = useRef<Map<string, LoadedPhoto>>(new Map());
  const [camera, setCamera] = useState({ yaw: 0, elev: -4, dist: 3.2 });
  const dragRef = useRef<{ x: number; y: number; yaw: number; elev: number } | null>(null);
  const playingRef = useRef(playing);
  playingRef.current = playing;
  const blendRef = useRef(blend);
  blendRef.current = blend;
  const spinRef = useRef(spin);
  spinRef.current = spin;

  // ---- load bins ----
  useEffect(() => {
    let dead = false;
    setLoading(true);
    morphingBins()
      .then(data => {
        if (dead) return;
        setBins(data.pose_bins);
        const bin = data.pose_bins.find(b => b.pose === pose) || data.pose_bins[4];
        const photos = bin.photos;
        const a = (initialA && photos.some(p => p.id === initialA) ? initialA : photos[0]?.id) || "";
        const b = (initialB && photos.some(p => p.id === initialB) ? initialB : photos[1]?.id) || photos[0]?.id || "";
        setPhotoA(a);
        setPhotoB(b);
        setCamera({ yaw: bin.camera.yaw_deg, elev: bin.camera.elevation_deg, dist: 3.2 });
      })
      .catch(error => setMessage(error instanceof Error ? error.message : String(error)))
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, []);

  const currentBin = useMemo(() => bins?.find(b => b.pose === pose) || null, [bins, pose]);

  const photosOfBin = useMemo(() => currentBin?.photos || [], [currentBin]);

  // ---- load two photos ----
  const loadPhoto = useCallback(async (id: string): Promise<LoadedPhoto | null> => {
    const cached = cacheRef.current.get(id);
    if (cached) return cached;
    try {
      const [payload, landmarksA] = await Promise.all([
        morphingPhoto(id),
        photoLandmarks(id, 106, "aligned").catch(() => null),
      ]);
      const mesh: MorphMeshData = {
        vertices: payload.vertices,
        triangles: payload.triangles,
        uv: payload.uv_coords,
        vertexCount: payload.vertex_count,
      };
      const loaded: LoadedPhoto = {
        payload,
        mesh,
        textureUrl: payload.texture_url ?? null,
        landmarks: landmarksA ? { a106: new Float32Array(landmarksA.points.flat()) } : undefined,
      };
      cacheRef.current.set(id, loaded);
      return loaded;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
      return null;
    }
  }, []);

  // ---- render loop ----
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let renderer = rendererRef.current;
    if (!renderer) {
      try {
        renderer = new MorphRenderer(canvas);
        rendererRef.current = renderer;
      } catch (error) {
        setMessage(error instanceof Error ? error.message : String(error));
        return;
      }
    }
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (playingRef.current) {
        const next = blendRef.current + dt * speed;
        if (next >= 1) {
          // advance to next chronological pair (outside the state updater)
          advanceSequenceRef.current();
        } else {
          setBlend(next);
        }
      }
      if (spinRef.current) {
        setCamera(c => ({ ...c, yaw: c.yaw + dt * 14 }));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [speed]);

  const advanceSequenceRef = useRef<() => void>(() => {});
  const setBlendState = setBlend;

  const advanceSequence = useCallback(() => {
    const photos = photosOfBin;
    if (photos.length < 2) return;
    const index = photos.findIndex(p => p.id === photoA);
    const nextIndex = index >= 0 && index < photos.length - 1 ? index + 1 : (loop ? 0 : photos.length - 2);
    setPhotoA(photos[Math.max(0, Math.min(photos.length - 2, nextIndex))].id);
    setPhotoB(photos[Math.max(1, Math.min(photos.length - 1, nextIndex + 1))].id);
    blendRef.current = 0;
    setBlendState(0);
  }, [photosOfBin, photoA, loop]);
  advanceSequenceRef.current = advanceSequence;

  // ---- load meshes + textures when A/B change ----
  useEffect(() => {
    if (!photoA || !photoB || photoA === photoB) return;
    let dead = false;
    setLoading(true);
    setMessage("");
    (async () => {
      const [a, b] = await Promise.all([loadPhoto(photoA), loadPhoto(photoB)]);
      if (dead || !a || !b || !rendererRef.current) return;
      const renderer = rendererRef.current;
      renderer.setMeshes(a.mesh, b.mesh);
      renderer.blend = blendRef.current;
      renderer.yaw = camera.yaw;
      renderer.elevation = camera.elev;
      renderer.distance = camera.dist;
      renderer.wireframe = wireframe;
      renderer.showLandmarks = showLandmarks;
      renderer.clearTextures();
      try {
        if (a.textureUrl && b.textureUrl) {
          await Promise.all([renderer.loadTexture("a", a.textureUrl), renderer.loadTexture("b", b.textureUrl)]);
        }
      } catch { /* texture optional */ }
      if (!dead) setLoading(false);
    })();
    return () => { dead = true; };
  }, [photoA, photoB, camera.yaw, camera.elev, camera.dist, wireframe, showLandmarks, loadPhoto]);

  // ---- per-frame updates (blend, landmarks, camera) ----
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.blend = blend;
    renderer.yaw = camera.yaw;
    renderer.elevation = camera.elev;
    renderer.distance = camera.dist;
    renderer.wireframe = wireframe;
    renderer.showLandmarks = showLandmarks;
    if (showLandmarks) {
      const a = cacheRef.current.get(photoA);
      const b = cacheRef.current.get(photoB);
      const ptsA = a?.landmarks?.a106;
      const ptsB = b?.landmarks?.a106;
      if (ptsA && ptsB && ptsA.length === ptsB.length) {
        const t = blend;
        const interp = new Float32Array(ptsA.length);
        for (let i = 0; i < ptsA.length; i++) interp[i] = ptsA[i] + (ptsB[i] - ptsA[i]) * t;
        renderer.setLandmarks(interp, [1, 0.45, 0.3, 0.95]);
      } else {
        renderer.setLandmarks(null);
      }
    } else {
      renderer.setLandmarks(null);
    }
    renderer.render();
  }, [blend, camera, wireframe, showLandmarks, photoA, photoB]);

  // ---- pose / mode changes ----
  const switchPose = (next: string) => {
    setPose(next);
    const bin = bins?.find(b => b.pose === next);
    if (bin) {
      setCamera({ yaw: bin.camera.yaw_deg, elev: bin.camera.elevation_deg, dist: 3.2 });
      if (bin.photos.length) {
        setPhotoA(bin.photos[0].id);
        setPhotoB(bin.photos[1]?.id || bin.photos[0].id);
      }
    }
    setBlend(0);
    setPlaying(false);
  };

  const pickPhoto = (side: "a" | "b", id: string) => {
    if (side === "a") setPhotoA(id); else setPhotoB(id);
    setBlend(0);
    setPlaying(false);
  };

  const photoById = (id: string): MorphPhoto | undefined => photosOfBin.find(p => p.id === id);
  const photoAObj = photoById(photoA);
  const photoBObj = photoById(photoB);

  // ---- pointer orbit ----
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

  const fmt = (photo?: MorphPhoto) => photo ? `${photo.date || "?"} · q ${photo.quality != null ? photo.quality.toFixed(2) : "—"}` : "—";

  return (
    <div className="workspace-modal morphing-modal">
      <header className="workspace-header">
        <div>
          <small>ITERATION 09 · MORPHING</small>
          <b>Morphing · текстурированные 3D-модели</b>
          <span>Каноническое положение ракурса · {currentBin ? LABEL[currentBin.pose as Pose] : pose}</span>
        </div>
        <button className="workspace-close" onClick={onClose} title="Закрыть">×</button>
      </header>
      <div className="workspace-body">
        <aside className="workspace-settings morph-settings">
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
            <h3>Режим</h3>
            <div className="mode-tabs">
              <button className={mode === "chronology" ? "active" : ""} onClick={() => setMode("chronology")}>По хронологии</button>
              <button className={mode === "manual" ? "active" : ""} onClick={() => setMode("manual")}>A / B</button>
            </div>
          </section>
          <section>
            <h3>Фотографии</h3>
            <label className="photo-select">
              <span>A</span>
              <select value={photoA} onChange={event => pickPhoto("a", event.target.value)}>
                {photosOfBin.map(photo => <option key={photo.id} value={photo.id}>{photo.date} · {photo.id}</option>)}
              </select>
            </label>
            <label className="photo-select">
              <span>B</span>
              <select value={photoB} onChange={event => pickPhoto("b", event.target.value)}>
                {photosOfBin.map(photo => <option key={photo.id} value={photo.id}>{photo.date} · {photo.id}</option>)}
              </select>
            </label>
            <div className="photo-mini-row">
              <div className="photo-mini"><img src={photoA ? image(photoA, "thumbnail") : ""} alt="" /><b>{fmt(photoAObj)}</b></div>
              <i>→</i>
              <div className="photo-mini"><img src={photoB ? image(photoB, "thumbnail") : ""} alt="" /><b>{fmt(photoBObj)}</b></div>
            </div>
          </section>
          <section>
            <h3>Смешение</h3>
            <label className="filter-slider">
              <span>A</span>
              <input type="range" min={0} max={100} value={Math.round(blend * 100)} onChange={event => { setBlend(Number(event.target.value) / 100); setPlaying(false); }} />
              <span>B</span>
            </label>
            <b className="blend-value">{Math.round(blend * 100)}%</b>
          </section>
          <section>
            <h3>Последовательность</h3>
            <div className="seq-controls">
              <button className="primary" disabled={photosOfBin.length < 2} onClick={() => setPlaying(value => !value)}>
                {playing ? "⏸ Пауза" : "▶ Запуск"}
              </button>
              <button disabled={!playing} onClick={() => { setPlaying(false); setBlend(0); }}>⏹</button>
            </div>
            <label className="filter-slider">
              <span>Скорость</span>
              <input type="range" min={0.2} max={4} step={0.1} value={speed} onChange={event => setSpeed(Number(event.target.value))} />
              <b>{speed.toFixed(1)}×</b>
            </label>
            <label className="filter-enable">
              <input type="checkbox" checked={loop} onChange={event => setLoop(event.target.checked)} />
              <b>Зациклить</b>
            </label>
          </section>
          <section>
            <h3>Отображение</h3>
            <label className="filter-enable">
              <input type="checkbox" checked={wireframe} onChange={event => setWireframe(event.target.checked)} />
              <b>Wireframe</b>
            </label>
            <label className="filter-enable">
              <input type="checkbox" checked={showLandmarks} onChange={event => setShowLandmarks(event.target.checked)} />
              <b>Landmarks 106</b>
            </label>
            <label className="filter-enable">
              <input type="checkbox" checked={spin} onChange={event => setSpin(event.target.checked)} />
              <b>Авто-вращение</b>
            </label>
            <button className="ghost" onClick={() => currentBin && setCamera({ yaw: currentBin.camera.yaw_deg, elev: currentBin.camera.elevation_deg, dist: 3.2 })}>↺ Сбросить камеру</button>
          </section>
          <footer className="workspace-notice">
            <b>visualization-only</b>
            <span>Интерполированные кадры не участвуют в Stage 2 и не являются измерениями.</span>
          </footer>
        </aside>
        <main className="workspace-main">
          <div className="morph-canvas-wrap" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onWheel={onWheel}>
            <canvas ref={canvasRef} className="morph-canvas" />
            {loading && <div className="canvas-loading">Загрузка 3D-моделей…</div>}
            <div className="canvas-badge">{currentBin ? LABEL[currentBin.pose as Pose] : pose} · каноническая поза</div>
            <div className="canvas-caption a">{photoAObj ? `${photoAObj.date} · A` : "A"}</div>
            <div className="canvas-caption b">{photoBObj ? `${photoBObj.date} · B` : "B"}</div>
          </div>
          {message && <div className="workspace-error">{message}</div>}
        </main>
      </div>
    </div>
  );
}
