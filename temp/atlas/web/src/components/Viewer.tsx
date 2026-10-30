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
import { calculate, decodeHeat, graph, type HeatStats, type ServerHeat } from "../heat";
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
// Пресеты вида поворачивают МОДЕЛЬ, а не камеру: знак совпадает с
// configs/pose_profiles.yaml (положительный yaw — нос вправо на снимке)
// и с серверным рендером server/rendering.py:rasterize.
const VIEW_YAW: Record<string, number> = {
  front: 0,
  left: -35,
  right: 35,
  profile: 85,
};
function CameraRig() {
  const { camera, invalidate } = useThree();
  const ref = useRef<any>(null);
  useEffect(() => {
    camera.position.set(0, 0.02, 4.4);
    camera.lookAt(0, -0.35, 0);
    if (ref.current) {
      ref.current.target.set(0, -0.35, 0);
      ref.current.update();
    }
    invalidate();
  }, [camera, invalidate]);
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
  imageTextureB,
  textureMix,
  textureEnabled,
  pose,
}: {
  computed: ReturnType<typeof calculate>;
  imageTexture: THREE.Texture | null;
  imageTextureB: THREE.Texture | null;
  textureMix: number;
  textureEnabled: boolean;
  /** Ракурс модели в градусах: [yaw, pitch, roll] с фото плюс пресет вида. */
  pose: [number, number, number];
  a: MeshData;
  b: MeshData;
  reference: MeshData;
  t: number;
  topology: Topology;
  heat: HeatSettings;
  onStats: (s: HeatStats) => void;
}) {
  const { invalidate } = useThree();
  const groupRef = useRef<THREE.Group>(null);
  const [poseYaw, posePitch, poseRoll] = pose;
  // Тот же порядок осей, что в server/models/tddfa.py:row_rotation_matrix:
  // R = Rz(roll) · Ry(yaw) · Rx(pitch), каноническая голова смотрит на +Z.
  useEffect(() => {
    const g = groupRef.current;
    if (!g) return;
    const rad = Math.PI / 180;
    const matrix = new THREE.Matrix4()
      .makeRotationZ(poseRoll * rad)
      .multiply(new THREE.Matrix4().makeRotationY(poseYaw * rad))
      .multiply(new THREE.Matrix4().makeRotationX(posePitch * rad));
    g.quaternion.setFromRotationMatrix(matrix);
    invalidate();
  }, [poseYaw, posePitch, poseRoll, invalidate]);
  const geometry = useMemo(() => new THREE.BufferGeometry(), []);
  const whiteTexture = useMemo(() => {
    const tex = new THREE.DataTexture(
      new Uint8Array([255, 255, 255, 255]),
      1,
      1,
      THREE.RGBAFormat,
    );
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.needsUpdate = true;
    return tex;
  }, []);
  const shaderRef = useRef<THREE.WebGLProgramParametersWithUniforms | null>(null);
  const textureBRef = useRef<THREE.Texture>(whiteTexture);
  const textureMixRef = useRef(0);
  textureBRef.current = imageTextureB ?? imageTexture ?? whiteTexture;
  textureMixRef.current = textureMix;
  const onBeforeCompile = useMemo(
    () => (shader: THREE.WebGLProgramParametersWithUniforms) => {
      shader.uniforms.atlasTextureB = { value: textureBRef.current };
      shader.uniforms.atlasTextureMix = { value: textureMixRef.current };
      shader.fragmentShader = shader.fragmentShader.replace(
        "#include <common>",
        "#include <common>\nuniform sampler2D atlasTextureB;\nuniform float atlasTextureMix;",
      ).replace(
        "#include <map_fragment>",
        `#ifdef USE_MAP
vec4 atlasSampleA = texture2D(map, vMapUv);
vec4 atlasSampleB = texture2D(atlasTextureB, vMapUv);
diffuseColor *= mix(atlasSampleA, atlasSampleB, clamp(atlasTextureMix, 0.0, 1.0));
#endif`,
      );
      shaderRef.current = shader;
    },
    [],
  );
  useEffect(() => {
    const uniforms = shaderRef.current?.uniforms;
    if (uniforms?.atlasTextureB) uniforms.atlasTextureB.value = textureBRef.current;
    if (uniforms?.atlasTextureMix) uniforms.atlasTextureMix.value = textureMixRef.current;
    invalidate();
  }, [imageTexture, imageTextureB, textureMix, textureEnabled, invalidate]);
  useEffect(() => () => whiteTexture.dispose(), [whiteTexture]);
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
    <group ref={groupRef}>
      <mesh geometry={geometry} onPointerMissed={() => setHover(null)}>
        <meshStandardMaterial
          vertexColors={!textureEnabled || heat.enabled}
          map={textureEnabled ? imageTexture ?? whiteTexture : null}
          onBeforeCompile={onBeforeCompile}
          customProgramCacheKey={() => "atlas-uv-crossfade-v1"}
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
    setHeat = useStore((s) => s.setHeat),
    set = useStore((s) => s.set);
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
    routeIndex = route.indexOf(seg.a),
    reference = mode === "morph"
      ? routeIndex > 0
        ? route[routeIndex - 1]
        : (ps[Math.max(0, index - 1)]?.id || seg.a)
      : heat.reference === "first"
        ? ps[0]?.id
        : heat.reference === "previous"
          ? ps[Math.max(0, index - 1)]?.id
          : heat.reference;
  const versions = [seg.a, seg.b, reference]
    .map((id) => photos.find((p) => p.id === id)?.meta?.feature_key || "")
    .join("|");
  // Ракурс берётся от углов наклона головы на фото (ручная правка в редакторе
  // перекрывает распознавание), пресет вида добавляет поворот модели.
  const poseOf = (id: string): [number, number, number] => {
    const p = photos.find((x) => x.id === id);
    if (!p) return [0, 0, 0];
    const o = p.angle_override || {};
    return [
      Number(o.yaw ?? p.angles?.yaw ?? 0),
      Number(o.pitch ?? p.angles?.pitch ?? 0),
      Number(o.roll ?? p.angles?.roll ?? 0),
    ];
  };
  const zero: [number, number, number] = [0, 0, 0];
  const poseA = heat.viewFromPhoto ? poseOf(seg.a) : zero,
    poseB =
      heat.viewFromPhoto && seg.b !== seg.a ? poseOf(seg.b) : poseA,
    photoPose: [number, number, number] = [
      poseA[0] + (poseB[0] - poseA[0]) * t,
      poseA[1] + (poseB[1] - poseA[1]) * t,
      poseA[2] + (poseB[2] - poseA[2]) * t,
    ],
    presetYaw = VIEW_YAW[heat.view] ?? 0,
    pose: [number, number, number] = [
      photoPose[0] + presetYaw,
      photoPose[1],
      photoPose[2],
    ];
  const [uvPair, setUvPair] = useState<{
    a: string; b: string; textureA: THREE.Texture; textureB: THREE.Texture;
  } | null>(null);
  const textureCache = useRef(new Map<string, THREE.Texture>());
  const textureLoads = useRef(new Map<string, Promise<THREE.Texture>>());
  const loadUVTexture = useMemo(() => (id: string): Promise<THREE.Texture> => {
    const cached = textureCache.current.get(id);
    if (cached) return Promise.resolve(cached);
    const pending = textureLoads.current.get(id);
    if (pending) return pending;
    let attempt = 0;
    const request = (): Promise<THREE.Texture> => new Promise((resolve, reject) => {
      const load = () => {
        attempt++;
        new THREE.TextureLoader().load(`/api/photos/${id}/uv-texture?v=3`, (tex) => {
          tex.flipY = true;
          tex.colorSpace = THREE.SRGBColorSpace;
          tex.magFilter = THREE.LinearFilter;
          tex.minFilter = THREE.LinearMipmapLinearFilter;
          tex.generateMipmaps = true;
          tex.needsUpdate = true;
          textureCache.current.set(id, tex);
          resolve(tex);
        }, undefined, () => {
          if (attempt < 6) setTimeout(load, Math.min(800 * attempt, 4000));
          else reject(new Error(`UV texture failed for ${id}`));
        });
      };
      load();
    });
    const promise = request().finally(() => textureLoads.current.delete(id));
    textureLoads.current.set(id, promise);
    return promise;
  }, []);
  const [textureStatus, setTextureStatus] = useState<"loading" | "ready" | "failed">("loading");
  const [textureProgress, setTextureProgress] = useState({ loaded: 0, total: 0 });
  const textureIds = Array.from(new Set(
    (route.length >= 2 ? route : [seg.a, seg.b])
      .filter((id): id is string => Boolean(id)),
  ));
  const textureIdsKey = textureIds.join("|");
  // Preload every morph keyframe texture, like the reference morphing viewer's
  // sequence_textures array; playback no longer changes atlases mid-request.
  useEffect(() => {
    if (!heat.photoTexture) {
      setTextureStatus("ready");
      set({ textureStatus: "ready" });
      setTextureProgress({ loaded: 0, total: 0 });
      return;
    }
    if (!textureIds.length) { setTextureStatus("failed"); set({ textureStatus: "failed" }); return; }
    let dead = false, loaded = 0;
    setTextureStatus("loading");
    set({ textureStatus: "loading" });
    setTextureProgress({ loaded: 0, total: textureIds.length });
    Promise.all(textureIds.map(async (id) => {
      await loadUVTexture(id);
      loaded++;
      if (!dead) setTextureProgress({ loaded, total: textureIds.length });
    })).then(() => {
      if (!dead) {
        setTextureStatus("ready");
        set({ textureStatus: "ready" });
      }
    }).catch(() => {
      if (!dead) {
        setTextureStatus("failed");
        set({ textureStatus: "failed" });
      }
    });
    return () => { dead = true; };
  }, [textureIdsKey, heat.photoTexture, loadUVTexture, set]);
  useEffect(() => {
    if (!heat.photoTexture || !seg.a) return;
    let dead = false;
    const idA = seg.a, idB = seg.b || seg.a;
    Promise.all([loadUVTexture(idA), loadUVTexture(idB)]).then(([textureA, textureB]) => {
      if (!dead) setUvPair({ a: idA, b: idB, textureA, textureB });
    }).catch(() => { /* status is reported by the preloader above */ });
    return () => { dead = true; };
  }, [seg.a, seg.b, heat.photoTexture, loadUVTexture]);
  useEffect(() => () => {
    textureCache.current.forEach((texture) => texture.dispose());
    textureCache.current.clear();
    textureLoads.current.clear();
  }, []);
  const pairMatches = uvPair?.a === seg.a && uvPair?.b === seg.b;
  // Read already-preloaded atlases synchronously when a segment changes.
  // Waiting for a new Promise.all here used to substitute the white fallback
  // for one render and flash the surface black/gray at every keyframe.
  const imageTexture = textureCache.current.get(seg.a) ?? (uvPair?.a === seg.a ? uvPair.textureA : null);
  const imageTextureB = textureCache.current.get(seg.b) ?? (pairMatches ? uvPair.textureB : imageTexture);
  const textureMix = imageTexture && imageTextureB && mode === "morph" ? t : 0;
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
  const serverHeat = heat.metric === "normal" || heat.weighting === "calibrated";
  const [serverValues, setServerValues] = useState<ServerHeat | null>(null);
  // Normal displacement and calibrated weights have one implementation —
  // server/heat.py. The browser only colorizes what the backend computed.
  useEffect(() => {
    if (!serverHeat || !seg.a || !reference) {
      setServerValues(null);
      return;
    }
    let dead = false;
    const query = new URLSearchParams({
      other: seg.b || seg.a,
      reference,
      morphing: String(mode === "morph"),
      metric: heat.metric,
      weighting: heat.weighting,
      smoothing: String(heat.smoothing),
      normalizeScale: String(heat.normalizeScale),
    });
    fetch(`/api/photos/${seg.a}/heat?${query}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((payload) => {
        if (!dead) setServerValues(decodeHeat(payload));
      })
      .catch(() => {
        if (!dead) setServerValues(null);
      });
    return () => {
      dead = true;
    };
  }, [
    serverHeat,
    seg.a,
    seg.b,
    reference,
    mode,
    heat.metric,
    heat.weighting,
    heat.smoothing,
    heat.normalizeScale,
    versions,
  ]);
  const computed = useMemo(
    () =>
      data
        ? calculate(
            data.a,
            data.b,
            data.ref,
            t,
            heat,
            data.top,
            noiseThreshold,
            mode === "morph",
            serverValues,
          )
        : null,
    [data, t, heat, noiseThreshold, mode, serverValues],
  );
  useEffect(() => {
    if (computed) onStats(computed.stats);
  }, [computed, onStats]);
  const cpu = data ? (
    <CPUPreview
      version={versions}
      morphing={mode === "morph"}
      a={seg.a}
      b={seg.b}
      reference={reference}
      t={t}
      heat={heat}
      data={data}
      hi={computed?.stats.hi || heat.vmax}
      baseYaw={pose[0]}
      basePitch={pose[1]}
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
        <div className="segmented" aria-label="Пресет поворота модели">
          {[
            ["front", "Фронт", "нос по центру"],
            ["left", "−35°", "нос влево на 35°"],
            ["right", "+35°", "нос вправо на 35°"],
            ["profile", "Профиль", "нос вправо на 85°"],
          ].map(([v, label, hint]) => (
            <button
              key={v}
              title={
                hint +
                (heat.viewFromPhoto
                  ? " · добавляется к углам с фото"
                  : " · углы с фото не учитываются")
              }
              className={heat.view === v ? "active" : ""}
              onClick={() => setHeat({ view: v as any })}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="segmented" aria-label="Источник ракурса">
          <button
            title={
              "Поворачивать модель на yaw/pitch/roll головы, распознанные на фото" +
              (heat.viewFromPhoto ? " (включено)" : " (выключено)")
            }
            className={heat.viewFromPhoto ? "active" : ""}
            onClick={() => setHeat({ viewFromPhoto: !heat.viewFromPhoto })}
          >
            Ракурс с фото
          </button>
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
                  imageTextureB={imageTextureB}
                  textureMix={textureMix}
                  textureEnabled={heat.photoTexture}
                  pose={pose}
                />
                <CameraRig />
              </Canvas>
            </GLBoundary>
          ))}
      </div>
      {loading && (
        <div className="mesh-loading">
          <LoaderCircle size={16} className="spin" /> Загрузка меша
          <div className="indeterminate-progress" role="progressbar" aria-label="Загрузка меша"><i /></div>
        </div>
      )}
      <div className="viewport-top-caption">
        <span className="eyebrow">КАНОНИЧЕСКАЯ ГЕОМЕТРИЯ</span>
        <span
          className="pose-badge"
          title={
            "Поворот модели: " +
            (heat.viewFromPhoto
              ? "углы головы с фото" +
                (presetYaw ? " плюс пресет " + presetYaw + "°" : "")
              : "только пресет вида " + presetYaw + "°") +
            " · знак yaw по pose_profiles.yaml (плюс — нос вправо)"
          }
        >
          {heat.viewFromPhoto ? "ракурс с фото" : "ракурс по пресету"} · yaw{" "}
          {pose[0].toFixed(1)}° · pitch {pose[1].toFixed(1)}° · roll{" "}
          {pose[2].toFixed(1)}°
        </span>
        {heat.photoTexture && <span className={`texture-state ${textureStatus}`} title={textureStatus === "failed" ? "Не удалось получить UV-текстуру. Проверьте обработку фото и серверный кэш." : "Источник: исходные пиксели, запечённые в UV-атлас 3DDFA_V3"}>{textureStatus === "ready" ? "UV · текстура загружена" : textureStatus === "loading" ? `UV · ${textureProgress.loaded}/${textureProgress.total}` : "UV · ошибка загрузки"}</span>}
        {heat.photoTexture && textureStatus === "loading" && <div className="texture-progress" role="progressbar" aria-label="Загрузка текстур маршрута" aria-valuemin={0} aria-valuemax={textureProgress.total} aria-valuenow={textureProgress.loaded}><i style={{ width: `${textureProgress.total ? textureProgress.loaded / textureProgress.total * 100 : 0}%` }} /></div>}
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
          Исходные пиксели запекаются по треугольникам в канонический UV-атлас
          3DDFA_V3. В CPU fallback то же фото, но выборкой по вершинам — мягче.
        </small>
      </div>
      <div className="field-label">
        <span>Масштаб модели</span>
        <Toggle
          label="Нормировать каждый меш по собственному IOD"
          checked={h.normalizeScale}
          onChange={(normalizeScale) => set({ normalizeScale })}
        />
        <small>
          Выключено — в карте и морфинге сохранены различия IOD; включите, чтобы смотреть только относительную форму. Исходный IOD также указан ниже.
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
        <span>{(stats?.lo ?? h.vmin).toFixed(4)}</span>
        <span>Δ / IOD₀</span>
        <span>{(stats?.hi || h.vmax).toFixed(4)}</span>
      </div>
      <Slider
        label="Нижний порог"
        value={stats?.lo ?? h.vmin}
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
        <div title="Не применяется к нормализованной геометрии; показывает исходную оценку модели">
          <span>IOD кадр / эталон</span>
          <b>{stats ? `${stats.scaleChangePct > 0 ? "+" : ""}${stats.scaleChangePct.toFixed(1)}%` : "—"}</b>
        </div>
      </div>
    </aside>
  );
}
