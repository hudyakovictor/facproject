import { useEffect, useRef, useState, useCallback } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  MiniMap,
  Controls,
  useReactFlow,
  type Connection,
  type Edge,
  Panel,
} from "@xyflow/react";
import {
  Plus,
  ChevronDown,
  Check,
  Cpu,
  Compass,
  Activity,
  Shapes,
  Maximize,
  MousePointer2,
  HelpCircle,
  Undo2,
  Focus,
  ScatterChart,
  Box,
  Images,
  X,
  LoaderCircle,
  AlertCircle,
  Lock,
  Hand,
  Eye,
  Map,
} from "lucide-react";
import { useStore, initialNodes, initialEdges, type WorkNode } from "./store";
import { api, post } from "./api";
import {
  SourceNode,
  ProcessorNode,
  MetricProcessorNode,
  PendingNode,
} from "./components/DataNodes";
import { SceneNode, MetricsTimelineNode } from "./components/SceneNode";
import { EyesNode } from "./components/EyesNode";
import { ClusterNode } from "./components/ClusterNode";
import { PoseNode, RegistryNode } from "./components/ConfigNodes";
import { PhotoEditor } from "./components/PhotoEditor";
import { usePlayback } from "./components/Timeline";
import "@xyflow/react/dist/style.css";
import "./styles.css";
const nodeTypes = {
  source: SourceNode,
  processor: ProcessorNode,
  metricProcessor: MetricProcessorNode,
  scene: SceneNode,
  timeline: MetricsTimelineNode,
  eyes: EyesNode,
  cluster: ClusterNode,
  poses: PoseNode,
  registry: RegistryNode,
  pending: PendingNode,
};
function Workbench() {
  const nodes = useStore((s) => s.nodes),
    edges = useStore((s) => s.edges),
    onNodesChange = useStore((s) => s.onNodesChange),
    onEdgesChange = useStore((s) => s.onEdgesChange),
    onConnect = useStore((s) => s.onConnect),
    loaded = useStore((s) => s.loaded),
    photos = useStore((s) => s.photos),
    models = useStore((s) => s.models),
    jobs = useStore((s) => s.jobs),
    error = useStore((s) => s.error),
    toast = useStore((s) => s.toast),
    group = useStore((s) => s.group),
    activeId = useStore((s) => s.activeId),
    route = useStore((s) => s.route),
    heat = useStore((s) => s.heat),
    visibleMetrics = useStore((s) => s.visibleMetrics),
    notify = useStore((s) => s.notify);
  const flow = useReactFlow();
  const [addOpen, setAddOpen] = useState(false),
    [help, setHelp] = useState(false),
    [saved, setSaved] = useState(true),
    [move, setMove] = useState(0);
  const [grab, setGrab] = useState(false),
    [showMap, setShowMap] = useState(false),
    [spaceDown, setSpaceDown] = useState(false),
    [guideOpen, setGuideOpen] = useState(() => localStorage.getItem("atlas-guide-dismissed") !== "1"),
    [dismissedJob, setDismissedJob] = useState<string | null>(null);
  const spaceRef = useRef(false),
    panGesture = useRef<any>(null);
  const initialized = useRef(false);
  const oldJobs = useRef(new Set<string>());
  usePlayback();
  useEffect(() => {
    useStore.getState().init();
  }, []);
  useEffect(() => {
    if (!loaded || error) return;
    const source = new EventSource("/api/events");
    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        useStore.setState({ jobs: data.jobs });
        for (const j of data.jobs) {
          if (j.status === "completed" && !oldJobs.current.has(j.id)) {
            oldJobs.current.add(j.id);
            if (j.kind === "process") {
              useStore.getState().refresh();
              if (j.result?.errors?.length)
                notify(
                  j.result.errors.length +
                    " фото не обработано: " +
                    j.result.errors[0].error,
                );
            }
          }
          if (j.status === "failed" && !oldJobs.current.has(j.id)) {
            oldJobs.current.add(j.id);
            notify(j.message);
          }
        }
      } catch {}
    };
    return () => source.close();
  }, [loaded, error]);
  useEffect(() => {
    if (!loaded || error) return;
    setSaved(false);
    const timeout = setTimeout(() => {
      const s = useStore.getState();
      const ws = {
        version: 3,
        nodes: s.nodes.map(
          ({ id, type, position, style, data, hidden, width, height }) => ({
            id,
            type,
            position,
            style,
            data,
            hidden,
            width,
            height,
          }),
        ),
        edges: s.edges,
        viewport: flow.getViewport(),
        preferences: {
          group: s.group,
          activeId: s.activeId,
          route: s.route,
          heat: s.heat,
          visibleMetrics: s.visibleMetrics,
        },
        saved_at: new Date().toISOString(),
      };
      api("/workspace", { method: "PUT", body: JSON.stringify(ws) })
        .then(() => setSaved(true))
        .catch(() => setSaved(false));
    }, 900);
    return () => clearTimeout(timeout);
  }, [
    nodes,
    edges,
    loaded,
    group,
    activeId,
    route,
    heat,
    visibleMetrics,
    move,
    error,
  ]);
  const init = useCallback(() => {
    if (initialized.current) return;
    initialized.current = true;
    api("/workspace").then((ws) => {
      if (ws?.version >= 3 && ws?.viewport) flow.setViewport(ws.viewport);
      else
        setTimeout(
          () =>
            flow.fitView({
              nodes: [{ id: "scene" }, { id: "timeline" }],
              padding: 0.07,
              maxZoom: 1.2,
              minZoom: 0.45,
            }),
          100,
        );
    });
  }, [flow]);
  const valid = (c: Edge | Connection) => {
    const output: Record<string, string> = {
      photos: "photos",
      mesh: "mesh",
      landmarks: "landmarks",
      alpha_id: "embedding",
      series: "series",
    };
    if (
      !c.source ||
      !c.target ||
      c.source === c.target ||
      output[c.sourceHandle || ""] !== c.targetHandle
    )
      return false;
    const visited = new Set<string>();
    const reaches = (n: string): boolean => {
      if (n === c.source) return true;
      if (visited.has(n)) return false;
      visited.add(n);
      return edges.filter((e) => e.source === n).some((e) => reaches(e.target));
    };
    return !reaches(c.target);
  };
  const reveal = (id: string) => {
    setAddOpen(false);
    const n = useStore.getState().nodes.find((n) => n.id === id);
    if (n) {
      useStore.setState((s) => ({
        nodes: s.nodes.map((x) => (x.id === id ? { ...x, hidden: false } : x)),
      }));
      setTimeout(
        () => flow.fitView({ nodes: [{ id }], padding: 0.12, duration: 450 }),
        40,
      );
    } else {
      const n = initialNodes.find((n) => n.id === id)!;
      useStore.setState((s) => ({
        nodes: [...s.nodes, { ...n, hidden: false }],
        edges: [
          ...s.edges,
          ...initialEdges.filter(
            (e) =>
              (e.source === id || e.target === id) &&
              !s.edges.some((x) => x.id === e.id) &&
              [...s.nodes.map((n) => n.id), id].includes(e.source) &&
              [...s.nodes.map((n) => n.id), id].includes(e.target),
          ),
        ],
      }));
      setTimeout(
        () => flow.fitView({ nodes: [{ id }], padding: 0.12, duration: 450 }),
        40,
      );
    }
  };
  const add = (type: string, title: string) => {
    setAddOpen(false);
    const id = type + "-" + Date.now(),
      center = flow.screenToFlowPosition({
        x: window.innerWidth * 0.45,
        y: window.innerHeight * 0.28,
      });
    const n: WorkNode = {
      id,
      type,
      position: center,
      style: {
        width: ["scene", "timeline"].includes(type)
          ? 950
          : type === "eyes"
            ? 500
            : type === "cluster"
              ? 420
              : 260,
        ...(type === "scene"
          ? { height: 760 }
          : type === "timeline"
            ? { height: 390 }
            : {}),
      },
      data: { title, compact: false },
      dragHandle: ".node-head",
    };
    const links =
      type === "scene"
        ? [
            {
              id: "edge-" + id,
              source: "recon",
              sourceHandle: "mesh",
              target: id,
              targetHandle: "mesh",
            },
            {
              id: "series-" + id,
              source: "metrics",
              sourceHandle: "series",
              target: "timeline",
              targetHandle: "series",
            },
          ]
        : type === "timeline"
          ? [
              {
                id: "series-" + id,
                source: "metrics",
                sourceHandle: "series",
                target: id,
                targetHandle: "series",
              },
            ]
          : type === "cluster"
            ? [
                {
                  id: "edge-" + id,
                  source: "recon",
                  sourceHandle: "alpha_id",
                  target: id,
                  targetHandle: "embedding",
                },
              ]
            : [];
    useStore.setState((s) => ({
      nodes: [...s.nodes, n],
      edges: [
        ...s.edges,
        ...links.map((e) => ({
          ...e,
          style: { stroke: "#a897de", strokeWidth: 1.5 },
        })),
      ],
    }));
  };
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest("input,textarea,select,[contenteditable=true]"))
        return;
      if (e.code === "Space") {
        e.preventDefault();
        spaceRef.current = true;
        setSpaceDown(true);
      } else if (!e.ctrlKey && !e.metaKey) {
        const id = (
          {
            "1": "scene",
            "2": "timeline",
            "3": "eyes",
            "4": "cluster",
          } as Record<string, string>
        )[e.key];
        if (id) {
          e.preventDefault();
          reveal(id);
        }
        if (e.key.toLowerCase() === "f" || e.key === "Home") {
          e.preventDefault();
          flow.fitView({ padding: 0.06, duration: 250 });
        }
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        spaceRef.current = false;
        setSpaceDown(false);
      }
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [flow]);
  const activeJobs = jobs.filter((j) =>
      ["running", "queued"].includes(j.status),
    ),
    latestProcess = jobs.find((j) => j.kind === "process"),
    ready = photos.filter((p) => p.status === "ready").length,
    hasDemo = photos
      .filter((p) => group === "__all" || p.group === group)
      .some((p) => p.demo);
  if (!loaded)
    return (
      <div className="startup">
        <div className="brand">
          ATLAS<span>FACE WORKBENCH</span>
        </div>
        <LoaderCircle className="spin" size={22} />
        <p>Загружаем рабочее поле и кэш геометрии…</p>
      </div>
    );
  if (error)
    return (
      <div className="startup">
        <AlertCircle size={28} />
        <h2>Бэкенд недоступен</h2>
        <p>{error}</p>
        <code>python -m uvicorn server.app:app --host 0.0.0.0 --port 8000</code>
        <button className="primary" onClick={() => location.reload()}>
          Повторить
        </button>
      </div>
    );
  return (
    <main className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          ATLAS<span className="brand-caption">FACE WORKBENCH</span>
        </div>
        <div className="header-divider" />
        <div className="project-name">
          <Shapes size={15} />
          <span>Лаборатория изменений</span>
          <ChevronDown size={12} />
        </div>
        <span className="project-tag">WORKSPACE 01</span>
        <div className="header-tools">
          <div className="relative">
            <button
              className={"secondary add-node " + (addOpen ? "active" : "")}
              onClick={() => setAddOpen(!addOpen)}
            >
              <Plus size={14} /> Нода <ChevronDown size={12} />
            </button>
            {addOpen && (
              <div className="add-menu">
                <div className="eyebrow">ДОБАВИТЬ НА КАНВАС</div>
                <button onClick={() => reveal("source")}>
                  <Images size={16} />
                  <span>
                    Фото и серии<small>Источник данных</small>
                  </span>
                </button>
                <button onClick={() => add("scene", "3D-сцена")}>
                  <Focus size={16} />
                  <span>
                    3D · морфинг · миниатюры<small>Независимая сцена</small>
                  </span>
                </button>
                <button onClick={() => add("timeline", "Таймлайн измерений")}>
                  <Activity size={16} />
                  <span>
                    Таймлайн измерений<small>Отдельная панель метрик</small>
                  </span>
                </button>
                <button onClick={() => reveal("eyes")}>
                  <Eye size={16} />
                  <span>
                    Глаза · исходные пиксели
                    <small>Радужка, щель, контроль качества</small>
                  </span>
                </button>
                <button onClick={() => add("cluster", "Облако α_id")}>
                  <ScatterChart size={16} />
                  <span>
                    Облако эмбеддингов<small>PCA, UMAP, t-SNE</small>
                  </span>
                </button>
                <button onClick={() => reveal("poses")}>
                  <Compass size={16} />
                  <span>
                    Пять ракурсов<small>Углы и профили</small>
                  </span>
                </button>
                <button onClick={() => reveal("registry")}>
                  <Activity size={16} />
                  <span>
                    Метрики и пороги<small>Python + YAML</small>
                  </span>
                </button>
                <div className="menu-divider" />
                {["MediaPipe", "FAN", "AdaFace"].map((t) => (
                  <button key={t} onClick={() => add("pending", t)}>
                    <Lock size={14} />
                    <span>
                      {t}
                      <small>Следующий этап · не установлена</small>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            className="header-text-button"
            onClick={() => reveal("poses")}
          >
            <Compass size={14} /> Ракурсы
          </button>
          <button
            className="header-text-button"
            onClick={() => reveal("registry")}
          >
            <Activity size={14} /> Реестр
          </button>
          <div className="header-divider" />
          <span className="cpu-chip">
            <span className="status-dot" />
            <Cpu size={12} /> CPU · 2
          </span>
          <span className="save-indicator">
            <Check size={13} />
            {saved ? "Сохранено" : "Сохраняется…"}
          </span>
          <button
            className="icon-btn"
            title="Управление"
            onClick={() => setHelp(!help)}
          >
            <HelpCircle size={17} />
          </button>
        </div>
      </header>
      <div
        className={"canvas-wrap " + (grab || spaceDown ? "grab-mode" : "")}
        onPointerDownCapture={(e) => {
          if ((grab || spaceRef.current) && e.button === 0) {
            panGesture.current = {
              x: e.clientX,
              y: e.clientY,
              view: flow.getViewport(),
            };
            e.currentTarget.setPointerCapture(e.pointerId);
            e.stopPropagation();
            e.preventDefault();
          }
        }}
        onPointerMoveCapture={(e) => {
          const p = panGesture.current;
          if (p) {
            flow.setViewport({
              ...p.view,
              x: p.view.x + e.clientX - p.x,
              y: p.view.y + e.clientY - p.y,
            });
            e.stopPropagation();
          }
        }}
        onPointerUpCapture={(e) => {
          if (panGesture.current) {
            panGesture.current = null;
            setMove((x) => x + 1);
            e.stopPropagation();
          }
        }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          isValidConnection={valid}
          onInit={init}
          onMoveEnd={() => setMove((x) => x + 1)}
          minZoom={0.18}
          maxZoom={2}
          onlyRenderVisibleElements
          deleteKeyCode={["Backspace", "Delete"]}
          selectionOnDrag={false}
          panOnDrag={[0, 1, 2]}
          panOnScroll
          zoomOnScroll={false}
          zoomActivationKeyCode={["Control", "Meta"]}
          panActivationKeyCode="Space"
          selectionKeyCode="Shift"
          multiSelectionKeyCode={["Meta", "Control"]}
          attributionPosition="top-right"
          defaultEdgeOptions={{ type: "default" }}
          fitViewOptions={{ padding: 0.03 }}
          colorMode="dark"
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={22}
            size={1}
            color="#2c3a47"
            bgColor="#10161e"
          />
          <Controls showInteractive={false} />
          {showMap && (
            <MiniMap
              pannable
              zoomable
              bgColor="#101820"
              nodeColor={(n) =>
                n.type === "scene"
                  ? "#4c887e"
                  : n.type === "cluster"
                    ? "#79699a"
                    : "#354b5b"
              }
              maskColor="rgba(7,12,17,.7)"
            />
          )}
          <Panel position="top-right">
            {guideOpen && <section className="workflow-guide" aria-label="Быстрый старт">
              <div className="guide-head"><div><span className="eyebrow">БЫСТРЫЙ СТАРТ</span><strong>Порядок работы</strong></div>
                <button className="icon-btn" aria-label="Скрыть подсказку" onClick={() => { setGuideOpen(false); localStorage.setItem("atlas-guide-dismissed", "1"); }}><X size={13}/></button></div>
              <div className="guide-progress"><i style={{ width: `${Math.round((Number(photos.length > 0) + Number(ready > 0) + Number(Boolean(activeId))) / 3 * 100)}%` }}/></div>
              <button className="guide-step" onClick={() => reveal("source")}><span className={photos.length ? "guide-check done" : "guide-check"}>{photos.length ? "✓" : "1"}</span><span><b>Выберите группу и фото</b><small>{photos.length ? `${photos.length} фото · ${ready} готовы` : "Откройте источник данных"}</small></span><ChevronDown size={13}/></button>
              <button className="guide-step" onClick={() => reveal("scene")}><span className={ready ? "guide-check done" : "guide-check"}>{ready ? "✓" : "2"}</span><span><b>Изучите 3D и миниатюры</b><small>Сцена, тепловая карта и морфинг</small></span><ChevronDown size={13}/></button>
              <button className="guide-step" onClick={() => reveal("timeline")}><span className="guide-check">3</span><span><b>Сопоставьте метрики</b><small>Выберите точку, чтобы перейти к кадру</small></span><ChevronDown size={13}/></button>
              <p className="guide-foot">Совет: колесо двигает поле · Ctrl/⌘ + колесо — масштаб</p>
            </section>}
          </Panel>
          {(latestProcess && ["queued", "running", "failed", "completed"].includes(latestProcess.status) && dismissedJob !== latestProcess.id) && <Panel position="top-center">
            <div className={`canvas-job-banner ${latestProcess.status}`} role="status">
              <div className="canvas-job-title"><span>{latestProcess.status === "running" ? <LoaderCircle size={13} className="spin"/> : latestProcess.status === "failed" ? <AlertCircle size={13}/> : latestProcess.status === "completed" ? <Check size={13}/> : <LoaderCircle size={13}/>}</span><b>{latestProcess.status === "failed" ? "Обработка завершилась с ошибкой" : latestProcess.status === "queued" ? "Обработка в очереди" : latestProcess.status === "completed" ? "Последняя обработка завершена" : "Идёт обработка фото"}</b><span>{Math.round(latestProcess.progress*100)}%</span>{["queued","running"].includes(latestProcess.status) ? <button className="icon-btn" title="Отменить обработку" onClick={()=>fetch(`/api/jobs/${latestProcess.id}/cancel`,{method:"POST"})}><X size={13}/></button> : <button className="icon-btn" title="Скрыть статус" onClick={()=>setDismissedJob(latestProcess.id)}><X size={13}/></button>}</div>
              <div className="canvas-job-track"><i style={{width:`${latestProcess.progress*100}%`}}/></div>
              <small>{latestProcess.status === "completed" && latestProcess.result ? `${latestProcess.result.photos} фото · ${latestProcess.result.errors?.length || 0} ошибок · ${latestProcess.result.cache_hits} из кэша` : latestProcess.message}{latestProcess.status === "failed" ? " · проверьте веса модели и настройки в узле 3DDFA_V3" : ""}</small>
            </div>
          </Panel>}
          <Panel position="top-left">
            <div className="canvas-breadcrumb">
              <span>01</span> РАБОЧЕЕ ПОЛЕ <i /> бесконечный канвас
            </div>
          </Panel>
          <Panel position="bottom-center">
            <div className="navigation-dock">
              <button
                className={grab ? "active" : ""}
                aria-label="Режим руки"
                title="Перемещать поле поверх любой панели · Space временно"
                onClick={() => setGrab(!grab)}
              >
                <Hand size={15} />
              </button>
              <i />
              {[
                ["scene", "3D", "1"],
                ["timeline", "Метрики", "2"],
                ["eyes", "Глаза", "3"],
                ["cluster", "Кластеры", "4"],
                ["source", "Фото", "5"],
              ].map(([id, label, key]) => (
                <button
                  key={id}
                  onClick={() => reveal(id)}
                  title={label + " · клавиша " + key}
                >
                  {label}
                  <kbd>{key}</kbd>
                </button>
              ))}
              <i />
              <button
                title="Все панели · F / Home"
                onClick={() => flow.fitView({ padding: 0.06, duration: 250 })}
              >
                <Maximize size={14} />
              </button>
              <button title="Миникарта" onClick={() => setShowMap(!showMap)}>
                <Map size={14} />
              </button>
            </div>
            <div className="navigation-hint">
              Колесо — перемещение · Ctrl/⌘ + колесо — масштаб · Space — рука
            </div>
          </Panel>
        </ReactFlow>
        {help && (
          <div className="help-panel">
            <div className="flex between">
              <strong>Рабочее поле</strong>
              <button className="icon-btn" onClick={() => setHelp(false)}>
                <X size={14} />
              </button>
            </div>
            <p>
              <kbd>Space</kbd> + мышь — двигать канвас
            </p>
            <p>
              Колесо — перемещение; Ctrl/⌘ + колесо — масштаб. За заголовок —
              перемещение ноды.
            </p>
            <p>Потяните от разъёма, чтобы соединить совместимые данные.</p>
            <p>
              <kbd>Ctrl/⌘</kbd> + фото — маршрут до 10 кадров.
            </p>
            <p>
              <kbd>Shift</kbd> + фото — диапазон. Двойной клик — дата и углы.
            </p>
            <p>Свернуть ≠ отключить. Выключенный плагин сохраняет кэш.</p>
            <button
              className="text-button"
              onClick={() => {
                useStore.setState({
                  nodes: initialNodes.map((n) => ({ ...n })),
                  edges: initialEdges,
                });
                setHelp(false);
                setTimeout(
                  () =>
                    flow.fitView({
                      nodes: [{ id: "scene" }, { id: "timeline" }],
                      padding: 0.07,
                      duration: 400,
                    }),
                  100,
                );
              }}
            >
              <Undo2 size={12} /> Сбросить только раскладку
            </button>
          </div>
        )}
        {toast && (
          <div role="status" className="toast">
            <span>{toast}</span>
            <button
              className="icon-btn"
              onClick={() => useStore.setState({ toast: null })}
            >
              <X size={13} />
            </button>
          </div>
        )}
        <PhotoEditor />
      </div>
      <footer className="app-status">
        <span>
          <span className="status-dot" /> {ready} фото в кэше <b>·</b>{" "}
          {models.find((m) => m.id === "3ddfa_v3")?.available
            ? models.find((m) => m.id === "3ddfa_v3")?.enabled
              ? "3DDFA_V3 готова"
              : "3DDFA_V3 выключена"
            : "Нет весов · доступен кэш"}
          {activeJobs.length > 0 && (
            <span className="status-job">
              <LoaderCircle className="spin" size={10} />{" "}
              {activeJobs[0].message}
            </span>
          )}
        </span>
        {hasDemo ? (
          <span className="demo-disclaimer">
            Демо: варианты одного синтетического фото · даты условные
          </span>
        ) : (
          <span className="muted">
            Обработка в среде проекта · без внешнего inference API
          </span>
        )}
        <span className="status-right">
          seed 42 <b>·</b> workspace.json
        </span>
      </footer>
    </main>
  );
}
export default function App() {
  return (
    <ReactFlowProvider>
      <Workbench />
    </ReactFlowProvider>
  );
}
