import { create } from "zustand";
import {
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type NodeChange,
  type EdgeChange,
  type Connection,
  addEdge,
} from "@xyflow/react";
import { api } from "./api";
import type {
  Photo,
  Model,
  Job,
  Profiles,
  MetricTable,
  HeatSettings,
  Health,
} from "./types";
export type WorkNode = Node<Record<string, any>>;
export const initialNodes: WorkNode[] = [
  {
    id: "scene",
    type: "scene",
    position: { x: 0, y: 0 },
    style: { width: 950, height: 760 },
    dragHandle: ".node-head",
    data: { title: "3D · морфинг · фотографии" },
  },
  {
    id: "timeline",
    type: "timeline",
    position: { x: 0, y: 790 },
    style: { width: 950, height: 390 },
    dragHandle: ".node-head",
    data: { title: "Таймлайн · измерения" },
  },
  {
    id: "source",
    type: "source",
    position: { x: -330, y: 0 },
    style: { width: 260 },
    dragHandle: ".node-head",
    data: { title: "Библиотека" },
  },
  {
    id: "recon",
    type: "processor",
    position: { x: -330, y: 530 },
    style: { width: 260 },
    dragHandle: ".node-head",
    data: { title: "3DDFA_V3", collapsed: true },
  },
  {
    id: "metrics",
    type: "metricProcessor",
    position: { x: -330, y: 585 },
    style: { width: 260 },
    dragHandle: ".node-head",
    data: { title: "Реестр метрик", collapsed: true },
  },
  {
    id: "cluster",
    type: "cluster",
    position: { x: 990, y: 790 },
    style: { width: 420 },
    dragHandle: ".node-head",
    data: { title: "Облако α_id", compact: false },
  },
  {
    id: "eyes",
    type: "eyes",
    position: { x: 990, y: 0 },
    style: { width: 500 },
    dragHandle: ".node-head",
    data: { title: "Глаза · контроль измерений" },
  },
  {
    id: "poses",
    type: "poses",
    position: { x: 1550, y: 0 },
    style: { width: 660 },
    hidden: true,
    dragHandle: ".node-head",
    data: { title: "Пять ракурсов" },
  },
  {
    id: "registry",
    type: "registry",
    position: { x: 1550, y: 650 },
    style: { width: 660 },
    hidden: true,
    dragHandle: ".node-head",
    data: { title: "Метрики и пороги" },
  },
];
export const initialEdges: Edge[] = [
  {
    id: "photos-recon",
    source: "source",
    sourceHandle: "photos",
    target: "recon",
    targetHandle: "photos",
    type: "default",
    style: { stroke: "#68b9ca", strokeWidth: 1.5 },
  },
  {
    id: "mesh-scene",
    source: "recon",
    sourceHandle: "mesh",
    target: "scene",
    targetHandle: "mesh",
    style: { stroke: "#ae9bec", strokeWidth: 1.5 },
  },
  {
    id: "landmarks-metrics",
    source: "recon",
    sourceHandle: "landmarks",
    target: "metrics",
    targetHandle: "landmarks",
    style: { stroke: "#e6b96f", strokeWidth: 1.5 },
  },
  {
    id: "series-timeline",
    source: "metrics",
    sourceHandle: "series",
    target: "timeline",
    targetHandle: "series",
    style: { stroke: "#58ccb1", strokeWidth: 1.5 },
  },
  {
    id: "id-cluster",
    source: "recon",
    sourceHandle: "alpha_id",
    target: "cluster",
    targetHandle: "embedding",
    style: { stroke: "#a997e9", strokeWidth: 1.5 },
  },
];
const defaultHeat: HeatSettings = {
  enabled: true,
  photoTexture: true,
  noiseCorrection: false,
  normalizeScale: false,
  metric: "distance",
  weighting: "none",
  reference: "previous",
  // Fixed thresholds keep the same colors comparable between photos.
  vmin: 0.0003,
  vmax: 0.084,
  auto: false,
  percentile: 95,
  gamma: 2,
  opacity: 0.78,
  outsideOpacity: 0.05,
  palette: "turbo",
  inverse: false,
  onlyAbove: true,
  smoothing: 0,
  low: "#3155c6",
  mid: "#5bd8b1",
  high: "#ed6558",
  midPosition: 0.5,
  texture: false,
  wireframe: false,
  ldm68: false,
  ldm106: true,
  ldm134: false,
  pointSize: 2.3,
  view: "front",
  viewFromPhoto: true,
};
export interface State {
  photos: Photo[];
  groups: string[];
  models: Model[];
  jobs: Job[];
  /** Состояние SSE-канала и время последнего сообщения — для окна статуса. */
  sse: "connecting" | "open" | "closed";
  eventsAt: number;
  /** Пульс API: последний ответ /api/health и его задержка. */
  apiOk: boolean;
  apiAt: number;
  apiLatency: number | null;
  health: Health | null;
  profiles: Profiles | null;
  metrics: MetricTable;
  group: string;
  secondsPerPhoto: number | null;
  loaded: boolean;
  error: string | null;
  toast: string | null;
  activeId: string;
  route: string[];
  mode: "photo" | "morph";
  playhead: number;
  playing: boolean;
  textureStatus: "loading" | "ready" | "failed";
  duration: number;
  fps: number;
  easing: "linear" | "smooth";
  heat: HeatSettings;
  visibleMetrics: string[] | null;
  timelineMode: "value" | "z" | "delta";
  timeAxis: boolean;
  settingsOpen: boolean;
  nodes: WorkNode[];
  edges: Edge[];
  workspaceVersion: number;
  photoEditor: string | null;
  init: () => Promise<void>;
  refresh: () => Promise<void>;
  refreshMetrics: () => Promise<void>;
  setGroup: (g: string) => void;
  selectPhoto: (id: string, multi?: boolean, range?: boolean) => void;
  setRoute: (ids: string[]) => void;
  setHeat: (v: Partial<HeatSettings>) => void;
  set: (p: Partial<State>) => void;
  notify: (s: string) => void;
  onNodesChange: (c: NodeChange<WorkNode>[]) => void;
  onEdgesChange: (c: EdgeChange[]) => void;
  onConnect: (c: Connection) => void;
  patchNode: (id: string, data: Record<string, any>) => void;
  revealNode: (id: string, position?: { x: number; y: number }) => void;
}
let initPromise: Promise<void> | null = null;
export const useStore = create<State>((set, get) => ({
  photos: [],
  groups: [],
  models: [],
  jobs: [],
  sse: "connecting",
  eventsAt: 0,
  apiOk: false,
  apiAt: 0,
  apiLatency: null,
  health: null,
  profiles: null,
  metrics: { catalog: [], rows: [], config_version: "" },
  group: "",
  secondsPerPhoto: null,
  loaded: false,
  error: null,
  toast: null,
  activeId: "",
  route: [],
  mode: "photo",
  playhead: 0,
  playing: false,
  textureStatus: "ready",
  duration: 2,
  fps: 24,
  easing: "smooth",
  heat: defaultHeat,
  visibleMetrics: null,
  timelineMode: "value",
  timeAxis: false,
  settingsOpen: false,
  nodes: initialNodes,
  edges: initialEdges,
  workspaceVersion: 0,
  photoEditor: null,
  init: () => {
    if (initPromise) return initPromise;
    initPromise = (async () => {
      try {
        const [lib, models, profiles, metrics, ws] = await Promise.all([
          api("/library"),
          api("/models"),
          api("/profiles"),
          api("/metrics"),
          api("/workspace"),
        ]);
        const photos = lib.photos as Photo[],
          saved = ws?.preferences || {};
        const defaultGroup =
          lib.groups.find((g: string) =>
            photos.some((p: Photo) => p.group === g && !p.demo),
          ) ||
          lib.groups[0] ||
          "";
        const savedGroupIsDemoOnly =
          saved.group === "__all"
            ? photos.some((p: Photo) => p.demo) &&
              photos.some((p: Photo) => !p.demo)
            : !!saved.group &&
              photos
                .filter((p: Photo) => p.group === saved.group)
                .every((p: Photo) => p.demo);
        const group =
          (saved.group === "__all" || lib.groups.includes(saved.group)) &&
          !savedGroupIsDemoOnly
            ? saved.group
            : defaultGroup;
        const ps = photos.filter(
          (p) =>
            (group === "__all" || p.group === group) && p.status === "ready",
        );
        set({
          photos,
          groups: lib.groups,
          models,
          profiles,
          metrics,
          jobs: lib.jobs,
          group,
          secondsPerPhoto: lib.seconds_per_photo,
          loaded: true,
          activeId: ps.some((p: Photo) => p.id === saved.activeId)
            ? saved.activeId
            : ps[Math.min(2, ps.length - 1)]?.id || "",
          route:
            saved.route?.filter((id: string) =>
              ps.some((p: Photo) => p.id === id),
            ).length >= 2
              ? saved.route
                  .filter((id: string) => ps.some((p: Photo) => p.id === id))
                  .slice(0, 10)
              : ps.slice(0, 3).map((p) => p.id),
          heat: {
            ...defaultHeat,
            ...(ws?.version >= 2
              ? saved.heat
              : { reference: saved.heat?.reference || "first" }),
          },
          visibleMetrics: saved.visibleMetrics ?? null,
          nodes:
            ws?.version >= 3 && ws?.nodes?.length
              ? ws.nodes.map((n: any) => ({ ...n, dragHandle: ".node-head" }))
              : initialNodes,
          edges: ws?.version >= 3 ? ws.edges || initialEdges : initialEdges,
        });
      } catch (e) {
        set({ error: String(e), loaded: true });
      }
    })();
    return initPromise;
  },
  refresh: async () => {
    try {
      const [lib, models] = await Promise.all([
        api("/library"),
        api("/models"),
      ]);
      const s = get();
      let group =
        s.group === "__all" || lib.groups.includes(s.group)
          ? s.group
          : lib.groups[0] || "";
      const ps: Photo[] = lib.photos.filter(
        (p: Photo) =>
          (group === "__all" || p.group === group) && p.status === "ready",
      );
      set({
        photos: lib.photos,
        groups: lib.groups,
        models,
        jobs: lib.jobs,
        group,
        secondsPerPhoto: lib.seconds_per_photo,
        ...(!ps.some((p) => p.id === s.activeId)
          ? {
              activeId: ps[0]?.id || "",
              route: ps.slice(0, 3).map((p) => p.id),
              mode: "photo" as const,
              playing: false,
            }
          : {}),
      });
      await get().refreshMetrics();
    } catch (e) {
      get().notify(String(e));
    }
  },
  refreshMetrics: async () => {
    try {
      set({ metrics: await api("/metrics"), profiles: await api("/profiles") });
    } catch (e) {
      get().notify(String(e));
    }
  },
  setGroup: (group) => {
    const ps = get().photos.filter(
      (p) => (group === "__all" || p.group === group) && p.status === "ready",
    );
    set({
      group,
      activeId: ps[Math.min(2, ps.length - 1)]?.id || "",
      route: ps.slice(0, 3).map((p) => p.id),
      mode: "photo",
      playing: false,
      playhead: 0,
    });
  },
  selectPhoto: (id, multi = false, range = false) => {
    const s = get();
    let route = [id];
    if (multi) {
      route = s.route.includes(id)
        ? s.route.filter((x) => x !== id)
        : [...s.route, id];
      if (route.length > 10) {
        s.notify("В маршруте максимум 10 фото");
        return;
      }
      const ps = s.photos
        .filter((p) => (s.group === "__all" || p.group === s.group) && p.status === "ready")
        .sort((a, b) => (a.date || "9999").localeCompare(b.date || "9999") || a.name.localeCompare(b.name));
      route.sort(
        (a, b) =>
          ps.findIndex((p) => p.id === a) - ps.findIndex((p) => p.id === b),
      );
    }
    if (range) {
      const ps = s.photos.filter(
        (p) =>
          (s.group === "__all" || p.group === s.group) && p.status === "ready",
      );
      const a = ps.findIndex((p) => p.id === s.activeId),
        b = ps.findIndex((p) => p.id === id);
      route = ps
        .slice(Math.min(a, b), Math.max(a, b) + 1)
        .slice(0, 10)
        .map((p) => p.id);
    }
    set({ activeId: id, route, mode: "photo", playing: false });
  },
  setRoute: (route) =>
    set({ route, mode: "morph", playhead: 0, playing: false }),
  setHeat: (v) => set((s) => ({ heat: { ...s.heat, ...v } })),
  set: (p) => set(p),
  notify: (toast) => {
    set({ toast });
    setTimeout(() => {
      if (get().toast === toast) set({ toast: null });
    }, 6500);
  },
  onNodesChange: (c) =>
    set((s) => ({
      nodes: applyNodeChanges(c, s.nodes),
      workspaceVersion: s.workspaceVersion + 1,
    })),
  onEdgesChange: (c) =>
    set((s) => ({
      edges: applyEdgeChanges(c, s.edges),
      workspaceVersion: s.workspaceVersion + 1,
    })),
  onConnect: (c) =>
    set((s) => ({
      edges: addEdge(
        {
          ...c,
          style: {
            stroke: c.sourceHandle === "alpha_id" ? "#ad98ec" : "#69cbb5",
            strokeWidth: 1.5,
          },
        },
        s.edges.filter(
          (e) => !(e.target === c.target && e.targetHandle === c.targetHandle),
        ),
      ),
      workspaceVersion: s.workspaceVersion + 1,
    })),
  patchNode: (id, data) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id
          ? {
              ...n,
              ...(n.type === "scene" && "collapsed" in data
                ? {
                    style: {
                      ...n.style,
                      height: data.collapsed ? 48 : n.data.savedHeight || 760,
                    },
                  }
                : {}),
              data: {
                ...n.data,
                ...(n.type === "scene" && data.collapsed
                  ? { savedHeight: n.height || 760 }
                  : {}),
                ...data,
              },
            }
          : n,
      ),
      workspaceVersion: s.workspaceVersion + 1,
    })),
  revealNode: (id, position) =>
    set((s) => ({
      nodes: s.nodes.map((n) =>
        n.id === id
          ? {
              ...n,
              hidden: !n.hidden,
              ...(position ? { position } : {}),
              selected: true,
            }
          : n,
      ),
      workspaceVersion: s.workspaceVersion + 1,
    })),
}));
export const readyPhotos = (s: State) =>
  s.photos.filter(
    (p) => (s.group === "__all" || p.group === s.group) && p.status === "ready",
  );
export function morphSegment(route: string[], head: number) {
  if (route.length < 2) return { a: route[0], b: route[0], t: 0 };
  const x = Math.min(Math.max(head, 0), 0.999999) * (route.length - 1),
    i = Math.min(Math.floor(x), route.length - 2);
  return { a: route[i], b: route[i + 1], t: head >= 1 ? 1 : x - i };
}
export const poseLabels: Record<string, string> = {
  frontal: "Фронтальный",
  three_quarter_left: "Полупрофиль ←",
  three_quarter_right: "Полупрофиль →",
  profile_left: "Профиль ←",
  profile_right: "Профиль →",
  unclassified: "Вне профилей",
};
