import { memo, useEffect, useRef, useState } from "react";
import type { NodeProps } from "@xyflow/react";
import {
  Compass,
  Activity,
  RefreshCw,
  Search,
  FileCode2,
  Check,
  AlertTriangle,
} from "lucide-react";
import { useStore, type WorkNode, poseLabels } from "../store";
import type { Profiles, Metric } from "../types";
import { api, post } from "../api";
import { NodeHead, Toggle, Slider } from "./ui";
function RangePair({
  label,
  value,
  limit,
  onChange,
}: {
  label: string;
  value: [number, number];
  limit: number;
  onChange: (a: [number, number]) => void;
}) {
  return (
    <div className="angle-range">
      <div className="flex between mini">
        <span>{label}</span>
        <span className="angle-numbers">
          <input
            aria-label={label + " минимум"}
            type="number"
            min={-limit}
            max={value[1] - 1}
            value={value[0]}
            onChange={(e) =>
              onChange([
                Math.max(-limit, Math.min(value[1] - 1, +e.target.value)),
                value[1],
              ])
            }
          />
          <span>…</span>
          <input
            aria-label={label + " максимум"}
            type="number"
            min={value[0] + 1}
            max={limit}
            value={value[1]}
            onChange={(e) =>
              onChange([
                value[0],
                Math.min(limit, Math.max(value[0] + 1, +e.target.value)),
              ])
            }
          />
          <span>°</span>
        </span>
      </div>
      <input
        aria-label={label + " нижняя граница"}
        type="range"
        min={-limit}
        max={limit}
        step={1}
        value={value[0]}
        onChange={(e) =>
          onChange([Math.min(+e.target.value, value[1] - 1), value[1]])
        }
      />
      <input
        aria-label={label + " верхняя граница"}
        type="range"
        min={-limit}
        max={limit}
        step={1}
        value={value[1]}
        onChange={(e) =>
          onChange([value[0], Math.max(+e.target.value, value[0] + 1)])
        }
      />
    </div>
  );
}
export const PoseNode = memo(function PoseNode({
  id,
  data,
}: NodeProps<WorkNode>) {
  const actual = useStore((s) => s.profiles),
    photos = useStore((s) => s.photos),
    refresh = useStore((s) => s.refresh),
    notify = useStore((s) => s.notify);
  const [draft, setDraft] = useState<Profiles | null>(actual),
    [status, setStatus] = useState("Сохранено");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => setDraft(actual), [actual]);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  const change = (index: number, key: string, value: [number, number]) => {
    if (!draft) return;
    const next = {
      ...draft,
      profiles: draft.profiles.map((p, i) =>
        i === index ? { ...p, [key]: value } : p,
      ),
    };
    setDraft(next);
    setStatus("Изменения…");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        await api("/profiles", { method: "PUT", body: JSON.stringify(next) });
        setStatus("Сохранено · ракурсы пересчитаны");
        await refresh();
      } catch (e) {
        notify(String(e));
        setStatus("Ошибка сохранения");
      }
    }, 650);
  };
  const classify = (angles: Record<string, number>) =>
    draft?.profiles.find((p) =>
      (["yaw", "pitch", "roll"] as const).every(
        (k) => p[k][0] <= angles[k] && angles[k] <= p[k][1],
      ),
    )?.id;
  const overlaps = draft?.profiles.some((a, i) =>
    draft.profiles
      .slice(i + 1)
      .some((b) =>
        (["yaw", "pitch", "roll"] as const).every(
          (k) => Math.max(a[k][0], b[k][0]) < Math.min(a[k][1], b[k][1]),
        ),
      ),
  );
  return (
    <div className="node-card config-node">
      <NodeHead
        id={id}
        title="Пять ракурсов"
        subtitle="Диапазоны → профиль → набор метрик"
        icon={<Compass size={16} />}
        collapsed={data.collapsed}
      />
      {!data.collapsed && draft && (
        <div className="node-content nodrag nowheel">
          <p className="config-intro">
            Сторона — направление носа на изображении. Диапазоны сохраняются в{" "}
            <code>configs/pose_profiles.yaml</code>. Повторная реконструкция не
            нужна.
          </p>
          <div className="pose-range-list">
            {draft.profiles.map((p, i) => (
              <div className="pose-range-row" key={p.id}>
                <div className="pose-row-heading">
                  <span className={"pose-mini pose-" + p.id}>
                    <Compass size={15} />
                  </span>
                  <div>
                    <strong>{p.title}</strong>
                    <small>
                      {
                        photos.filter(
                          (photo) =>
                            photo.status === "ready" &&
                            classify(photo.angles) === p.id,
                        ).length
                      }{" "}
                      фото
                    </small>
                  </div>
                </div>
                <div className="pose-angle-controls">
                  {(["yaw", "pitch", "roll"] as const).map((k) => (
                    <RangePair
                      key={k}
                      label={k}
                      value={p[k]}
                      limit={k === "yaw" ? 100 : 90}
                      onChange={(value) => change(i, k, value)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
          {overlaps && (
            <div className="inline-warning">
              <AlertTriangle size={13} /> Диапазоны пересекаются. Приоритет —
              сверху вниз.
            </div>
          )}
          <div className="config-status">
            <Check size={12} /> {status}
            <span>версия {draft.version}</span>
          </div>
          <p className="micro muted">
            Вне всех диапазонов → «Вне профилей», метрики отключены. Ручные углы
            фото имеют приоритет над моделью.
          </p>
        </div>
      )}
    </div>
  );
});
function MetricEditor({ metric, pose }: { metric: Metric; pose: string }) {
  const c = metric.poses[pose];
  const [warn, setWarn] = useState(c?.thresholds.warn || 2),
    [alert, setAlert] = useState(c?.thresholds.alert || 3),
    [enabled, setEnabled] = useState(c?.enabled ?? true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const notify = useStore((s) => s.notify);
  useEffect(() => {
    setWarn(c?.thresholds.warn || 2);
    setAlert(c?.thresholds.alert || 3);
    setEnabled(c?.enabled ?? true);
  }, [c]);
  const save = (w: number, a: number, en: boolean) => {
    setWarn(w);
    setAlert(a);
    setEnabled(en);
    useStore.setState((s) => ({
      metrics: {
        ...s.metrics,
        catalog: s.metrics.catalog.map((m) =>
          m.id === metric.id
            ? {
                ...m,
                poses: {
                  ...m.poses,
                  [pose]: {
                    ...m.poses[pose],
                    enabled: en,
                    thresholds: { warn: w, alert: a },
                  },
                },
              }
            : m,
        ),
      },
    }));
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        await api("/metric-config", {
          method: "PUT",
          body: JSON.stringify({
            model: metric.model,
            pose,
            id: metric.id,
            enabled: en,
            thresholds: { warn: w, alert: a },
          }),
        });
        await useStore.getState().refreshMetrics();
      } catch (e) {
        notify(String(e));
      }
    }, 550);
  };
  return (
    <div className="metric-editor">
      <div className="flex between">
        <div>
          <strong>{metric.title}</strong>
          <small title={metric.source}>
            {metric.id} · {metric.unit}
          </small>
          {c?.archive_rank && (
            <small className="muted">
              Архивный ранг #{c.archive_rank} · AUC {c.cv_auc_mean?.toFixed(3)} · видимость опор {c.archive_visibility?.group3_fully_visible}/{c.archive_visibility?.group4_fully_visible}
            </small>
          )}
          {c?.quality_note && <small className="muted">{c.quality_note}</small>}
        </div>
        <Toggle
          checked={enabled}
          label={metric.title + " включена"}
          onChange={(v) => save(warn, alert, v)}
        />
      </div>
      <div className="threshold-grid">
        <Slider
          label="Предупреждение |z|"
          value={warn}
          min={0.5}
          max={6}
          step={0.1}
          onChange={(v) => save(v, Math.max(v, alert), enabled)}
        />
        <Slider
          label="Скачок |z|"
          value={alert}
          min={0.5}
          max={8}
          step={0.1}
          onChange={(v) => save(Math.min(warn, v), v, enabled)}
        />
      </div>
      <div className="metric-source">
        <FileCode2 size={11} />
        <code>{c?.config_file || metric.source}</code>
      </div>
    </div>
  );
}
export const RegistryNode = memo(function RegistryNode({
  id,
  data,
}: NodeProps<WorkNode>) {
  const table = useStore((s) => s.metrics),
    notify = useStore((s) => s.notify);
  const [model, setModel] = useState("3ddfa_v3"),
    [pose, setPose] = useState("frontal"),
    [query, setQuery] = useState(""),
    [busy, setBusy] = useState(false);
  const list = table.catalog.filter(
    (m) =>
      m.model === model &&
      (m.title + " " + m.id).toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <div className="node-card config-node">
      <NodeHead
        id={id}
        title="Метрики и пороги"
        subtitle={`${table.catalog.length} определений · файлы Python + YAML`}
        icon={<Activity size={16} />}
        collapsed={data.collapsed}
      />
      {!data.collapsed && (
        <div className="node-content nodrag nowheel">
          <div className="model-tabs">
            {[
              ["3ddfa_v3", "3DDFA_V3"],
              ["mediapipe", "MediaPipe"],
              ["fan", "FAN"],
              ["adaface", "AdaFace"],
            ].map(([v, t]) => (
              <button
                key={v}
                className={model === v ? "active" : ""}
                onClick={() => setModel(v)}
              >
                {t}
                {v !== "3ddfa_v3" && <span className="tiny-dot" />}
              </button>
            ))}
          </div>
          <div className="flex gap registry-toolbar">
            <select value={pose} onChange={(e) => setPose(e.target.value)}>
              {Object.entries(poseLabels)
                .filter(([id]) => id !== "unclassified")
                .map(([id, t]) => (
                  <option key={id} value={id}>
                    {t}
                  </option>
                ))}
            </select>
            <div className="search-wrap">
              <Search size={13} />
              <input
                placeholder="Поиск метрик"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <button
              className="secondary small"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await post("/metrics/reload");
                  await useStore.getState().refreshMetrics();
                  notify("Реестр перечитан с диска");
                } catch (e) {
                  notify(String(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              <RefreshCw size={12} /> Обновить
            </button>
          </div>
          {model !== "3ddfa_v3" && (
            <div className="inline-note">
              Модель ещё не установлена. Это готовые определения метрик, не
              рассчитанные значения.
            </div>
          )}
          <div className="metric-editor-list">
            {list.map((m) => (
              <MetricEditor key={model + pose + m.id} metric={m} pose={pose} />
            ))}
          </div>
          <p className="micro muted">
            Новая функция с @metric в metrics/ появляется после «Обновить». YAML
            переопределяет включение и пороги отдельно для каждого ракурса. Z
            считается только внутри группы и ракурса.
          </p>
          <div className="config-status">
            <Check size={12} /> Конфиг <code>{table.config_version}</code>
            <span>{list.length} метрики</span>
          </div>
        </div>
      )}
    </div>
  );
});
