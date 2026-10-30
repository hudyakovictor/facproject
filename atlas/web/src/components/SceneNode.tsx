import { memo, useState } from "react";
import { NodeResizer, useReactFlow, type NodeProps } from "@xyflow/react";
import {
  Focus,
  PanelRightClose,
  SlidersHorizontal,
  ChartNoAxesCombined,
} from "lucide-react";
import { useStore, type WorkNode, poseLabels } from "../store";
import { Viewer, HeatControls } from "./Viewer";
import { Timeline } from "./Timeline";
import { NodeHead, Port, Empty } from "./ui";
import type { HeatStats } from "../heat";
export const SceneNode = memo(function SceneNode({
  id,
  data,
  selected,
  height,
}: NodeProps<WorkNode>) {
  const [stats, setStats] = useState<HeatStats | null>(null),
    open = useStore((s) => s.settingsOpen),
    set = useStore((s) => s.set),
    patch = useStore((s) => s.patchNode),
    active = useStore((s) => s.photos.find((p) => p.id === s.activeId)),
    rf = useReactFlow();
  return (
    <div
      className={
        "node-card scene-node scene-v2 " + (data.collapsed ? "collapsed" : "")
      }
    >
      <NodeResizer
        isVisible={selected && !data.collapsed}
        minWidth={560}
        minHeight={480}
        lineStyle={{ borderColor: "#65d9b9" }}
      />
      <NodeHead
        id={id}
        title="3D · морфинг · фотографии"
        icon={<Focus size={16} />}
        collapsed={data.collapsed}
        badge={
          <span className="scene-connection">
            {active ? poseLabels[active.pose] : "Нет кадра"}
          </span>
        }
        onExpand={() =>
          rf.fitView({ nodes: [{ id }], padding: 0.06, duration: 280 })
        }
        onHide={() => patch(id, { previewHidden: !data.previewHidden })}
        hiddenPreview={data.previewHidden}
      >
        <button
          className={"icon-btn nodrag " + (open ? "active" : "")}
          title="Параметры тепловой карты"
          onClick={() => set({ settingsOpen: !open })}
        >
          {open ? (
            <PanelRightClose size={15} />
          ) : (
            <SlidersHorizontal size={15} />
          )}
        </button>
      </NodeHead>
      {!data.collapsed && (
        <>
          <div className="scene-stage">
            {data.previewHidden ? (
              <Empty
                title="Сцена скрыта"
                detail="Геометрия и исходники сохранены."
              />
            ) : (
              <Viewer sceneId={id} onStats={setStats} />
            )}{" "}
            {open && <HeatControls stats={stats} />}
          </div>
          <Timeline
            sceneId={id}
            stats={stats}
            variant="morph"
            paneHeight={height || 650}
          />
        </>
      )}
      <Port
        id="mesh"
        type="target"
        color="#b29bea"
        top={data.collapsed ? "50%" : 110}
      />
    </div>
  );
});
export const MetricsTimelineNode = memo(function MetricsTimelineNode({
  id,
  data,
  selected,
  height,
}: NodeProps<WorkNode>) {
  const rf = useReactFlow();
  return (
    <div
      className={
        "node-card metrics-timeline-node " + (data.collapsed ? "collapsed" : "")
      }
    >
      <NodeResizer
        isVisible={selected && !data.collapsed}
        minWidth={560}
        minHeight={280}
      />
      <NodeHead
        id={id}
        title="Таймлайн · измерения"
        subtitle="Отдельная панель · общий выбор и курсор"
        icon={<ChartNoAxesCombined size={15} />}
        collapsed={data.collapsed}
        onExpand={() =>
          rf.fitView({ nodes: [{ id }], padding: 0.08, duration: 280 })
        }
      />
      {!data.collapsed && (
        <Timeline
          sceneId={id}
          stats={null}
          variant="metrics"
          paneHeight={height || 410}
        />
      )}
      <Port
        id="series"
        type="target"
        color="#62d5b2"
        top={data.collapsed ? "50%" : 100}
      />
    </div>
  );
});
