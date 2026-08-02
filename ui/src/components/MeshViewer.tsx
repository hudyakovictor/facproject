import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { evaluateGradient, type GradientModel } from "../gradient";
import { DEFAULT_HEATMAP_STOPS as SHARED_STOPS, heatRgb } from "../heatscale";

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
  /** Настраиваемый градиент; при наличии имеет приоритет над heatmapStops. */
  gradient?: GradientModel;
  className?: string;
  backgroundColor?: string;
}


const DEFAULT_STOPS = SHARED_STOPS;

/** Кусочно-линейная тепловая шкала: синий → голубой → зелёный → красный → тёмно-красный.
 * Пороги настраиваются (попап "Настройки тепловой карты" в ТЗ). Нормализованный
 * вход `t` в [0,1] — доля от `maxReference`. */
/** Цвет по настраиваемому градиенту (с посегментной резкостью).
 * Используется, когда модель градиента задана; иначе — старая логика. */
function gradientColor(t: number, model: GradientModel): THREE.Color {
  // См. примечание в heatColor: компоненты градиента заданы в sRGB.
  const { r, g, b } = evaluateGradient(model, t);
  return new THREE.Color().setRGB(r, g, b, THREE.SRGBColorSpace);
}

function heatColor(t: number, stops: typeof DEFAULT_STOPS): THREE.Color {
  // Математика вынесена в `heatscale.ts` (без three.js), чтобы легенда и
  // настройки не тянули 471 KB рендерера в бандл.
  //
  // ⚠️ `setRGB` с явным SRGBColorSpace, а НЕ конструктор `new THREE.Color(r,g,b)`:
  // конструктор трактует компоненты как linear-sRGB и применяет конверсию,
  // из-за чего 0x1d4ed8 превращался в 0x5f96ed. Значения heatRgb — sRGB.
  const { r, g, b } = heatRgb(t, stops);
  return new THREE.Color().setRGB(r, g, b, THREE.SRGBColorSpace);
}

/** 🧹 Полная рекурсивная утилизация содержимого группы (DEV_FIX_TZ P1.3).
 *
 * Обрабатывает ЛЮБОЙ Object3D, а не только Points/LineSegments/Mesh: обходит
 * поддеревья, освобождает geometry, все материалы (включая массивы материалов)
 * и их текстуры. Без этого каждая перестройка сцены оставляла в памяти
 * буферы GPU — заметная утечка на мешах в 35 709 вершин. */
function disposeGroupChildren(group: THREE.Group): void {
  while (group.children.length) {
    const child = group.children.pop()!;
    group.remove(child);
    child.traverse((node: THREE.Object3D) => {
      const withGeometry = node as Partial<THREE.Mesh>;
      withGeometry.geometry?.dispose?.();
      const material = (node as Partial<THREE.Mesh>).material;
      const materials = Array.isArray(material) ? material : material ? [material] : [];
      for (const mat of materials) {
        for (const value of Object.values(mat)) {
          if (value instanceof THREE.Texture) value.dispose();
        }
        mat.dispose();
      }
      if (node instanceof THREE.Light) node.dispose?.();
    });
  }
}

/** Реальный 3D-просмотрщик landmark-облака ИЛИ полного BFM-меша на three.js.
 * Поддерживает вращение мышью, зум колесом, каркас/поверхность и тепловую
 * карту по residual/z-score. Это не декоративный SVG — рендерит фактические
 * координаты, полученные от `/api/v1/photos/{id}`, `/api/v1/photos/{id}/mesh`
 * или `/api/v1/compare[/full_mesh]`. */
export default function MeshViewer({
  points106, points134, heatmapPoints, fullMesh, morphT = 0, wireframe = true, showPoints = true,
  heatmapStops = DEFAULT_STOPS, gradient, className, backgroundColor = "#0d0d0f",
}: Props) {
  /** Единая точка вычисления цвета: градиент, если задан, иначе — легаси-шкала. */
  const colorFor = (t: number): THREE.Color =>
    gradient ? gradientColor(t, gradient) : heatColor(t, heatmapStops);

  const containerRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef<{
    renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
    group: THREE.Group; frameId: number;
    rotation: { x: number; y: number }; dragging: boolean; lastX: number; lastY: number; distance: number;
  } | null>(null);

  // P1.2 (DEV_FIX_TZ 2.2): backgroundColor читается через ref, поэтому смена
  // цвета фона больше НЕ пересоздаёт WebGL-контекст (раньше это роняло старый
  // renderer вместе с ResizeObserver и оставляло stale closure).
  const backgroundColorRef = useRef(backgroundColor);
  backgroundColorRef.current = backgroundColor;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(backgroundColorRef.current);
    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    container.appendChild(renderer.domElement);

    // P1.3 (DEV_FIX_TZ 2.3): освещение живёт в собственной группе на сцене и
    // никогда не попадает в `group`, который целиком очищается при каждой
    // перестройке геометрии. Раньше очистка обрабатывала только Points/
    // LineSegments/Mesh, а прочие Object3D утекали.
    const group = new THREE.Group();
    scene.add(group);
    const lights = new THREE.Group();
    lights.add(new THREE.AmbientLight(0xffffff, 0.9));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
    dirLight.position.set(1, 1, 2);
    lights.add(dirLight);
    scene.add(lights);

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
      disposeGroupChildren(group);
      lights.traverse(obj => { if (obj instanceof THREE.Light) obj.dispose?.(); });
      scene.clear();
      renderer.dispose();
      renderer.forceContextLoss();
      container.removeChild(renderer.domElement);
      stateRef.current = null;
    };
  }, []);

  // Смена фона — дешёвое обновление уже существующей сцены, без пересоздания
  // renderer (см. P1.2 выше).
  useEffect(() => {
    const state = stateRef.current;
    if (!state) return;
    state.scene.background = new THREE.Color(backgroundColor);
  }, [backgroundColor]);

  /** P3.10 (DEV_FIX_TZ): k-NN каркас — O(n²), поэтому считается только при
   * фактическом изменении точек, а не на каждый ре-рендер (например при
   * движении слайдера морфинга). Возвращает `null`, когда каркас неприменим.
   *
   * P3.7: при <4 точках каркас невозможен — раньше это происходило молча;
   * теперь пишется явное предупреждение в консоль. */
  const knnLinePositions = useMemo<number[] | null>(() => {
    if (fullMesh && fullMesh.vertices.length > 0) return null;
    const sourcePoints: MeshPoint[] = heatmapPoints
      ?? (points134 ?? points106 ?? []).map(([x, y, z]) => ({ x, y, z }));
    if (sourcePoints.length === 0) return null;
    if (sourcePoints.length <= 3) {
      if (wireframe) {
        console.warn(
          `[MeshViewer] каркас отключён: получено ${sourcePoints.length} точек, ` +
          "для k-NN связности нужно минимум 4.",
        );
      }
      return null;
    }
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
    return linePositions;
  }, [points106, points134, heatmapPoints, fullMesh, wireframe]);

  useEffect(() => {
    const state = stateRef.current;
    if (!state) return undefined;
    disposeGroupChildren(state.group);

    if (fullMesh && fullMesh.vertices.length > 0) {
      // ---- Real BFM surface: THREE.Mesh with the authentic 70,789-triangle
      // topology from 3ddfa_v3/assets/face_model.tar.gz, not an approximation.
      const vertexCount = fullMesh.vertices.length;
      const positions = new Float32Array(vertexCount * 3);
      const colors = new Float32Array(vertexCount * 3);
      const maxRef = Math.max(1e-6, gradient?.maxReference ?? heatmapStops.maxReference);
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
        const color = colorFor(normalized);
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
      // P1.4 (DEV_FIX_TZ 2.4): эффект ОБЯЗАН вернуть cleanup на каждом пути
      // выхода — иначе в React StrictMode (и при размонтировании) созданная
      // геометрия/материалы остаются в памяти.
      return () => disposeGroupChildren(state.group);
    }

    const sourcePoints: MeshPoint[] = heatmapPoints
      ?? (points134 ?? points106 ?? []).map(([x, y, z]) => ({ x, y, z }));
    if (sourcePoints.length === 0) return () => disposeGroupChildren(state.group);

    const positions = new Float32Array(sourcePoints.length * 3);
    const colors = new Float32Array(sourcePoints.length * 3);
    sourcePoints.forEach((p, i) => {
      positions[i * 3] = p.x; positions[i * 3 + 1] = p.y; positions[i * 3 + 2] = p.z;
      const reference = gradient?.maxReference ?? heatmapStops.maxReference;
      const normalized = p.value !== undefined ? p.value / Math.max(1e-6, reference) : 0.15;
      const color = colorFor(normalized);
      colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b;
    });

    if (showPoints) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
      const material = new THREE.PointsMaterial({ size: 0.035, vertexColors: true, sizeAttenuation: true });
      state.group.add(new THREE.Points(geometry, material));
    }

    if (wireframe && knnLinePositions && knnLinePositions.length > 0) {
      // Приближённый k-NN каркас по landmarks — используется только когда
      // полная BFM-топология (fullMesh) недоступна для этого фото/пары.
      // P3.10: сами связи считаются в useMemo (O(n²)), а не на каждый рендер.
      const lineGeometry = new THREE.BufferGeometry();
      lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(knnLinePositions, 3));
      const lineMaterial = new THREE.LineBasicMaterial({ color: 0x5591c7, transparent: true, opacity: 0.35 });
      state.group.add(new THREE.LineSegments(lineGeometry, lineMaterial));
    }
    return () => disposeGroupChildren(state.group);
  }, [points106, points134, heatmapPoints, fullMesh, morphT, wireframe, showPoints, heatmapStops, gradient, knnLinePositions]);


  return <div ref={containerRef} className={className} style={{ width: "100%", height: "100%" }} />;
}

export { heatColor, gradientColor, DEFAULT_STOPS as DEFAULT_HEATMAP_STOPS };
