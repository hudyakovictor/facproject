import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import {
  interpolatePositions,
  residualColors,
  type HeatmapScale,
  type MeshPayload,
} from "./meshData";
import styles from "./morphing.module.css";

/**
 * 3D-холст морфинга (§12.2).
 *
 * Позиции вершин пересчитываются на CPU в существующий буфер и помечаются как
 * изменённые: 35 709 вершин это 107 127 чисел, и выделять новый массив на кадр
 * означало бы шестьдесят сборок мусора в секунду. Материал и геометрия
 * создаются один раз на пару, а не на каждый кадр скраббера.
 *
 * 🚨 WARNING: изображение между якорями построено интерполяцией. Это
 * визуализация гипотезы о плавном переходе, а не наблюдение. Подпись об этом
 * выводится поверх холста постоянно, а не прячется в подсказку.
 */

export interface LayerState {
  mesh: boolean;
  wireframe: boolean;
  heatmap: boolean;
  landmarks: boolean;
}

export interface HeatmapSettings {
  max: number;
  scale: HeatmapScale;
}

function MorphMesh({
  payload,
  t,
  layers,
  heatmap,
}: {
  payload: MeshPayload;
  t: number;
  layers: LayerState;
  heatmap: HeatmapSettings;
}) {
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    // Позиции копируются: буфер будет переписываться каждый кадр, а исходные
    // массивы A и B должны остаться нетронутыми.
    geo.setAttribute("position", new THREE.BufferAttribute(payload.verticesA.slice(), 3));
    geo.setAttribute(
      "color",
      new THREE.BufferAttribute(new Float32Array(payload.vertexCount * 3), 3),
    );
    geo.setIndex(new THREE.BufferAttribute(payload.triangles, 1));
    geo.computeVertexNormals();
    return geo;
  }, [payload]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  /** Цвета зависят только от настроек тепловой карты, а не от позиции скраббера. */
  useEffect(() => {
    const colors = geometry.getAttribute("color") as THREE.BufferAttribute;
    const target = colors.array as Float32Array;
    if (layers.heatmap) {
      residualColors(payload.residuals, heatmap.max, heatmap.scale, target);
    } else {
      target.fill(0.72);
    }
    colors.needsUpdate = true;
  }, [geometry, payload, layers.heatmap, heatmap.max, heatmap.scale]);

  useFrame(() => {
    const position = geometry.getAttribute("position") as THREE.BufferAttribute;
    interpolatePositions(
      payload.verticesA,
      payload.verticesB,
      t,
      position.array as Float32Array,
    );
    position.needsUpdate = true;
    geometry.computeVertexNormals();
  });

  return (
    <group>
      {layers.mesh && (
        <mesh geometry={geometry}>
          <meshStandardMaterial
            vertexColors
            roughness={0.62}
            metalness={0.05}
            side={THREE.DoubleSide}
            flatShading={false}
          />
        </mesh>
      )}
      {layers.wireframe && (
        <mesh geometry={geometry}>
          <meshBasicMaterial wireframe color="#4dd0e1" transparent opacity={0.28} />
        </mesh>
      )}
    </group>
  );
}

/**
 * Восстановление после потери контекста WebGL (§12.2).
 *
 * Драйвер может отобрать контекст в любой момент — при переключении на
 * дискретную видеокарту, при спящем режиме. Без обработчика холст остаётся
 * чёрным навсегда, и это выглядит как «модель пустая».
 */
function ContextLossGuard({ onLost }: { onLost: (lost: boolean) => void }) {
  const { gl } = useThree();

  useEffect(() => {
    const canvas = gl.domElement;
    const handleLost = (event: Event) => {
      event.preventDefault();
      onLost(true);
    };
    const handleRestored = () => onLost(false);
    canvas.addEventListener("webglcontextlost", handleLost);
    canvas.addEventListener("webglcontextrestored", handleRestored);
    return () => {
      canvas.removeEventListener("webglcontextlost", handleLost);
      canvas.removeEventListener("webglcontextrestored", handleRestored);
    };
  }, [gl, onLost]);

  return null;
}

export function MorphCanvas({
  payload,
  t,
  layers,
  heatmap,
  lightIntensity,
  onContextLost,
  canvasRef,
}: {
  payload: MeshPayload;
  t: number;
  layers: LayerState;
  heatmap: HeatmapSettings;
  lightIntensity: number;
  onContextLost: (lost: boolean) => void;
  canvasRef: React.MutableRefObject<HTMLCanvasElement | null>;
}) {
  const controls = useRef(null);

  return (
    <div className={styles.canvasHost}>
      <Canvas
        camera={{ position: [0, 0, 3.2], fov: 40 }}
        dpr={[1, 2]}
        gl={{ antialias: true, preserveDrawingBuffer: true }}
        onCreated={({ gl }) => {
          canvasRef.current = gl.domElement;
        }}
      >
        <ContextLossGuard onLost={onContextLost} />
        <ambientLight intensity={0.55 * lightIntensity} />
        <directionalLight position={[2, 3, 4]} intensity={1.1 * lightIntensity} />
        <directionalLight position={[-3, -1, -2]} intensity={0.35 * lightIntensity} />
        <MorphMesh payload={payload} t={t} layers={layers} heatmap={heatmap} />
        <OrbitControls ref={controls} enablePan enableZoom makeDefault />
      </Canvas>
    </div>
  );
}
