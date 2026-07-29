import { useEffect, useRef } from "react";
import * as THREE from "three";

export interface MeshPoint {
  x: number; y: number; z: number;
  /** Скаляр для тепловой карты: z-score или residual. undefined = нейтральный цвет. */
  value?: number;
}

interface Props {
  points106?: [number, number, number][];
  points134?: [number, number, number][];
  heatmapPoints?: MeshPoint[];
  wireframe?: boolean;
  showPoints?: boolean;
  heatmapStops?: { blueCyan: number; cyanGreen: number; greenRed: number; saturatedRed: number; maxReference: number };
  className?: string;
  backgroundColor?: string;
}

const DEFAULT_STOPS = { blueCyan: 0.25, cyanGreen: 0.5, greenRed: 0.75, saturatedRed: 1.0, maxReference: 0.12 };

/** Кусочно-линейная тепловая шкала: синий → голубой → зелёный → красный → тёмно-красный.
 * Пороги настраиваются (попап "Настройки тепловой карты" в ТЗ). Нормализованный
 * вход `t` в [0,1] — доля от `maxReference`. */
function heatColor(t: number, stops: typeof DEFAULT_STOPS): THREE.Color {
  const clamped = Math.min(1, Math.max(0, t));
  const stopsArr: [number, THREE.Color][] = [
    [0, new THREE.Color(0x1d4ed8)], // синий
    [stops.blueCyan, new THREE.Color(0x22d3ee)], // голубой
    [stops.cyanGreen, new THREE.Color(0x4ade80)], // зелёный
    [stops.greenRed, new THREE.Color(0xef4444)], // красный (яркий)
    [stops.saturatedRed, new THREE.Color(0x7f1d1d)], // тёмно-красный
  ];
  for (let i = 1; i < stopsArr.length; i++) {
    const [prevT, prevC] = stopsArr[i - 1];
    const [curT, curC] = stopsArr[i];
    if (clamped <= curT || i === stopsArr.length - 1) {
      const span = Math.max(1e-6, curT - prevT);
      const local = Math.min(1, Math.max(0, (clamped - prevT) / span));
      return prevC.clone().lerp(curC, local);
    }
  }
  return stopsArr[stopsArr.length - 1][1];
}

/** Реальный 3D-просмотрщик landmark-облака (106/134 точки из API) на three.js.
 * Поддерживает вращение мышью, зум колесом, каркас соединений и тепловую карту
 * по residual/z-score. Это не декоративный SVG — рендерит фактические
 * координаты, полученные от `/api/v1/photos/{id}` или `/api/v1/compare`. */
export default function MeshViewer({
  points106, points134, heatmapPoints, wireframe = true, showPoints = true,
  heatmapStops = DEFAULT_STOPS, className, backgroundColor = "#0d0d0f",
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef<{
    renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
    group: THREE.Group; frameId: number;
    rotation: { x: number; y: number }; dragging: boolean; lastX: number; lastY: number; distance: number;
  } | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(backgroundColor);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    container.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);
    scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
    dirLight.position.set(1, 1, 2);
    scene.add(dirLight);

    const state = {
      renderer, scene, camera, group, frameId: 0,
      rotation: { x: 0, y: 0 }, dragging: false, lastX: 0, lastY: 0, distance: 3.2,
    };
    stateRef.current = state;

    const resize = () => {
      const { clientWidth, clientHeight } = container;
      if (clientWidth === 0 || clientHeight === 0) return;
      renderer.setSize(clientWidth, clientHeight);
      camera.aspect = clientWidth / clientHeight;
      camera.updateProjectionMatrix();
    };
    resize();
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);

    const onPointerDown = (e: PointerEvent) => { state.dragging = true; state.lastX = e.clientX; state.lastY = e.clientY; };
    const onPointerUp = () => { state.dragging = false; };
    const onPointerMove = (e: PointerEvent) => {
      if (!state.dragging) return;
      state.rotation.y += (e.clientX - state.lastX) * 0.008;
      state.rotation.x += (e.clientY - state.lastY) * 0.008;
      state.rotation.x = Math.max(-1.4, Math.min(1.4, state.rotation.x));
      state.lastX = e.clientX; state.lastY = e.clientY;
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      state.distance = Math.max(1.0, Math.min(12, state.distance + e.deltaY * 0.0025));
    };
    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("wheel", onWheel, { passive: false });

    const animate = () => {
      group.rotation.y = state.rotation.y;
      group.rotation.x = state.rotation.x;
      camera.position.set(0, 0, state.distance);
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      state.frameId = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(state.frameId);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("wheel", onWheel);
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [backgroundColor]);

  useEffect(() => {
    const state = stateRef.current;
    if (!state) return;
    while (state.group.children.length) {
      const child = state.group.children.pop()!;
      state.group.remove(child);
      if (child instanceof THREE.Points || child instanceof THREE.LineSegments) {
        child.geometry.dispose();
        (child.material as THREE.Material).dispose();
      }
    }

    const sourcePoints: MeshPoint[] = heatmapPoints
      ?? (points134 ?? points106 ?? []).map(([x, y, z]) => ({ x, y, z }));
    if (sourcePoints.length === 0) return;

    const positions = new Float32Array(sourcePoints.length * 3);
    const colors = new Float32Array(sourcePoints.length * 3);
    sourcePoints.forEach((p, i) => {
      positions[i * 3] = p.x; positions[i * 3 + 1] = p.y; positions[i * 3 + 2] = p.z;
      const normalized = p.value !== undefined ? p.value / Math.max(1e-6, heatmapStops.maxReference) : 0.15;
      const color = heatColor(normalized, heatmapStops);
      colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
    });

    if (showPoints) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
      const material = new THREE.PointsMaterial({ size: 0.035, vertexColors: true, sizeAttenuation: true });
      state.group.add(new THREE.Points(geometry, material));
    }

    if (wireframe && sourcePoints.length > 3) {
      // Простая k-nearest-neighbour "сетка" для визуального каркаса: рисуем
      // линию к ближайшим 2 точкам каждой вершины. Это не anatomical mesh
      // topology (для этого нужен BFM face indexing из 3DDFA_V3), а
      // ориентировочный каркас, достаточный чтобы видеть форму облака.
      const linePositions: number[] = [];
      for (let i = 0; i < sourcePoints.length; i++) {
        const distances: { j: number; d: number }[] = [];
        for (let j = 0; j < sourcePoints.length; j++) {
          if (i === j) continue;
          const dx = sourcePoints[i].x - sourcePoints[j].x;
          const dy = sourcePoints[i].y - sourcePoints[j].y;
          const dz = sourcePoints[i].z - sourcePoints[j].z;
          distances.push({ j, d: dx * dx + dy * dy + dz * dz });
        }
        distances.sort((a, b) => a.d - b.d);
        for (const { j } of distances.slice(0, 2)) {
          linePositions.push(sourcePoints[i].x, sourcePoints[i].y, sourcePoints[i].z,
                             sourcePoints[j].x, sourcePoints[j].y, sourcePoints[j].z);
        }
      }
      const lineGeometry = new THREE.BufferGeometry();
      lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(linePositions, 3));
      const lineMaterial = new THREE.LineBasicMaterial({ color: 0x5591c7, transparent: true, opacity: 0.35 });
      state.group.add(new THREE.LineSegments(lineGeometry, lineMaterial));
    }
  }, [points106, points134, heatmapPoints, wireframe, showPoints, heatmapStops]);

  return <div ref={containerRef} className={className} style={{ width: "100%", height: "100%" }} />;
}

export { heatColor, DEFAULT_STOPS as DEFAULT_HEATMAP_STOPS };
