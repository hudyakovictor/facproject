import { useEffect, useRef } from "react";
import * as THREE from "three";

export interface MeshPoint {
  x: number; y: number; z: number;
  /** Скаляр для тепловой карты: z-score или residual. undefined = нейтральный цвет. */
  value?: number;
}

export interface FullMeshData {
  vertices: [number, number, number][];
  triangles: [number, number, number][];
  /** Опционально: значение на вершину для окраски тепловой картой (например, residual). */
  vertexValues?: number[];
  /** Опционально: вторая форма (та же топология/вершин-в-соответствии) для
   * линейного морфинга A→B. Требует `morphT` для управления интерполяцией. */
  verticesTarget?: [number, number, number][];
}

interface Props {
  points106?: [number, number, number][];
  points134?: [number, number, number][];
  heatmapPoints?: MeshPoint[];
  /** Реальная BFM-топология (35 709 вершин / 70 789 треугольников из /api/v1/photos/{id}/mesh
   * или /api/v1/compare/full_mesh). Когда задано, рендерится настоящая
   * поверхность (THREE.Mesh) вместо приближённого k-NN каркаса по landmarks. */
  fullMesh?: FullMeshData;
  /** Доля морфинга A→B в [0,1]: 0 = чистая A, 1 = выровненная B. Требует
   * `fullMesh.verticesTarget`. Игнорируется, если target не задан. */
  morphT?: number;
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

/** Реальный 3D-просмотрщик landmark-облака ИЛИ полного BFM-меша на three.js.
 * Поддерживает вращение мышью, зум колесом, каркас/поверхность и тепловую
 * карту по residual/z-score. Это не декоративный SVG — рендерит фактические
 * координаты, полученные от `/api/v1/photos/{id}`, `/api/v1/photos/{id}/mesh`
 * или `/api/v1/compare[/full_mesh]`. */
export default function MeshViewer({
  points106, points134, heatmapPoints, fullMesh, morphT = 0, wireframe = true, showPoints = true,
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
      if (child instanceof THREE.Points || child instanceof THREE.LineSegments || child instanceof THREE.Mesh) {
        child.geometry.dispose();
        (child.material as THREE.Material).dispose();
      }
    }

    if (fullMesh && fullMesh.vertices.length > 0) {
      // ---- Real BFM surface: THREE.Mesh with the authentic 70,789-triangle
      // topology from 3ddfa_v3/assets/face_model.tar.gz, not an approximation.
      const vertexCount = fullMesh.vertices.length;
      const positions = new Float32Array(vertexCount * 3);
      const colors = new Float32Array(vertexCount * 3);
      const maxRef = Math.max(1e-6, heatmapStops.maxReference);
      const target = fullMesh.verticesTarget;
      const t = target ? Math.min(1, Math.max(0, morphT)) : 0;
      fullMesh.vertices.forEach(([x, y, z], i) => {
        // Linear morph A→B when a target shape is provided (real BFM
        // vertex correspondence — same topology, Kabsch-aligned by the
        // backend — so per-vertex lerp is anatomically meaningful, not a
        // pixel-space cross-fade).
        const [tx, ty, tz] = target ? target[i] : [x, y, z];
        positions[i * 3] = x + (tx - x) * t;
        positions[i * 3 + 1] = y + (ty - y) * t;
        positions[i * 3 + 2] = z + (tz - z) * t;
        const raw = fullMesh.vertexValues?.[i];
        const normalized = raw !== undefined ? raw / maxRef : 0.1;
        const color = heatColor(normalized, heatmapStops);
        colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
      });
      const indices = new Uint32Array(fullMesh.triangles.length * 3);
      fullMesh.triangles.forEach(([a, b, c], i) => {
        indices[i * 3] = a; indices[i * 3 + 1] = b; indices[i * 3 + 2] = c;
      });

      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

      geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
      geometry.setIndex(new THREE.BufferAttribute(indices, 1));
      geometry.computeVertexNormals();
      const material = new THREE.MeshStandardMaterial({
        vertexColors: true, side: THREE.DoubleSide, roughness: 0.75, metalness: 0.05,
        flatShading: false,
      });
      const mesh = new THREE.Mesh(geometry, material);
      state.group.add(mesh);

      if (wireframe) {
        const wireGeometry = new THREE.WireframeGeometry(geometry);
        const wireMaterial = new THREE.LineBasicMaterial({ color: 0x5591c7, transparent: true, opacity: 0.15 });
        state.group.add(new THREE.LineSegments(wireGeometry, wireMaterial));
      }

      if (showPoints) {
        const pointsMaterial = new THREE.PointsMaterial({ size: 0.008, vertexColors: true, sizeAttenuation: true });
        state.group.add(new THREE.Points(geometry.clone(), pointsMaterial));
      }
      return;
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
      // Приближённый k-NN каркас по landmarks — используется только когда
      // полная BFM-топология (fullMesh) недоступна для этого фото/пары.
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
  }, [points106, points134, heatmapPoints, fullMesh, morphT, wireframe, showPoints, heatmapStops]);


  return <div ref={containerRef} className={className} style={{ width: "100%", height: "100%" }} />;
}

export { heatColor, DEFAULT_STOPS as DEFAULT_HEATMAP_STOPS };
