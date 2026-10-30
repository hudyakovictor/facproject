import { memo, type ReactNode, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  ChevronDown,
  ChevronRight,
  MoreHorizontal,
  Maximize2,
  Eye,
  EyeOff,
  X,
  Check,
  LoaderCircle,
} from "lucide-react";
import { useStore, type WorkNode } from "../store";
export function Toggle({
  checked,
  onChange,
  disabled = false,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <button
      aria-label={label || "Включить"}
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      className={"switch nodrag " + (checked ? "on" : "")}
      onClick={() => onChange(!checked)}
    >
      <span />
    </button>
  );
}
export function Slider({
  label,
  value,
  min,
  max,
  step = 0.01,
  onChange,
  format,
  unit = "",
  disabled = false,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (n: number) => void;
  format?: (n: number) => string;
  unit?: string;
  disabled?: boolean;
}) {
  return (
    <label className={"slider-control " + (disabled ? "disabled" : "")}>
      <span className="slider-label">
        <span>{label}</span>
        <span className="numeric">
          {format
            ? format(Number.isFinite(value) ? value : 0)
            : Number(
                (Number.isFinite(value) ? value : 0).toFixed(
                  step < 0.001 ? 4 : step < 0.1 ? 2 : step < 1 ? 1 : 0,
                ),
              )}
          {unit}
        </span>
      </span>
      <input
        aria-label={label}
        className="nodrag nowheel"
        type="range"
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        value={value}
        onChange={(e) => onChange(+e.target.value)}
      />
    </label>
  );
}
export const NodeHead = memo(function NodeHead({
  id,
  title,
  icon,
  subtitle,
  badge,
  collapsed,
  children,
  onExpand,
  onHide,
  hiddenPreview = false,
}: {
  id: string;
  title: string;
  icon: ReactNode;
  subtitle?: string;
  badge?: ReactNode;
  collapsed?: boolean;
  children?: ReactNode;
  onExpand?: () => void;
  onHide?: () => void;
  hiddenPreview?: boolean;
}) {
  const patch = useStore((s) => s.patchNode);
  const [menu, setMenu] = useState(false);
  return (
    <header className="node-head">
      <div className="node-title">
        <span className="node-symbol">{icon}</span>
        <div>
          <strong>{title}</strong>
          {subtitle && <small>{subtitle}</small>}
        </div>
      </div>
      <div className="node-head-actions">
        {badge}
        {children}
        {onHide && (
          <button
            className="icon-btn nodrag"
            title="Скрыть превью, сохранив данные"
            onClick={onHide}
          >
            {hiddenPreview ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
        )}
        {onExpand && (
          <button
            className="icon-btn nodrag"
            title="Раскрыть"
            onClick={onExpand}
          >
            <Maximize2 size={14} />
          </button>
        )}
        <button
          className="icon-btn nodrag"
          title={collapsed ? "Развернуть ноду" : "Свернуть ноду"}
          onClick={() => patch(id, { collapsed: !collapsed })}
        >
          {collapsed ? <ChevronRight size={15} /> : <ChevronDown size={15} />}
        </button>
        <div className="relative">
          <button
            className="icon-btn nodrag"
            title="Действия"
            onClick={() => setMenu(!menu)}
          >
            <MoreHorizontal size={16} />
          </button>
          {menu && (
            <div className="node-menu nodrag">
              <button
                onClick={() => {
                  patch(id, { collapsed: !collapsed });
                  setMenu(false);
                }}
              >
                {collapsed ? "Развернуть" : "Свернуть"}
              </button>
              <button
                onClick={() => {
                  useStore.setState((s) => ({
                    nodes: s.nodes.filter((n) => n.id !== id),
                    edges: s.edges.filter(
                      (e) => e.source !== id && e.target !== id,
                    ),
                    workspaceVersion: s.workspaceVersion + 1,
                  }));
                  setMenu(false);
                }}
              >
                Убрать с канваса
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
});
export function Port({
  id,
  type,
  label,
  color,
  top,
}: {
  id: string;
  type: "source" | "target";
  label?: string;
  color?: string;
  top?: string | number;
}) {
  return (
    <>
      <Handle
        id={id}
        type={type}
        position={type === "source" ? Position.Right : Position.Left}
        style={{
          top: top || "50%",
          background: color || "#64cdb5",
          borderColor: "#17232f",
          width: 10,
          height: 10,
        }}
      />
      {label && (
        <span
          className={"port-label " + type}
          style={{ top: top || "50%", color: color || "#89a9b4" }}
        >
          {label}
        </span>
      )}
    </>
  );
}
export function Empty({
  title,
  detail,
  children,
}: {
  title: string;
  detail?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark">◇</div>
      <strong>{title}</strong>
      {detail && <p>{detail}</p>}
      {children}
    </div>
  );
}
export function StatusDot({ on = true }: { on?: boolean }) {
  return <span className={"status-dot " + (!on ? "off" : "")} />;
}
export function JobProgress({ job }: { job: import("../types").Job }) {
  return (
    <div className="job-progress">
      <div className="flex between">
        <span>
          {job.status === "running" ? (
            <LoaderCircle className="spin inline" size={11} />
          ) : null}{" "}
          {job.message}
        </span>
        {["queued", "running"].includes(job.status) && (
          <button
            className="icon-btn nodrag"
            title="Отменить"
            onClick={() =>
              fetch("/api/jobs/" + job.id + "/cancel", { method: "POST" })
            }
          >
            <X size={12} />
          </button>
        )}
      </div>
      <div className="progress-track">
        <i
          className={job.progress > 0 ? "" : "indeterminate"}
          style={{ width: job.progress * 100 + "%" }}
        />
      </div>
    </div>
  );
}
