import React from "react";

export type RenderMode = "3d-wireframe" | "3d-solid" | "uv-texture" | "heatmap";

/**
 * The current Stage 2 API does not expose a mesh artifact. Keep this component
 * as an honest boundary instead of drawing a synthetic face that looks like a
 * measurement.
 */
export const FaceMesh3D: React.FC<{ mode: RenderMode; className?: string }> = ({ mode, className = "" }) => (
  <div className={`relative flex h-full min-h-48 items-center justify-center rounded-lg border border-amber-500 bg-surface-base p-6 text-center ${className}`}>
    <div className="max-w-md space-y-2">
      <div className="font-mono text-xs text-amber-300">3D / {mode}</div>
      <p className="text-sm text-ink-secondary">Mesh-артефакт не входит в текущий ответ Stage 2 API.</p>
      <p className="text-xs text-ink-muted">Здесь намеренно нет сгенерированной модели: она была бы демонстрационной, а не результатом измерения.</p>
    </div>
  </div>
);
