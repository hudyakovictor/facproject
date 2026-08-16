import { Suspense, useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { useQuery } from "@tanstack/react-query";
import { BlockedState, LoadingState } from "./states";
import { parseObj, type ParsedMesh } from "./objParser";
import { describeError } from "./errorDetail";
import styles from "./faceMesh3d.module.css";

/**
 * 3D-панель кадра (§10.2, правая область инспектора).
 *
 * Раньше здесь стояла честная заглушка: mesh-артефакт «не входит в ответ API».
 * Это было верно для `/timeline`, но `mesh.obj` доступен как артефакт кадра —
 * реальная реконструкция Stage 1 на 35 709 вершин. Панель грузит именно её.
 *
 * 🚨 WARNING: модель показывается только если файл реально есть. Ни при каких
 * условиях не рисуется «примерное лицо»: сгенерированная голова выглядела бы
 * как результат измерения, не будучи им.
 */

export type RenderMode = "3d-wireframe" | "3d-solid" | "uv-texture" | "heatmap";

function MeshBody({ mesh, wireframe }: { mesh: ParsedMesh; wireframe: boolean }) {
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(mesh.positions, 3));
    geo.setIndex(new THREE.BufferAttribute(mesh.indices, 1));
    geo.computeVertexNormals();
    geo.center();
    return geo;
  }, [mesh]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh geometry={geometry}>
      {wireframe ? (
        <meshBasicMaterial wireframe color="#4dd0e1" />
      ) : (
        <meshStandardMaterial color="#b8c4cc" roughness={0.65} metalness={0.05} side={THREE.DoubleSide} />
      )}
    </mesh>
  );
}

export function FaceMesh3D({
  photoId,
  mode = "3d-solid",
  className = "",
}: {
  photoId: string;
  mode?: RenderMode;
  className?: string;
}) {
  const [wireframe, setWireframe] = useState(mode === "3d-wireframe");

  const query = useQuery({
    queryKey: ["photo-mesh-obj", photoId],
    queryFn: async () => {
      const response = await fetch(
        `/api/v1/photos/${encodeURIComponent(photoId)}/artifacts/mesh.obj`,
      );
      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}`) as Error & { status?: number };
        error.status = response.status;
        throw error;
      }
      return parseObj(await response.text());
    },
    retry: false,
    staleTime: Infinity,
  });

  if (query.isPending) {
    return (
      <div className={`${styles.host} ${className}`}>
        <LoadingState text="Загрузка модели кадра…" />
      </div>
    );
  }

  if (query.isError) {
    const detail = describeError(query.error);
    return (
      <div className={`${styles.host} ${className}`}>
        <BlockedState
          title="Модель кадра недоступна"
          description={
            detail.status === 404
              ? "Файл mesh.obj для этого кадра не создан. Синтетическая модель не показывается: она была бы демонстрацией, а не результатом реконструкции."
              : detail.message
          }
        />
      </div>
    );
  }

  const mesh = query.data;

  return (
    <div className={`${styles.host} ${className}`}>
      <div className={styles.toolbar}>
        <span className={styles.meta}>
          {mesh.vertexCount.toLocaleString("ru-RU")} вершин ·{" "}
          {mesh.triangleCount.toLocaleString("ru-RU")} треугольников
        </span>
        <button
          type="button"
          className={styles.toggle}
          aria-pressed={wireframe}
          onClick={() => setWireframe((current) => !current)}
        >
          Каркас
        </button>
      </div>
      <div className={styles.canvasHost}>
        <Suspense fallback={null}>
          <Canvas camera={{ position: [0, 0, 3], fov: 40 }} dpr={[1, 2]}>
            <ambientLight intensity={0.6} />
            <directionalLight position={[2, 3, 4]} intensity={1.1} />
            <directionalLight position={[-3, -1, -2]} intensity={0.3} />
            <MeshBody mesh={mesh} wireframe={wireframe} />
            <OrbitControls enablePan enableZoom makeDefault />
          </Canvas>
        </Suspense>
      </div>
      <p className={styles.note}>
        Реконструкция Stage 1 из mesh.obj. Вращение и приближение — мышью. Форма
        отражает результат подгонки модели к кадру и сама по себе не является
        суждением о личности.
      </p>
    </div>
  );
}
