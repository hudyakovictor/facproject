import { useEffect, useMemo, useState } from "react";
import { Background, Controls, Handle, MiniMap, Panel, Position, ReactFlow, ReactFlowProvider, useEdgesState, useNodesState, useReactFlow } from "@xyflow/react";
import ELK from "elkjs/lib/elk.bundled.js";
import "@xyflow/react/dist/style.css";
import type { CanvasEdge, CanvasGraph, CanvasNodeData, ReadinessItem } from "./types";
import { loadCanvas, loadReadiness } from "./api";
import { uiLog } from "./logStore";

const elk = new ELK();
type Level = "stages" | "modules" | "functions" | "search";
type DisplayNode = CanvasNodeData & { childCount?: number };

function PipelineNode({ data }: { data: DisplayNode }) {
  return <div className={`pipeline-node ${data.kind} status-${data.status}`} tabIndex={0}>
    <Handle type="target" position={Position.Left} />
    <div className="node-kicker">{data.kind}{data.childCount != null ? ` · ${data.childCount}` : ""}</div>
    <b>{data.title}</b><small>{data.technical_name}</small>
    <div className="node-footer"><span>{data.status}</span>{data.criticality === "critical" && <i>critical</i>}</div>
    <Handle type="source" position={Position.Right} />
  </div>;
}
const nodeTypes = { pipeline: PipelineNode };

async function layout(nodes: any[], edges: any[]) {
  const result = await elk.layout({ id: "root", layoutOptions: {
    "elk.algorithm": "layered", "elk.direction": "RIGHT", "elk.spacing.nodeNode": "46",
    "elk.layered.spacing.nodeNodeBetweenLayers": "120", "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  }, children: nodes.map((n) => ({ id: n.id, width: 250, height: 96 })), edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })) });
  const positions = new Map((result.children ?? []).map((n) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }]));
  return nodes.map((n) => ({ ...n, position: positions.get(n.id) ?? { x: 0, y: 0 } }));
}

function uniqueEdges(edges: CanvasEdge[], representative: (id: string) => string | null, visible: Set<string>) {
  const seen = new Set<string>();
  const out: any[] = [];
  for (const edge of edges) {
    if (edge.label === "contains") continue;
    const source = representative(edge.source), target = representative(edge.target);
    if (!source || !target || source === target || !visible.has(source) || !visible.has(target)) continue;
    const key = `${source}→${target}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ id: key, source, target, animated: edge.confidence === "runtime_observed", className: `edge-${edge.confidence}` });
  }
  return out;
}

function Explorer({ graph, readiness }: { graph: CanvasGraph; readiness: ReadinessItem[] }) {
  const rf = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);
  const [level, setLevel] = useState<Level>("stages");
  const [stage, setStage] = useState<string | null>(null);
  const [moduleId, setModuleId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<DisplayNode | null>(null);
  const [layoutBusy, setLayoutBusy] = useState(false);

  const nodeMap = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph]);
  const modules = useMemo(() => graph.nodes.filter((n) => n.kind === "module"), [graph]);
  const functions = useMemo(() => graph.nodes.filter((n) => n.kind === "function"), [graph]);

  const model = useMemo(() => {
    let display: DisplayNode[] = [];
    let representative: (id: string) => string | null = () => null;
    const q = query.trim().toLowerCase();

    if (q) {
      display = functions.filter((n) => `${n.title} ${n.technical_name}`.toLowerCase().includes(q)).slice(0, 80);
      const ids = new Set(display.map((n) => n.id));
      representative = (id) => ids.has(id) ? id : null;
    } else if (level === "stages") {
      display = graph.nodes.filter((n) => n.kind === "stage").map((n) => ({ ...n, childCount: functions.filter((f) => f.stage === n.stage).length }));
      representative = (id) => { const n = nodeMap.get(id); return n?.stage ? `stage:${n.stage}` : null; };
    } else if (level === "modules" && stage) {
      display = modules.map((n) => ({ ...n, childCount: functions.filter((f) => f.parent_id === n.id).length })).filter((n) => n.stage === stage && (n.childCount ?? 0) > 0);
      representative = (id) => { const n = nodeMap.get(id); if (!n || n.stage !== stage) return null; return n.kind === "module" ? n.id : n.parent_id; };
    } else if (moduleId) {
      display = functions.filter((n) => n.parent_id === moduleId);
      const ids = new Set(display.map((n) => n.id));
      representative = (id) => ids.has(id) ? id : null;
    }
    const visible = new Set(display.map((n) => n.id));
    return { display, edges: uniqueEdges(graph.edges, representative, visible), search: Boolean(q) };
  }, [query, level, stage, moduleId, graph, functions, modules, nodeMap]);

  useEffect(() => {
    let cancelled = false;
    setLayoutBusy(true);
    const raw = model.display.map((n) => ({ id: n.id, type: "pipeline", position: { x: 0, y: 0 }, data: n }));
    layout(raw, model.edges).then((positioned) => {
      if (cancelled) return;
      setNodes(positioned); setEdges(model.edges); setLayoutBusy(false);
      window.requestAnimationFrame(() => rf.fitView({ padding: .18, duration: 240, maxZoom: 1 }));
      uiLog("debug", "canvas", `Отображено ${positioned.length} узлов (${model.search ? "поиск" : level})`);
    }).catch((e) => { if (!cancelled) { setLayoutBusy(false); uiLog("error", "canvas", String(e)); } });
    return () => { cancelled = true; };
  }, [model, level, setNodes, setEdges, rf]);

  function drill(node: DisplayNode) {
    setSelected(node);
    if (query.trim()) return;
    if (node.kind === "stage") { setStage(node.stage); setModuleId(null); setLevel("modules"); }
    else if (node.kind === "module") { setModuleId(node.id); setLevel("functions"); }
  }
  function home() { setQuery(""); setStage(null); setModuleId(null); setLevel("stages"); setSelected(null); }
  function back() {
    setSelected(null);
    if (query) { setQuery(""); return; }
    if (level === "functions") { setModuleId(null); setLevel("modules"); }
    else home();
  }

  const selectedReadiness = selected?.kind === "function" ? readiness.find((x) => x.function_id === selected.technical_name) : null;
  const stageNode = stage ? nodeMap.get(`stage:${stage}`) : null;
  const moduleNode = moduleId ? nodeMap.get(moduleId) : null;

  return <div className="canvas-explorer">
    <div className="canvas-commandbar">
      <div className="breadcrumbs"><button onClick={home}>Pipeline</button>{stageNode && <><span>›</span><button onClick={() => { setModuleId(null); setLevel("modules"); }}>{stageNode.title}</button></>}{moduleNode && <><span>›</span><b>{moduleNode.title}</b></>}</div>
      <input value={query} onChange={(e) => { setQuery(e.target.value); setSelected(null); }} placeholder="Найти функцию во всём проекте…" aria-label="Поиск функции" />
      {(level !== "stages" || query) && <button className="back-button" onClick={back}>← Назад</button>}
    </div>
    <div className="canvas-body">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={(_, n: any) => drill(n.data)} onPaneClick={() => setSelected(null)} colorMode="dark" minZoom={.15} maxZoom={1.8} onlyRenderVisibleElements fitView>
        <Background gap={24} size={1} /><MiniMap pannable zoomable /><Controls showInteractive={false} />
        <Panel position="top-left" className="canvas-stats">{layoutBusy ? "Раскладка…" : `${nodes.length} узлов · ${edges.length} связей`}</Panel>
        <Panel position="top-right" className="canvas-actions"><button onClick={() => rf.fitView({ padding: .18, duration: 220, maxZoom: 1 })}>Вписать</button><button onClick={() => rf.zoomTo(1, { duration: 180 })}>100%</button></Panel>
      </ReactFlow>
      <aside className={`canvas-inspector ${selected ? "open" : ""}`}>
        {selected ? <><button className="inspector-close" onClick={() => setSelected(null)}>×</button><p className="eyebrow">{selected.kind}</p><h2>{selected.title}</h2><code>{selected.technical_name}</code><dl><div><dt>Этап</dt><dd>{selected.stage}</dd></div><div><dt>Статус</dt><dd>{selected.status}</dd></div><div><dt>Критичность</dt><dd>{selected.criticality}</dd></div>{selected.childCount != null && <div><dt>Внутри</dt><dd>{selected.childCount}</dd></div>}</dl>{selected.kind !== "function" && <button className="drill-button" onClick={() => drill(selected)}>Открыть содержимое →</button>}{selectedReadiness && <div className="readiness-detail"><h3>Readiness</h3><b>{selectedReadiness.status}</b><p>{selectedReadiness.explanation}</p><small>Не закрыто: {selectedReadiness.missing.join(", ") || "нет"}</small></div>}</> : <div className="inspector-placeholder"><b>Инспектор</b><p>Выберите этап, модуль или функцию. Двойной объём данных больше не рендерится одновременно.</p></div>}
      </aside>
    </div>
  </div>;
}

export function PipelineCanvas() {
  const [graph, setGraph] = useState<CanvasGraph | null>(null);
  const [readiness, setReadiness] = useState<ReadinessItem[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([loadCanvas(), loadReadiness()]).then(([g, r]) => { setGraph(g); setReadiness(r); uiLog("info", "canvas", `Граф загружен: ${g.summary.nodes} узлов; включён поэтапный режим`); }).catch((e) => { setError(String(e)); uiLog("error", "canvas", String(e)); }); }, []);
  if (error) return <div className="canvas-error">Не удалось загрузить карту: {error}</div>;
  if (!graph) return <div className="canvas-loading">Загрузка карты проекта…</div>;
  return <ReactFlowProvider><Explorer graph={graph} readiness={readiness} /></ReactFlowProvider>;
}
