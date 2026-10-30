import { memo, useEffect, useMemo, useRef, useState } from "react";
import { useReactFlow, type NodeProps } from "@xyflow/react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import {
  ScatterChart,
  Settings2,
  Maximize2,
  LoaderCircle,
  Grid2X2,
  ChevronDown,
} from "lucide-react";
import { useStore, type WorkNode, poseLabels } from "../store";
import { post } from "../api";
import type { Projection, Photo } from "../types";
import { NodeHead, Port, Slider, Empty, JobProgress } from "./ui";
import { dateLabel } from "./Timeline";
import { supportsWebGL } from "../graphics";
const colors = [
  "#59d7b8",
  "#b49ced",
  "#edb86e",
  "#74bae8",
  "#eb91b3",
  "#9bce83",
  "#de977e",
  "#94c3d8",
];
type Point = Projection["points"][number];
function colorFor(
  point: Point,
  projection: Projection,
  colorBy: string,
  photos: Photo[],
) {
  if (colorBy === "group")
    return colors[projection.groups.indexOf(point.group) % colors.length];
  if (colorBy === "pose") {
    const poses = Object.keys(poseLabels);
    return colors[
      poses.indexOf(photos.find((p) => p.id === point.id)?.pose || "frontal") %
        colors.length
    ];
  }
  if (colorBy === "norm") {
    const values = projection.points.map((p) => p.norm),
      t =
        (point.norm - Math.min(...values)) /
        (Math.max(...values) - Math.min(...values) || 1);
    return `hsl(${170 - t * 130},65%,${55 + t * 10}%)`;
  }
  return colors[point.cluster % colors.length];
}
function Scatter3D({
  projection,
  photos,
  colorBy,
  onSelect,
  route,
}: {
  projection: Projection;
  photos: Photo[];
  colorBy: string;
  onSelect: (p: Point, multi: boolean) => void;
  route: string[];
}) {
  const [hover, setHover] = useState<Point | null>(null);
  const max = Math.max(
    ...projection.points.flatMap((p) => p.coords.map(Math.abs)),
    1,
  );
  return (
    <Canvas camera={{ position: [0, 0, 7], fov: 42 }} dpr={[1, 1.4]}>
      <ambientLight intensity={2} />
      <gridHelper
        args={[5, 10, "#304454", "#253644"]}
        rotation={[Math.PI / 2, 0, 0]}
      />
      {projection.points.map((p) => (
        <mesh
          key={p.id}
          position={
            [
              (p.coords[0] / max) * 2,
              (p.coords[1] / max) * 2,
              ((p.coords[2] || 0) / max) * 2,
            ] as [number, number, number]
          }
          onClick={(e) => {
            e.stopPropagation();
            onSelect(p, e.ctrlKey || e.metaKey);
          }}
          onPointerOver={() => setHover(p)}
          onPointerOut={() => setHover(null)}
        >
          <sphereGeometry
            args={[route.includes(p.id) ? 0.09 : 0.065, 16, 12]}
          />
          <meshBasicMaterial
            color={
              route.includes(p.id)
                ? "#ffffff"
                : colorFor(p, projection, colorBy, photos)
            }
          />
        </mesh>
      ))}
      {hover && (
        <Html
          position={
            [
              (hover.coords[0] / max) * 2,
              (hover.coords[1] / max) * 2,
              ((hover.coords[2] || 0) / max) * 2,
            ] as [number, number, number]
          }
        >
          <div className="cluster-tooltip">
            <img src={photos.find((p) => p.id === hover.id)?.thumbnail} />
            <span>
              {dateLabel(photos.find((p) => p.id === hover.id)?.date || null)}
              <small>α_id · ‖α‖ {hover.norm.toFixed(2)}</small>
            </span>
          </div>
        </Html>
      )}
      <OrbitControls enablePan={false} />
    </Canvas>
  );
}
// Порог похожести: косинусное расстояние α_id на реальных корпусах лежит в
// ~0…0.3, евклидово по 80D — в ~2…6. Один ползунок на обе шкалы был бы
// подделкой, поэтому у каждой метрики свой диапазон и свой по умолчанию.
const THRESHOLD: Record<string, { min: number; max: number; step: number; def: number }> = {
  cosine: { min: 0, max: 0.5, step: 0.005, def: 0.1 },
  euclidean: { min: 0, max: 10, step: 0.1, def: 3 },
};
export const ClusterNode = memo(function ClusterNode({
  id,
  data,
}: NodeProps<WorkNode>) {
  const photos = useStore((s) => s.photos),
    jobs = useStore((s) => s.jobs),
    route = useStore((s) => s.route),
    edges = useStore((s) => s.edges),
    notify = useStore((s) => s.notify),
    patch = useStore((s) => s.patchNode);
  const rf = useReactFlow();
  const [params, setParams] = useState({
    focus: "compare",
    threshold: 0.1,
    method: "pca",
    dimensions: 2,
    distance: "cosine",
    n_neighbors: 15,
    min_dist: 0.1,
    perplexity: 15,
    seed: 42,
    clusters: 3,
    ...data.settings,
  });
  const [projection, setProjection] = useState<Projection | null>(null);
  const [jobId, setJobId] = useState("");
  const [settings, setSettings] = useState(false);
  const [colorBy, setColorBy] = useState("cluster");
  const [hover, setHover] = useState<Point | null>(null);
  const [matrix, setMatrix] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);
  const [manual, setManual] = useState(0);
  const connected = edges.some(
    (e) => e.target === id && e.targetHandle === "embedding",
  );
  const ids = photos.filter((p) => p.status === "ready").map((p) => p.id);
  // Режим ноды и порог — только отображение матрицы; пересчитывать из-за них
  // проекцию (и слать новый job на каждое движение слайдера) нельзя.
  const key = JSON.stringify({
    method: params.method,
    dimensions: params.dimensions,
    distance: params.distance,
    n_neighbors: params.n_neighbors,
    min_dist: params.min_dist,
    perplexity: params.perplexity,
    seed: params.seed,
    clusters: params.clusters,
    photo_ids: ids,
  });
  useEffect(() => {
    if (!connected || ids.length < 2) return;
    const n = ++request.current;
    const timer = setTimeout(() => {
      setError("");
      post("/projection", JSON.parse(key))
        .then((j) => {
          if (request.current === n) setJobId(j.id);
        })
        .catch((e) => {
          if (request.current === n) setError(String(e));
        });
    }, 500);
    return () => clearTimeout(timer);
  }, [key, connected, manual]);
  const job = jobs.find((j) => j.id === jobId);
  useEffect(() => {
    if (job?.status === "completed") {
      setProjection(job.result);
      setError("");
    }
    if (job?.status === "failed") setError(job.message);
  }, [job?.status, job?.id]);
  const change = (p: Record<string, any>) => {
    const next = { ...params, ...p };
    setParams(next);
    patch(id, { settings: next });
  };
  const select = (p: Point, multi: boolean) => {
    const s = useStore.getState();
    if (p.group !== s.group && s.group !== "__all") s.setGroup(p.group);
    s.selectPhoto(p.id, multi);
  };
  const expanded = !data.compact;
  // Режим ноды: «Сравнение» оставляет единственный вопрос «похожи ли» —
  // матрицу и порог; «Облако» — прежняя настройка проекции со всеми ручками.
  const compare = params.focus === "compare";
  const thr = THRESHOLD[params.distance] || THRESHOLD.cosine;
  const similar = (() => {
    const m = projection?.matrix || [];
    let count = 0,
      best: { i: number; j: number; d: number } | null = null;
    for (let i = 0; i < m.length; i++)
      for (let j = i + 1; j < m[i].length; j++) {
        const d = m[i][j];
        if (d <= params.threshold) count++;
        if (!best || d < best.d) best = { i, j, d };
      }
    return { count, best };
  })();
  const frameLabel = (i: number) => {
    const p = projection?.points[i];
    const photo = p ? photos.find((q) => q.id === p.id) : null;
    return photo ? dateLabel(photo.date || null) : "—";
  };
  // Косинусные расстояния α_id мелкие (0.02…0.16), евклидовы — единицы.
  const distLabel = (d: number) =>
    params.distance === "euclidean" ? d.toFixed(1) : d.toFixed(3);
  const chartW = expanded ? 530 : 260,
    chartH = expanded ? 320 : 178;
  const matrixMax = projection
    ? Math.max(
        0.001,
        ...projection.matrix.slice(0, 40).flatMap((row) => row.slice(0, 40)),
      )
    : 1;
  const coords = projection?.points.map((p) => p.coords) || [[0, 0]];
  const xx = coords.map((p) => p[0]),
    yy = coords.map((p) => p[1]);
  const xmin = Math.min(...xx),
    xmax = Math.max(...xx),
    ymin = Math.min(...yy),
    ymax = Math.max(...yy);
  const px = (v: number) =>
      25 + ((v - xmin) / (xmax - xmin || 1)) * (chartW - 50),
    py = (v: number) =>
      chartH - 22 - ((v - ymin) / (ymax - ymin || 1)) * (chartH - 44);
  const expand = () => {
    useStore.setState((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id
          ? {
              ...n,
              style: { ...n.style, width: expanded ? 290 : 570 },
              data: { ...n.data, compact: expanded },
            }
          : n,
      ),
      workspaceVersion: s.workspaceVersion + 1,
    }));
    setTimeout(
      () => rf.fitView({ nodes: [{ id }], padding: 0.15, duration: 400 }),
      40,
    );
  };
  return (
    <div className="node-card cluster-node">
      <NodeHead
        id={id}
        title="Облако α_id"
        subtitle={data.collapsed ? "3DDFA_V3 · кластеризация" : undefined}
        icon={<ScatterChart size={16} />}
        collapsed={data.collapsed}
        onExpand={expand}
      />
      {!data.collapsed && (
        <div className="node-content nodrag nowheel">
          <div className="cluster-toolbar">
            <div className="segmented small" role="group" aria-label="Режим ноды">
              <button
                className={compare ? "active" : ""}
                title="Только матрица расстояний и порог похожести"
                onClick={() => change({ focus: "compare" })}
              >
                Сравнение
              </button>
              <button
                className={compare ? "" : "active"}
                title="Проекция α_id: метод, размерность, кластеры"
                onClick={() => change({ focus: "cloud" })}
              >
                Облако
              </button>
            </div>
            {!compare && (
              <>
                <select
                  aria-label="Метод проекции"
                  value={params.method}
                  onChange={(e) => change({ method: e.target.value })}
                >
                  <option value="pca">PCA</option>
                  <option value="umap">UMAP</option>
                  <option value="tsne">t-SNE</option>
                </select>
                <div className="segmented small">
                  {[2, 3].map((n) => (
                    <button
                      key={n}
                      className={params.dimensions === n ? "active" : ""}
                      onClick={() => change({ dimensions: n })}
                    >
                      {n}D
                    </button>
                  ))}
                </div>
                <button
                  className={"icon-btn " + (settings ? "accent" : "")}
                  title="Параметры кластеризации"
                  onClick={() => setSettings(!settings)}
                >
                  <Settings2 size={14} />
                </button>
              </>
            )}
          </div>
          {settings && !compare && (
            <div className="projection-settings">
              <label className="field-label">
                Расстояние
                <select
                  value={params.distance}
                  onChange={(e) => change({ distance: e.target.value })}
                >
                  <option value="cosine">Косинусное</option>
                  <option value="euclidean">Евклидово</option>
                </select>
              </label>
              <Slider
                label="Кластеров K-means"
                value={params.clusters}
                min={1}
                max={Math.max(2, Math.min(15, ids.length))}
                step={1}
                onChange={(clusters) => change({ clusters })}
              />
              {params.method === "umap" && (
                <>
                  <Slider
                    label="n_neighbors"
                    value={params.n_neighbors}
                    min={2}
                    max={50}
                    step={1}
                    onChange={(n_neighbors) => change({ n_neighbors })}
                  />
                  <Slider
                    label="min_dist"
                    value={params.min_dist}
                    min={0}
                    max={1}
                    onChange={(min_dist) => change({ min_dist })}
                  />
                </>
              )}
              {params.method === "tsne" && (
                <Slider
                  label="perplexity"
                  value={params.perplexity}
                  min={1}
                  max={50}
                  step={1}
                  onChange={(perplexity) => change({ perplexity })}
                />
              )}
              <Slider
                label="Seed"
                value={params.seed}
                min={0}
                max={1000}
                step={1}
                onChange={(seed) => change({ seed })}
              />
              <label className="field-label">
                Цвет точек
                <select
                  value={colorBy}
                  onChange={(e) => setColorBy(e.target.value)}
                >
                  <option value="cluster">Кластеры K-means</option>
                  <option value="group">Группа</option>
                  <option value="pose">Ракурс</option>
                  <option value="norm">Норма α_id</option>
                </select>
              </label>
            </div>
          )}
          {!connected ? (
            <Empty
              title="Подключите α_id"
              detail="Вход embedding принимает параметры идентичности 3DDFA_V3."
            />
          ) : error ? (
            <div className="inline-warning">
              {error}
              <button
                className="text-button"
                onClick={() => setManual(manual + 1)}
              >
                Повторить
              </button>
            </div>
          ) : !projection ? (
            <div className="cluster-loading">
              <LoaderCircle className="spin" size={19} />
              <span>
                {ids.length < 2
                  ? "Нужны два обработанных фото"
                  : "Считаем проекцию…"}
              </span>
            </div>
          ) : (
            <>
              {compare && (
                <div className="compare-panel">
                  <div className="compare-controls">
                    <label className="field-label">
                      Расстояние
                      <select
                        value={params.distance}
                        onChange={(e) =>
                          change({
                            distance: e.target.value,
                            // Шкалы несопоставимы: при смене метрики порог
                            // возвращаем на её разумное значение.
                            threshold:
                              (THRESHOLD[e.target.value] || THRESHOLD.cosine)
                                .def,
                          })
                        }
                      >
                        <option value="cosine">Косинусное</option>
                        <option value="euclidean">Евклидово</option>
                      </select>
                    </label>
                    <Slider
                      label="Порог похожести"
                      value={params.threshold}
                      min={thr.min}
                      max={thr.max}
                      step={thr.step}
                      onChange={(threshold) => change({ threshold })}
                    />
                  </div>
                  <div className="compare-summary">
                    <span>
                      Пар ниже порога{" "}
                      <b>
                        {similar.count} /{" "}
                        {Math.max(
                          0,
                          (projection.points.length *
                            (projection.points.length - 1)) /
                            2,
                        )}
                      </b>
                    </span>
                    {similar.best && (
                      <span>
                        Ближе всех{" "}
                        <b>
                          {frameLabel(similar.best.i)} ↔{" "}
                          {frameLabel(similar.best.j)}
                        </b>{" "}
                        · {similar.best.d.toFixed(4)}
                      </span>
                    )}
                  </div>
                  <p className="micro muted">
                    Порог не откалиброван: α_id описывает форму лица, а не
                    идентичность. Числа ниже порога подсвечены — это подсказка,
                    а не вывод о том, что человек тот же.
                  </p>
                </div>
              )}
              {!compare && (
                <>
              <div className="scatter-container" style={{ height: chartH }}>
                {params.dimensions === 3 && supportsWebGL() ? (
                  <Scatter3D
                    projection={projection}
                    photos={photos}
                    colorBy={colorBy}
                    onSelect={select}
                    route={route}
                  />
                ) : (
                  <svg
                    viewBox={`0 0 ${chartW} ${chartH}`}
                    width="100%"
                    height="100%"
                  >
                    {[0.25, 0.5, 0.75].map((v) => (
                      <g key={v}>
                        <line
                          x1={25}
                          x2={chartW - 25}
                          y1={chartH * v}
                          y2={chartH * v}
                          stroke="#273642"
                          strokeDasharray="2 5"
                        />
                        <line
                          x1={chartW * v}
                          x2={chartW * v}
                          y1={20}
                          y2={chartH - 20}
                          stroke="#273642"
                          strokeDasharray="2 5"
                        />
                      </g>
                    ))}
                    <text
                      x={chartW - 25}
                      y={chartH - 5}
                      fill="#526b7e"
                      fontSize={9}
                    >
                      {projection.method === "pca" ? "PC1" : "X"}
                    </text>
                    <text x={4} y={15} fill="#526b7e" fontSize={9}>
                      {projection.method === "pca" ? "PC2" : "Y"}
                    </text>
                    {projection.points.map((p) => (
                      <g
                        key={p.id}
                        className="clickable"
                        onClick={(e) => select(p, e.ctrlKey || e.metaKey)}
                        onMouseEnter={() => setHover(p)}
                        onMouseLeave={() => setHover(null)}
                      >
                        <circle
                          cx={px(p.coords[0])}
                          cy={py(p.coords[1])}
                          r={12}
                          fill="transparent"
                        />
                        {route.includes(p.id) && (
                          <circle
                            cx={px(p.coords[0])}
                            cy={py(p.coords[1])}
                            r={7.5}
                            fill="none"
                            stroke="#d5ebe5"
                            strokeWidth={1.1}
                          />
                        )}
                        <circle
                          cx={px(p.coords[0])}
                          cy={py(p.coords[1])}
                          r={4.1}
                          fill={colorFor(p, projection, colorBy, photos)}
                        />
                      </g>
                    ))}
                  </svg>
                )}
                {hover && params.dimensions === 2 && (
                  <div className="cluster-tooltip floating">
                    <img
                      src={photos.find((p) => p.id === hover.id)?.thumbnail}
                    />
                    <span>
                      {dateLabel(
                        photos.find((p) => p.id === hover.id)?.date || null,
                      )}
                      <small>
                        {
                          poseLabels[
                            photos.find((p) => p.id === hover.id)?.pose ||
                              "unclassified"
                          ]
                        }{" "}
                        · ‖α‖ {hover.norm.toFixed(2)}
                      </small>
                    </span>
                  </div>
                )}
              </div>
              <div className="cluster-legend">
                {Array.from(
                  new Set(projection.points.map((p) => p.cluster)),
                ).map((k) => (
                  <span key={k}>
                    <i style={{ background: colors[k % colors.length] }} />K
                    {k + 1}
                  </span>
                ))}
                <span className="muted">{projection.points.length} фото</span>
              </div>
              <div className="cluster-summary">
                <span>
                  Силуэт <b>{projection.silhouette?.toFixed(2) || "—"}</b>
                </span>
                <span>
                  {projection.explained_variance !== null
                    ? "PCA " +
                      Math.round(projection.explained_variance * 100) +
                      "%"
                    : "seed " + projection.seed}
                </span>
              </div>
              {projection.silhouette === null && expanded && (
                <p className="micro muted">
                  Силуэт групп требует ≥2 групп. Цвета K-means не являются
                  идентификацией людей.
                </p>
              )}
                </>
              )}
              {projection.note && (
                <p className="micro muted">{projection.note}</p>
              )}
              {!compare && (
                <button
                  className="disclosure"
                  onClick={() => setMatrix(!matrix)}
                >
                  <Grid2X2 size={12} /> Матрица расстояний{" "}
                  <ChevronDown size={12} />
                </button>
              )}
              {(compare || matrix) && (
                <div className={"distance-matrix" + (compare ? " wide" : "")}>
                  <div
                    className="matrix-grid"
                    style={{
                      gridTemplateColumns: `repeat(${Math.min(40, projection.points.length)},22px)`,
                    }}
                  >
                    {projection.matrix.slice(0, 40).flatMap((row, i) =>
                      row.slice(0, 40).map((d, j) => (
                        <button
                          key={i + "-" + j}
                          className={
                            i !== j && d <= params.threshold ? "similar" : ""
                          }
                          title={`${i + 1} ↔ ${j + 1} · ${frameLabel(i)} ↔ ${frameLabel(j)}: ${d.toFixed(4)}${
                            i !== j && d <= params.threshold
                              ? " · ниже порога"
                              : ""
                          }`}
                          style={{
                            background: `rgba(85,213,184,${Math.min(0.9, (d / matrixMax) * 0.85) + 0.07})`,
                          }}
                          onClick={() => {
                            const a = projection.points[i],
                              b = projection.points[j];
                            if (i === j) {
                              select(a, false);
                              return;
                            }
                            const s = useStore.getState();
                            s.setGroup(a.group === b.group ? a.group : "__all");
                            s.setRoute([a.id, b.id]);
                            s.set({ playhead: 0.5, mode: "morph" });
                          }}
                        >
                          {expanded || compare ? distLabel(d) : ""}
                        </button>
                      )),
                    )}
                  </div>
                  {compare && (
                    <ul className="matrix-axis">
                      {projection.points.map((p, i) => (
                        <li key={p.id}>
                          {i + 1} · {frameLabel(i)}
                        </li>
                      ))}
                    </ul>
                  )}
                  {expanded && !compare && (
                    <div className="centroid-stats">
                      {projection.groups.map((g) => (
                        <div key={g}>
                          {g} · дисперсия {projection.dispersion[g].toFixed(4)}
                        </div>
                      ))}
                      <div className="micro muted">
                        Между центроидами:{" "}
                        {projection.centroid_distances
                          .map((row) =>
                            row.map((x) => x.toFixed(3)).join(" / "),
                          )
                          .join(" · ")}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
          {job && ["queued", "running"].includes(job.status) && (
            <JobProgress job={job} />
          )}
          <div className="cluster-footer">
            {params.dimensions === 3 && !supportsWebGL()
              ? "3D → XY · нет WebGL · "
              : ""}
            3DDFA_V3 · α_id{" "}
            <span>
              {compare
                ? params.distance === "euclidean"
                  ? "евклидово расстояние"
                  : "косинусное расстояние"
                : projection?.cache_hit
                  ? "из кэша"
                  : "80D → " + params.dimensions + "D"}
            </span>
          </div>
        </div>
      )}
      <Port
        id="embedding"
        type="target"
        color="#ac99eb"
        top={data.collapsed ? "50%" : 36}
      />
    </div>
  );
});
