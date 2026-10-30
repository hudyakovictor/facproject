import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";
import type { HeatSettings, MeshData, Topology } from "../types";
import { vertexNormals } from "../heat";

// One request in flight. Throttle (not debounce!) so playback continues without WebGL.
export function CPUPreview({
  a,
  b,
  reference,
  t,
  heat,
  data,
  hi,
  version,
}: {
  a: string;
  b: string;
  reference: string;
  t: number;
  heat: HeatSettings;
  data: { a: MeshData; b: MeshData; top: Topology };
  hi: number;
  version: string;
}) {
  const preset =
    heat.view === "left"
      ? -35
      : heat.view === "right"
        ? 35
        : heat.view === "profile"
          ? 85
          : 0;
  const [orbit, setOrbit] = useState({ yaw: preset, pitch: 0, zoom: 1 });
  useEffect(() => setOrbit({ yaw: preset, pitch: 0, zoom: 1 }), [preset]);
  const latest = useRef({ a, b, reference, t, heat, hi, orbit, data, version });
  latest.current = { a, b, reference, t, heat, hi, orbit, data, version };
  const [request, setRequest] = useState(latest.current),
    [shown, setShown] = useState(latest.current);
  const busy = useRef(true),
    lastKey = useRef(""),
    drag = useRef<{ x: number; y: number; yaw: number; pitch: number } | null>(
      null,
    );
  // Only PNG-affecting parameters may enter the request key. Landmark toggles
  // do not change img.src and therefore cannot release an in-flight image lock.
  const key = (f: typeof request) =>
    JSON.stringify([
      f.a,
      f.b,
      f.reference,
      f.t.toFixed(3),
      f.hi,
      f.orbit,
      f.version,
      ...(
        [
          "vmin",
          "palette",
          "enabled",
          "metric",
          "gamma",
          "opacity",
          "outsideOpacity",
          "onlyAbove",
          "inverse",
          "texture",
          "wireframe",
          "smoothing",
          "low",
          "mid",
          "high",
          "midPosition",
        ] as const
      ).map((k) => f.heat[k]),
    ]);
  useEffect(() => {
    lastKey.current = key(request);
    const timer = setInterval(() => {
      const next = latest.current,
        newKey = key(next);
      if (!busy.current && newKey !== lastKey.current) {
        busy.current = true;
        lastKey.current = newKey;
        setRequest(next);
      }
    }, 160);
    return () => clearInterval(timer);
  }, []);
  const p = new URLSearchParams({
    revision: request.version,
    other: request.b,
    reference: request.reference,
    t: request.t.toFixed(3),
    vmax: String(request.hi),
    vmin: String(request.heat.vmin),
    palette: request.heat.palette,
    heatmap: String(request.heat.enabled),
    metric: request.heat.metric,
    gamma: String(request.heat.gamma),
    opacity: String(request.heat.opacity),
    outsideOpacity: String(request.heat.outsideOpacity),
    onlyAbove: String(request.heat.onlyAbove),
    inverse: String(request.heat.inverse),
    texture: String(request.heat.texture),
    wireframe: String(request.heat.wireframe),
    smoothing: String(request.heat.smoothing),
    low: request.heat.low,
    mid: request.heat.mid,
    high: request.heat.high,
    midPosition: String(request.heat.midPosition),
    yaw: String(request.orbit.yaw),
    pitch: String(request.orbit.pitch),
    zoom: String(request.orbit.zoom),
  });
  const overlays = useMemo(() => {
    const { a, b, top } = shown.data,
      n = a.vertices.length,
      v = new Float32Array(n);
    for (let i = 0; i < n; i++)
      v[i] = a.vertices[i] * (1 - shown.t) + b.vertices[i] * shown.t;
    const normals = vertexNormals(v, top.triangles);
    const y = (shown.orbit.yaw * Math.PI) / 180,
      p = (shown.orbit.pitch * Math.PI) / 180,
      sy = Math.sin(y),
      cy = Math.cos(y),
      sp = Math.sin(p),
      cp = Math.cos(p),
      scale = (512 / 3.6) * shown.orbit.zoom;
    const project = (i: number) => {
      const x = v[i * 3],
        y = v[i * 3 + 1],
        z = v[i * 3 + 2],
        y1 = y * cp - z * sp,
        z1 = y * sp + z * cp;
      const nx = normals[i * 3],
        ny = normals[i * 3 + 1],
        nz = normals[i * 3 + 2],
        nz1 = ny * sp + nz * cp;
      return {
        x: (x * cy + z1 * sy) * scale + 256,
        y: -y1 * scale + 512 * 0.41,
        visible: -nx * sy + nz1 * cy > -0.04,
      };
    };
    return [
      ["ldm68", heat.ldm68, "#efbd6d"],
      ["ldm106", heat.ldm106, "#60e4d3"],
      ["ldm134", heat.ldm134, "#c39afa"],
    ]
      .filter(([, enabled]) => enabled)
      .map(([name, _, color]) => ({
        name: String(name),
        color: String(color),
        points: (top.landmarks[String(name)] || []).map((idx, i) => ({
          ...project(idx),
          index: i,
        })),
      }));
  }, [shown, heat.ldm68, heat.ldm106, heat.ldm134]);
  return (
    <div className="cpu-preview">
      <div
        className="cpu-image-wrap"
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          drag.current = {
            x: e.clientX,
            y: e.clientY,
            yaw: orbit.yaw,
            pitch: orbit.pitch,
          };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (drag.current) {
            const d = drag.current;
            setOrbit((o) => ({
              ...o,
              yaw: d.yaw + (e.clientX - d.x) * 0.45,
              pitch: Math.max(
                -65,
                Math.min(65, d.pitch + (e.clientY - d.y) * 0.4),
              ),
            }));
          }
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onWheel={(e) => {
          e.stopPropagation();
          setOrbit((o) => ({
            ...o,
            zoom: Math.max(0.55, Math.min(2.2, o.zoom - e.deltaY * 0.001)),
          }));
        }}
      >
        <img
          alt="CPU-рендер настоящего 3D-меша"
          src={"/api/photos/" + request.a + "/preview?" + p}
          onLoad={() => {
            setShown(request);
            busy.current = false;
          }}
          onError={() => {
            busy.current = false;
          }}
        />
        <svg
          viewBox="0 0 512 512"
          preserveAspectRatio="xMidYMid meet"
          className="cpu-landmarks"
        >
          {overlays.map((layer) => (
            <g key={layer.name}>
              {layer.points
                .filter((p) => p.visible)
                .map((p) => (
                  <circle
                    key={p.index}
                    cx={p.x}
                    cy={p.y}
                    r={heat.pointSize * 0.7}
                    fill={layer.color}
                    fillOpacity={0.95}
                    stroke="#10232c"
                    strokeWidth={0.25}
                  >
                    <title>
                      {layer.name} · {p.index} · индекс с нуля
                    </title>
                  </circle>
                ))}
            </g>
          ))}
        </svg>
      </div>
      <span>
        <AlertCircle size={11} /> CPU-превью · до 6 кадров/с · мышь — вращение
        {heat.wireframe ? " · редкая сетка" : ""}
      </span>
    </div>
  );
}
