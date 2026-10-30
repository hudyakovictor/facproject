import React, {
  useEffect,
  useMemo,
  useState,
  useRef,
  memo,
  type ReactNode,
} from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import * as THREE from "three";
import {
  Camera,
  RotateCcw,
  Box,
  LoaderCircle,
  AlertCircle,
  Layers,
  ChevronDown,
} from "lucide-react";
import { getMesh, getTopology } from "../api";
import { useStore, morphSegment } from "../store";
import type { MeshData, Topology, HeatSettings } from "../types";
import { calculate, graph, type HeatStats } from "../heat";
import { Empty, Slider, Toggle } from "./ui";
import { CPUPreview } from "./CPUPreview";
import { supportsWebGL } from "../graphics";

class GLBoundary extends React.Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
function CameraRig({ view }: { view: string }) {
  const { camera, invalidate } = useThree();
  const ref = useRef<any>(null);
  useEffect(() => {
    const yaw =
      view === "left"
        ? -35
        : view === "right"
          ? 35
          : view === "profile"
            ? 85
            : 0;
    const angle = (yaw * Math.PI) / 180;
    camera.position.set(Math.sin(angle) * 4.4, 0.02, Math.cos(angle) * 4.4);
    camera.lookAt(0, -0.35, 0);
    if (ref.current) {
      ref.current.target.set(0, -0.35, 0);
      ref.current.update();
    }
    invalidate();
  }, [view, camera, invalidate]);
  return (
    <OrbitControls
      ref={ref}
      target={[0, -0.35, 0]}
      enableDamping
      dampingFactor={0.12}
      minDistance={2}
      maxDistance={12}
      makeDefault
    />
  );
}
function FaceObject({
  a,
  b,
  reference,
  t,
  topology,
  heat,
  onStats,
  computed,
  imageTexture,
  textureEnabled,
}: {
  computed: ReturnType<typeof calculate>;
  imageTexture: THREE.Texture | null;
  textureEnabled: boolean;
  a: MeshData;
  b: MeshData;
  reference: MeshData;
  t: number;
  topology: Topology;
  heat: HeatSettings;
  onStats: (s: HeatStats) => void;
}) {
  const { invalidate } = useThree();
  const geometry = useMemo(() => new THREE.BufferGeometry(), []);
  const [hover, setHover] = useState<{
    model: string;
    index: number;
    position: number[];
  } | null>(null);
  const result = computed;
  useEffect(() => {
    geometry.setIndex(new THREE.BufferAttribute(graph(topology).indices, 1));
    // Keep the model's canonical 3DDFA UV layout; source pixels are baked into
    // that atlas server-side. Never replace template UVs with image-space coords.
    if (topology.uv)
      geometry.setAttribute(
        "uv",
        new THREE.BufferAttribute(new Float32Array(topology.uv.flat()), 2),
      );
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(result.positions, 3),
    );
    geometry.setAttribute("color", new THREE.BufferAttribute(result.colors, 3));
    geometry.computeVertexNormals();
    geometry.computeBoundingSphere();
    invalidate();
  }, [geometry, result, topology, imageTexture, onStats, invalidate]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  const layers = [
    ["ldm68", heat.ldm68, "#efbd6d"],
    ["ldm106", heat.ldm106, "#60e4d3"],
    ["ldm134", heat.ldm134, "#c39afa"],
  ] as const;
  return (
    <group>
      <mesh geometry={geometry} onPointerMissed={() => setHover(null)}>
        <meshStandardMaterial
          vertexColors={!textureEnabled || heat.enabled}
          map={textureEnabled ? imageTexture : null}
          roughness={0.8}
          metalness={0.04}
          side={THREE.DoubleSide}
          polygonOffset
          polygonOffsetFactor={1}
          polygonOffsetUnits={1}
        />
      </mesh>
      {heat.wireframe && (
        <mesh geometry={geometry}>
          <meshBasicMaterial
            color="#bad3df"
            wireframe
            transparent
            opacity={0.14}
            depthWrite={false}
          />
        </mesh>
      )}
      {layers
        .filter((l) => l[1])
        .map(([key, _, color]) => {
          const indices = topology.landmarks[key] || [];
          const ps = new Float32Array(
            indices.flatMap((i) => [
              result.positions[i * 3],
              result.positions[i * 3 + 1],
              result.positions[i * 3 + 2] + 0.005,
            ]),
          );
          return (
            <points
              key={key}
              onPointerMove={(e) => {
                e.stopPropagation();
                const i = e.index ?? 0;
                setHover({
                  model: key,
                  index: i,
                  position: [ps[i * 3], ps[i * 3 + 1], ps[i * 3 + 2]],
                });
              }}
              onPointerOut={() => setHover(null)}
            >
              <bufferGeometry>
                <bufferAttribute attach="attributes-position" args={[ps, 3]} />
              </bufferGeometry>
              <pointsMaterial
                color={color}
                size={heat.pointSize}
                sizeAttenuation={false}
                depthWrite={false}
              />
            </points>
          );
        })}
      {hover && (
        <Html
          position={hover.position as [number, number, number]}
          distanceFactor={5}
          style={{ pointerEvents: "none" }}
        >
          <div className="point-tooltip">
            {hover.model} · {hover.index}
            <small>индекс с нуля</small>
          </div>
        </Html>
      )}
    </group>
  );
}
export const Viewer = memo(function Viewer({
  sceneId,
  onStats,
}: {
  sceneId: string;
  onStats: (s: HeatStats) => void;
}) {
  const activeId = useStore((s) => s.activeId),
    route = useStore((s) => s.route),
    head = useStore((s) => s.playhead),
    mode = useStore((s) => s.mode),
    heat = useStore((s) => s.heat),
    easing = useStore((s) => s.easing),
    photos = useStore((s) => s.photos),
    group = useStore((s) => s.group),
    edges = useStore((s) => s.edges),
    setHeat = useStore((s) => s.setHeat);
  const linked =
    edges.some((e) => e.target === sceneId && e.targetHandle === "mesh") &&
    edges.some((e) => e.target === "recon" && e.targetHandle === "photos");
  const ps = photos
    .filter(
      (p) => (group === "__all" || p.group === group) && p.status === "ready",
    )
    .sort(
      (a, b) =>
        (a.date || "9999").localeCompare(b.date || "9999") ||
        a.name.localeCompare(b.name),
    );
  let seg =
    mode === "morph" && route.length >= 2
      ? morphSegment(route, head)
      : { a: activeId, b: activeId, t: 0 };
  let t = easing === "smooth" ? seg.t * seg.t * (3 - 2 * seg.t) : seg.t;
  const index = ps.findIndex((p) => p.id === seg.a),
    reference =
      heat.reference === "first"
        ? ps[0]?.id
        : heat.reference === "previous"
          ? ps[Math.max(0, index - 1)]?.id
          : heat.reference;
  const versions = [seg.a, seg.b, reference]
    .map((id) => photos.find((p) => p.id === id)?.meta?.feature_key || "")
    .join("|");
  // Feature key changes when the photo is reprocessed; without it the browser
  // keeps serving the stale atlas for an hour.
  const textureVersion =
    photos.find((p) => p.id === seg.a)?.meta?.feature_key || "";
  const [imageTexture, setImageTexture] = useState<THREE.Texture | null>(null);
  const [textureStatus, setTextureStatus] = useState<"loading" | "ready" | "failed">("loading");
  useEffect(() => {
    if (!seg.a) { setImageTexture(null); setTextureStatus("failed"); return; }
    let dead = false, attempt = 0, retry: ReturnType<typeof setTimeout>;
    setTextureStatus("loading"); setImageTexture(null);
    const load = () => {
      attempt++;
      new THREE.TextureLoader().load(
        `/api/photos/${seg.a}/uv-texture?v=${textureVersion}`,
        (tex) => {
          if (dead) { tex.dispose(); return; }
          tex.flipY = true;
          tex.colorSpace = THREE.SRGBColorSpace;
          tex.magFilter = THREE.LinearFilter;
          tex.minFilter = THREE.LinearMipmapLinearFilter;
          tex.generateMipmaps = true;
          setImageTexture(tex); setTextureStatus("ready");
        },
        undefined,
        () => {
          if (dead) return;
          if (attempt < 6) retry = setTimeout(load, Math.min(800 * attempt, 4000));
          else { setImageTexture(null); setTextureStatus("failed"); }
        },
      );
    };
    load();
    return () => { dead = true; clearTimeout(retry); };
  }, [seg.a, textureVersion]);
  useEffect(() => () => imageTexture?.dispose(), [imageTexture]);
  const [noiseThreshold, setNoiseThreshold] = useState<number[] | null>(null);
  useEffect(() => {
    const load = () => fetch("/api/calibration/noise").then(r=>r.json()).then(x=>setNoiseThreshold(x.threshold || null)).catch(()=>setNoiseThreshold(null));
    load(); window.addEventListener("atlas-noise-calibrated", load);
    return () => window.removeEventListener("atlas-noise-calibrated", load);
  }, []);
  const [data, setData] = useState<{
    a: MeshData;
    b: MeshData;
    ref: MeshData;
    top: Topology;
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [hideBadges, setHideBadges] = useState(false);
  useEffect(() => {
    if (!linked || !seg.a || !seg.b || !reference) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      getMesh(seg.a, photos.find((p) => p.id === seg.a)?.meta?.feature_key),
      getMesh(seg.b, photos.find((p) => p.id === seg.b)?.meta?.feature_key),
      getMesh(
        reference,
        photos.find((p) => p.id === reference)?.meta?.feature_key,
      ),
      getTopology(),
    ])
      .then(([a, b, ref, top]) => {
        if (!cancelled) setData({ a, b, ref, top });
      })
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [seg.a, seg.b, reference, linked, versions]);
  const computed = useMemo(
    () =>
      data ? calculate(data.a, data.b, data.ref, t, heat, data.top, noiseThreshold) : null,
    [data, t, heat, noiseThreshold],
  );
  useEffect(() => {
    if (computed) onStats(computed.stats);
  }, [computed, onStats]);
  const cpu = data ? (
    <CPUPreview
      version={versions}
      a={seg.a}
      b={seg.b}
      reference={reference}
      t={t}
      heat={heat}
      data={data}
      hi={computed?.stats.hi || heat.vmax}
    />
  ) : null;
  if (!linked)
    return (
      <Empty
        title="Подключите меш"
        detail="Соедините выход mesh плагина 3DDFA_V3 со входом этой сцены."
      />
    );
  if (!activeId || !ps.length)
    return (
      <Empty
        title="Загрузите серию фотографий"
        detail="JPG, PNG, WebP или ZIP с группами. Обработка идёт на CPU."
      />
    );
  if (error) return <Empty title="Не удалось загрузить меш" detail={error} />;
  return (
    <div className="viewer-area">
      <div className="viewport-actions nodrag">
        <div className="segmented" aria-label="Режим отображения поверхности">
          <button
            className={heat.enabled && !heat.photoTexture ? "active" : ""}
            title="Только геометрическая тепловая карта"
            onClick={() => setHeat({ enabled: true, photoTexture: false })}
          >Карта</button>
          <button
            className={heat.photoTexture && !heat.enabled ? "active" : ""}
            title={imageTexture ? "Только текстура исходного фото в каноническом UV" : "UV-текстура ещё загружается или недоступна"}
            onClick={() => setHeat({ photoTexture: true, enabled: false })}
          >Фото UV</button>
          <button
            className={heat.photoTexture && heat.enabled ? "active" : ""}
            title="Исходная фототекстура с полупрозрачным слоем геометрических различий"
            onClick={() => setHeat({ photoTexture: true, enabled: true })}
          >Фото + Δ</button>
          <button
            className={heat.wireframe ? "active" : ""}
            title="Показать рёбра сетки"
            onClick={() => setHeat({ wireframe: !heat.wireframe })}
          >Сетка</button>
        </div>
        <div className="segmented">
          {[
            ["front", "Фронт"],
            ["left", "−35°"],
            ["right", "+35°"],
            ["profile", "Профиль"],
          ].map(([v, label]) => (
            <button
              key={v}
              className={heat.view === v ? "active" : ""}
              onClick={() => setHeat({ view: v as any })}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="webgl-host nodrag nowheel" data-testid="three-view">
        {data &&
          (!supportsWebGL() ? (
            cpu
          ) : (
            <GLBoundary fallback={cpu}>
              <Canvas
                frameloop="demand"
                dpr={[1, 1.5]}
                gl={{
                  antialias: true,
                  preserveDrawingBuffer: true,
                  alpha: true,
                }}
                camera={{
                  position: [0, 0.12, 5.5],
                  fov: 34,
                  near: 0.1,
                  far: 100,
                }}
                fallback={cpu}
              >
                <ambientLight intensity={0.65} />
                <directionalLight position={[3, 4, 5]} intensity={1.7} />
                <directionalLight position={[-4, 1, 2]} intensity={0.55} />
                <FaceObject
                  computed={computed!}
                  a={data.a}
                  b={data.b}
                  reference={data.ref}
                  t={t}
                  topology={data.top}
                  heat={heat}
                  onStats={onStats}
                  imageTexture={imageTexture}
                  textureEnabled={heat.photoTexture}
                />
                <CameraRig view={heat.view} />
              </Canvas>
            </GLBoundary>
          ))}
      </div>
      {loading && (
        <div className="mesh-loading">
          <LoaderCircle size={16} className="spin" /> Загрузка меша
        </div>
      )}
      <div className="viewport-top-caption">
        <span className="eyebrow">КАНОНИЧЕСКАЯ ГЕОМЕТРИЯ</span>
        {heat.photoTexture && <span className={`texture-state ${textureStatus}`} title={textureStatus === "failed" ? "Не удалось получить UV-текстуру. Проверьте обработку фото и серверный кэш." : "Источник: исходные пиксели, запечённые в UV-атлас 3DDFA_V3"}>{textureStatus === "ready" ? "UV · текстура загружена" : textureStatus === "loading" ? "UV · загружается…" : "UV · ошибка загрузки"}</span>}
        {mode === "morph" ? (
          <span className="morph-badge">
            <span className="status-dot" /> Морфинг · {Math.round(t * 100)}%{" "}
            <span className="muted">синтетический кадр</span>
          </span>
        ) : (
          <span className="source-badge">
            Исходный кадр ·{" "}
            {ps.find((p) => p.id === activeId)?.date || "без даты"}
          </span>
        )}
      </div>
      <div className="viewport-footer">
        <div className="axis-gizmo">
          <span className="axis-y">Y</span>
          <span className="axis-x">X</span>
          <span className="axis-z">Z</span>
          <i />
        </div>
        <span>
          35 709 вершин <b>·</b> 70 789 граней <b>·</b>{" "}
          {mode === "morph" ? "интерполяция ID + exp" : "3DDFA_V3"}
        </span>
        <button
          className="icon-btn nodrag"
          title="Сохранить PNG"
          onClick={(e) => {
            const canvas = e.currentTarget
              .closest(".viewer-area")
              ?.querySelector("canvas");
            if (canvas) {
              const a = document.createElement("a");
              a.download = "atlas-mesh.png";
              a.href = canvas.toDataURL("image/png");
              a.click();
            }
          }}
        >
          <Camera size={15} />
        </button>
      </div>
    </div>
  );
});
export function HeatControls({ stats }: { stats: HeatStats | null }) {
  const h = useStore((s) => s.heat),
    set = useStore((s) => s.setHeat),
    photos = useStore((s) => s.photos),
    group = useStore((s) => s.group);
  const ps = photos
    .filter(
      (p) => (group === "__all" || p.group === group) && p.status === "ready",
    )
    .sort(
      (a, b) =>
        (a.date || "9999").localeCompare(b.date || "9999") ||
        a.name.localeCompare(b.name),
    );
  const maxLimit = Math.max(0.02, (stats?.max || 0.05) * 2, h.vmax * 1.2);
  const histMax = Math.max(...(stats?.hist || [1]));
  const [more, setMore] = useState(false);
  const [calOpen, setCalOpen] = useState(false), [calInfo, setCalInfo] = useState<any>(null),
    [calBusy, setCalBusy] = useState(false), [calError, setCalError] = useState("");
  const allReady = photos.filter((p) => p.status === "ready" && !p.demo);
  const [participants, setParticipants] = useState(() => Array.from({length:7}, (_, i) => ({label:`Человек ${i+1}`, photo_ids:[] as string[]})));
  useEffect(() => { fetch("/api/calibration/noise").then(r=>r.json()).then(setCalInfo).catch(()=>{}); }, []);
  const runCalibration = async () => {
    setCalBusy(true); setCalError("");
    try { const r=await fetch("/api/calibration/noise",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({participants})});
      const j=await r.json(); if(!r.ok) throw new Error(j.detail || "Не удалось откалибровать");
      setCalInfo(j); window.dispatchEvent(new Event("atlas-noise-calibrated"));
    } catch(e:any) { setCalError(e.message); } finally { setCalBusy(false); }
  };
  return (
    <aside className="heat-controls nodrag nowheel">
      <div className="section-title">
        <span>
          <Layers size={13} /> Тепловая карта
        </span>
        <Toggle
          label="Включить тепловую карту"
          checked={h.enabled}
          onChange={(enabled) => set({ enabled })}
        />
      </div>
      <label className="field-label">
        Изменение геометрии
        <select
          value={h.metric}
          onChange={(e) => set({ metric: e.target.value as any })}
        >
          <option value="distance">Расстояние по вершинам</option>
          <option value="identity">Только форма · α_id</option>
          <option value="normal">Смещение по нормали</option>
        </select>
      </label>
      <div className="field-label">
        <span>Текстура исходного фото</span>
        <Toggle
          label="Фототекстура по исходным пикселям"
          checked={h.photoTexture}
          onChange={(photoTexture) => set({ photoTexture })}
        />
        <small>
          Исходные пиксели запекаются по треугольникам в канонический UV-атлас 3DDFA_V3. Только WebGL-просмотр.
        </small>
      </div>
      <div className="noise-calibration">
        <div className="flex between"><b>Калибровка шума меша</b><button className="text-button" onClick={()=>setCalOpen(!calOpen)}>{calOpen ? "Свернуть" : "Настроить"}</button></div>
        <small>{calInfo?.participant_count ? `Калибровка: ${calInfo.participant_count} человек · ${calInfo.photo_count} фото` : "Нужны 7 человек, по 2–3 ракурса каждого"}</small>
        <div className="flex between mini"><span>Вычитать шум из геометрической Δ</span><Toggle label="Компенсация шума" checked={h.noiseCorrection} onChange={(noiseCorrection)=>set({noiseCorrection})}/></div>
        {calOpen && <div className="calibration-form">
          <p>Для каждого человека выберите 2–3 кадра с разными поворотами. Межличностную форму алгоритм не вычитает: сравнивает каждый кадр с медианой его участника и использует 75-й перцентиль повторяемости меша.</p>
          {participants.map((person, i)=><label key={i}><input aria-label={`Метка участника ${i+1}`} value={person.label} onChange={e=>setParticipants(xs=>xs.map((x,k)=>k===i?{...x,label:e.target.value}:x))}/><select multiple size={3} value={person.photo_ids} onChange={e=>{const values=Array.from(e.target.selectedOptions,o=>o.value);setParticipants(xs=>xs.map((x,k)=>k===i?{...x,photo_ids:values}:x));}}>{allReady.map(p=><option key={p.id} value={p.id}>{p.group} · {p.date || p.name}</option>)}</select></label>)}
          {allReady.length < 14 && <small className="cal-warning">В библиотеке сейчас {allReady.length} готовых несинтетических фото; для 7×2 выберите/импортируйте не менее 14.</small>}
          {calError && <small className="cal-error">{calError}</small>}
          <button className="primary" disabled={calBusy || allReady.length<14 || participants.some(p=>p.photo_ids.length<2||p.photo_ids.length>3)} onClick={runCalibration}>{calBusy?"Считаю шум…":"Рассчитать и сохранить baseline"}</button>
        </div>}
      </div>
      <label className="field-label">
        Относительно
        <select
          aria-label="Эталон тепловой карты"
          value={h.reference}
          onChange={(e) => set({ reference: e.target.value })}
        >
          <option value="first">Первого фото группы</option>
          <option value="previous">Предыдущего по дате</option>
          {ps.map((p) => (
            <option key={p.id} value={p.id}>
              {p.date || p.name}
            </option>
          ))}
        </select>
      </label>
      <div className="histogram">
        <svg viewBox="0 0 200 38" preserveAspectRatio="none">
          {stats?.hist.map((v, i) => (
            <rect
              key={i}
              x={i * 5.55}
              y={38 - (v / histMax) * 34}
              width={4}
              height={(v / histMax) * 34}
              fill={i / 36 < h.vmin / (stats?.max || 1) ? "#334656" : "#4a8d9d"}
            />
          ))}
        </svg>
      </div>
      <div
        className={"heat-gradient " + h.palette}
        style={
          h.palette === "custom"
            ? {
                background: `linear-gradient(90deg,${h.low},${h.mid} ${h.midPosition * 100}%,${h.high})`,
              }
            : undefined
        }
      />
      <div className="flex between mini muted">
        <span>{h.vmin.toFixed(4)}</span>
        <span>Δ / IOD₀</span>
        <span>{(stats?.hi || h.vmax).toFixed(4)}</span>
      </div>
      <Slider
        label="Нижний порог"
        value={h.vmin}
        min={0}
        max={Math.max(maxLimit * 0.9, 0.005)}
        step={0.0001}
        onChange={(v) =>
          set({
            vmin: Math.min(
              v,
              h.auto ? (stats?.hi || maxLimit) - 0.0001 : h.vmax - 0.0001,
            ),
          })
        }
      />
      <Slider
        label="Верхний порог"
        value={h.auto ? stats?.hi || h.vmax : h.vmax}
        min={h.vmin + 0.0001}
        max={maxLimit}
        step={0.0001}
        onChange={(vmax) => set({ vmax, auto: false })}
      />
      <div className="flex between mini">
        <span>Авто по перцентилю</span>
        <Toggle
          label="Автоматические пороги"
          checked={h.auto}
          onChange={(auto) => set({ auto, vmax: stats?.hi || h.vmax })}
        />
      </div>
      {h.auto && (
        <Slider
          label="Перцентиль"
          value={h.percentile}
          min={50}
          max={100}
          step={1}
          onChange={(percentile) => set({ percentile })}
        />
      )}
      <div className="palette-options">
        {["turbo", "viridis", "coolwarm", "custom"].map((p) => (
          <button
            key={p}
            title={p}
            className={
              "palette-swatch " + p + (h.palette === p ? " chosen" : "")
            }
            onClick={() => set({ palette: p })}
            style={
              p === "custom"
                ? {
                    background: `linear-gradient(90deg,${h.low},${h.mid},${h.high})`,
                  }
                : undefined
            }
          />
        ))}
      </div>
      <Slider
        label="Прозрачность"
        value={h.opacity}
        min={0}
        max={1}
        onChange={(opacity) => set({ opacity })}
        format={(v) => Math.round(v * 100) + "%"}
      />
      <button className="disclosure" onClick={() => setMore(!more)}>
        <ChevronDown
          size={12}
          style={{ transform: more ? "rotate(180deg)" : "" }}
        />{" "}
        {more ? "Скрыть" : "Гамма, сглаживание, цвета"}
      </button>
      {more && (
        <div className="extra-settings">
          <Slider
            label="Гамма"
            value={h.gamma}
            min={0.2}
            max={3}
            step={0.05}
            onChange={(gamma) => set({ gamma })}
          />
          <Slider
            label="Вне диапазона"
            value={h.outsideOpacity}
            min={0}
            max={1}
            onChange={(outsideOpacity) => set({ outsideOpacity })}
          />
          <Slider
            label="Сглаживание"
            value={h.smoothing}
            min={0}
            max={5}
            step={1}
            onChange={(smoothing) => set({ smoothing })}
          />
          <label className="check-row">
            <input
              type="checkbox"
              checked={h.inverse}
              onChange={(e) => set({ inverse: e.target.checked })}
            />{" "}
            Инверсия
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={h.onlyAbove}
              onChange={(e) => set({ onlyAbove: e.target.checked })}
            />{" "}
            Только выше порога
          </label>
          {h.palette === "custom" && (
            <>
              <div className="color-stops">
                {(["low", "mid", "high"] as const).map((k) => (
                  <input
                    key={k}
                    aria-label={k}
                    type="color"
                    value={h[k]}
                    onChange={(e) => set({ [k]: e.target.value })}
                  />
                ))}
              </div>
              <Slider
                label="Позиция среднего цвета"
                value={h.midPosition}
                min={0.05}
                max={0.95}
                onChange={(midPosition) => set({ midPosition })}
              />
            </>
          )}
        </div>
      )}
      <div className="controls-divider" />
      <div className="section-title">Ключевые точки</div>
      {[
        ["ldm68", "ldm68", "#e8ba6c"],
        ["ldm106", "ldm106", "#61dfcd"],
        ["ldm134", "ldm134", "#bd9cf4"],
      ].map(([key, label, color]) => (
        <div className="landmark-control" key={key}>
          <Toggle
            label={"Точки " + label}
            checked={Boolean(h[key as keyof HeatSettings])}
            onChange={(value) => set({ [key]: value })}
          />
          <i style={{ background: color }} />
          <span>{label}</span>
          <span className="muted">{key.slice(3)}</span>
        </div>
      ))}
      <div className="landmark-control disabled">
        <Toggle disabled checked={false} onChange={() => {}} />
        <i style={{ background: "#657586" }} />
        <span>MediaPipe / FAN</span>
        <small>позже</small>
      </div>
      <Slider
        label="Размер точек"
        value={h.pointSize}
        min={0.7}
        max={5}
        step={0.1}
        onChange={(pointSize) => set({ pointSize })}
      />
      <div className="heat-summary">
        <div>
          <span>Среднее</span>
          <b>{stats?.mean.toFixed(4) || "—"}</b>
        </div>
        <div>
          <span>P95</span>
          <b>{stats?.p95.toFixed(4) || "—"}</b>
        </div>
        <div>
          <span>Макс.</span>
          <b>{stats?.max.toFixed(4) || "—"}</b>
        </div>
      </div>
    </aside>
  );
}
