import { Suspense, lazy } from "react";
import { t } from "../i18n";
import type { ComponentProps } from "react";
import type MeshViewerType from "./MeshViewer";

/** Ленивая обёртка 3D-просмотрщика.
 *
 * `MeshViewer` тянет three.js (~471 KB gzip 117 KB). Раньше он попадал в
 * главный чанк, потому что импортировался статически четырьмя компонентами, —
 * пользователь оплачивал загрузку рендерера, даже если ни разу не открывал
 * 3D-режим.
 *
 * Здесь модуль подгружается по требованию; на время загрузки показывается
 * честное состояние, а не пустой прямоугольник.
 */
const MeshViewer = lazy(() => import("./MeshViewer"));

type Props = ComponentProps<typeof MeshViewerType>;

export default function LazyMeshViewer(props: Props) {
  return (
    <Suspense
      fallback={
        <div className="w-full h-full flex items-center justify-center font-mono text-[10px] text-text-muted">
          {t.meshLoading}
        </div>
      }>
      <MeshViewer {...props} />
    </Suspense>
  );
}
