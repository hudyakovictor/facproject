import { memo, useEffect, useRef, useState } from "react";
import { type NodeProps } from "@xyflow/react";
import {
  Eye,
  ScanEye,
  Check,
  RefreshCw,
  AlertTriangle,
  Download,
} from "lucide-react";
import { useStore, type WorkNode } from "../store";
import { api, post } from "../api";
import { NodeHead, JobProgress } from "./ui";
function EyeView({
  data,
  eye,
  onChange,
}: {
  data: any;
  eye: any;
  onChange: (r: any) => void;
}) {
  const drag = useRef<number | null>(null),
    svg = useRef<SVGSVGElement>(null),
    [pts, setPts] = useState(data.points);
  useEffect(() => setPts(data.points), [data]);
  const handles = [
      eye.outer,
      eye.inner,
      eye.top,
      eye.bottom,
      ...eye.ring,
      eye.iris,
    ],
    a = pts[eye.ring[0]],
    b = pts[eye.ring[2]],
    c = pts[eye.iris],
    d = Math.hypot(a[0] - b[0], a[1] - b[1]),
    mesh = eye.mesh_aperture as
      | {
          points: number[][];
          width_px: number;
          height_px: number;
          area_px2: number;
        }
      | undefined;
  return (
    <div className="eye-view">
      <div>
        <b>{eye.label}</b>
        <span>
          {`MediaPipe ${eye.width_px.toFixed(0)} px · D/H ${eye.iris_height_ratio.toFixed(3)}`}
          {mesh
            ? ` · 3DDFA ${mesh.width_px.toFixed(0)} px · D/H ${(
                eye.mesh_iris_height_ratio ?? 0
              ).toFixed(3)}`
            : " · 3DDFA нет"}
        </span>
      </div>
      <svg
        ref={svg}
        viewBox={eye.bounds.join(" ")}
        onPointerMove={(e) => {
          if (drag.current === null || !svg.current) return;
          const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(
            svg.current.getScreenCTM()!.inverse(),
          );
          const next = pts.map((q: any, i: number) =>
            i === drag.current
              ? [
                  Math.max(0, Math.min(data.width, p.x)),
                  Math.max(0, Math.min(data.height, p.y)),
                ]
              : q,
          );
          setPts(next);
        }}
        onPointerUp={async (e) => {
          if (drag.current !== null) {
            const index = drag.current;
            drag.current = null;
            const r = await api("/photos/" + data.id + "/eye-annotations", {
              method: "PATCH",
              body: JSON.stringify({ points: { [index]: pts[index] } }),
            });
            onChange(r);
          }
        }}
      >
        <image
          href={data.source}
          x={0}
          y={0}
          width={data.width}
          height={data.height}
        />
        <polygon
          points={eye.contour.map((i: number) => pts[i].join(",")).join(" ")}
          fill="none"
          stroke="#60edca"
          strokeWidth={eye.width_px * 0.008}
        >
          <title>
            {`Контур MediaPipe · ${eye.width_px.toFixed(0)}×${eye.height_px.toFixed(
              0,
            )} px`}
          </title>
        </polygon>
        {mesh && (
          <>
            {/* Та же щель по версии 3DDFA_V3: шесть точек ldm68, спроецированных
                на фото. Рисуется пунктиром поверх, чтобы видно было расхождение. */}
            <polygon
              points={mesh.points.map((q) => q.join(",")).join(" ")}
              fill="rgba(195,154,250,0.10)"
              stroke="#c39afa"
              strokeWidth={eye.width_px * 0.007}
              strokeDasharray={`${eye.width_px * 0.03} ${eye.width_px * 0.02}`}
            >
              <title>
                {`Контур 3DDFA_V3 · ${mesh.width_px.toFixed(0)}×${mesh.height_px.toFixed(
                  0,
                )} px · площадь ${mesh.area_px2.toFixed(0)} px²`}
              </title>
            </polygon>
            {mesh.points.map((q, i) => (
              <circle
                key={`m${i}`}
                cx={q[0]}
                cy={q[1]}
                r={eye.width_px * 0.014}
                fill="#c39afa"
                stroke="#10222b"
                strokeWidth={eye.width_px * 0.004}
              >
                <title>{`3DDFA ldm68 · точка ${i}`}</title>
              </circle>
            ))}
          </>
        )}
        <circle
          cx={c[0]}
          cy={c[1]}
          r={d / 2}
          fill="none"
          stroke="#ffc76e"
          strokeWidth={eye.width_px * 0.009}
        />
        {handles.map((i: number) => (
          <circle
            key={i}
            cx={pts[i][0]}
            cy={pts[i][1]}
            r={eye.width_px * 0.024}
            fill={i === eye.iris ? "#ffc76e" : "#55ebd0"}
            stroke="#10222b"
            strokeWidth={eye.width_px * 0.006}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId);
              drag.current = i;
              e.stopPropagation();
            }}
          >
            <title>{i} · перетащите для исправления</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}
export const EyesNode = memo(function EyesNode({
  id,
  data,
}: NodeProps<WorkNode>) {
  const active = useStore((s) => s.activeId),
    photos = useStore((s) => s.photos),
    group = useStore((s) => s.group),
    jobs = useStore((s) => s.jobs),
    notify = useStore((s) => s.notify),
    set = useStore((s) => s.set),
    refreshMetrics = useStore((s) => s.refreshMetrics);
  const [result, setResult] = useState<any>(null),
    [report, setReport] = useState<any>(null),
    [cohort, setCohort] = useState(""),
    [angles, setAngles] = useState({ yaw: 0, pitch: 0, roll: 0 }),
    [gaze, setGaze] = useState<"unknown" | "straight" | "not-straight">(
      "unknown",
    ),
    [error, setError] = useState(""),
    [tab, setTab] = useState("eye");
  const job = jobs.find((j) => j.kind === "eyes");
  useEffect(() => {
    let stale = false;
    setError("");
    setResult(null);
    if (active)
      api("/photos/" + active + "/eyes")
        .then((r) => {
          if (!stale && r.status !== "pending") {
            setResult(r);
            setCohort(r.cohort || "");
            setAngles(r.angles);
            setGaze(
              r.gaze_ok === true
                ? "straight"
                : r.gaze_ok === false
                  ? "not-straight"
                  : "unknown",
            );
          }
        })
        .catch(() => {});
    api("/eyes/report?group=" + encodeURIComponent(group))
      .then((r) => !stale && setReport(r))
      .catch(() => {});
    return () => {
      stale = true;
    };
  }, [active, group, job?.status, job?.progress]);
  const run = async (all = false) => {
    try {
      await post("/eyes/analyze", {
        photo_ids: all
          ? photos
              .filter(
                (p) => (group === "__all" || p.group === group) && !p.demo,
              )
              .map((p) => p.id)
          : [active],
      });
      setError("");
    } catch (e) {
      setError(String(e));
    }
  };
  return (
    <div className="node-card eyes-node">
      <NodeHead
        id={id}
        title="Глаза · исходные пиксели"
        subtitle="20 относительных метрик · не детектор накладок"
        icon={<Eye size={15} />}
        collapsed={data.collapsed}
      />
      {!data.collapsed && (
        <div className="node-content nodrag nowheel">
          <div className="eye-toolbar">
            <button
              className={tab === "eye" ? "active" : ""}
              onClick={() => setTab("eye")}
            >
              Кадр
            </button>
            <button
              className={tab === "selection" ? "active" : ""}
              onClick={() => setTab("selection")}
            >
              Выборка <small>{report?.selected?.length || 0}</small>
            </button>
            <button
              className={tab === "metrics" ? "active" : ""}
              onClick={() => setTab("metrics")}
            >
              20 метрик
            </button>
            <button
              className="primary small"
              disabled={
                !active || ["queued", "running"].includes(job?.status || "")
              }
              onClick={() => run(true)}
            >
              <ScanEye size={13} />
              Рассчитать группу
            </button>
          </div>
          {error && <div className="warning">{error}</div>}
          {job && ["queued", "running", "failed"].includes(job.status) && (
            <JobProgress job={job} />
          )}
          {tab === "eye" &&
            (!result ? (
              <div className="eye-empty">
                <ScanEye size={25} />
                <b>Разметка радужек и век</b>
                <p>
                  На оригинале, не на 224×224 и не по альбедо. Автоматические
                  точки можно исправить мышью.
                </p>
                <button onClick={() => run(false)} disabled={!active}>
                  Измерить текущий кадр
                </button>
              </div>
            ) : (
              <>
                <div
                  className={
                    "quality-banner " +
                    ((result.quality_flags || []).length ? "review" : "ok")
                  }
                >
                  <span>
                    {(result.quality_flags || []).length
                      ? "Признаки качества · кадр всё равно в выборке"
                      : "Признаков нет"}
                  </span>
                  <small>
                    {result.reviewed
                      ? "Разметка просмотрена"
                      : "Автооценка · нужна проверка"}
                  </small>
                </div>
                <div className="ocular-annotation">
                  <label>
                    Сравнительная группа (например A/B/C; подписи задаёте вы)
                    <input
                      value={cohort}
                      maxLength={80}
                      placeholder="Не назначена · можно оставить пустым"
                      onChange={(e) => setCohort(e.target.value)}
                      onBlur={async () => {
                        if (cohort !== (result.cohort || "")) {
                          await api("/photos/" + active, {
                            method: "PATCH",
                            body: JSON.stringify({ cohort }),
                          });
                          setResult(await api("/photos/" + active + "/eyes"));
                        }
                      }}
                    />
                  </label>
                  <div className="angle-correction">
                    {(["yaw", "pitch", "roll"] as const).map((k) => (
                      <label key={k}>
                        {k}
                        <input
                          aria-label={"Угол головы " + k}
                          type="number"
                          min={-90}
                          max={90}
                          step={0.1}
                          value={angles?.[k] ?? 0}
                          onChange={(e) =>
                            setAngles({ ...angles, [k]: +e.target.value })
                          }
                        />
                      </label>
                    ))}
                    <button
                      title="Сохранить ручные углы"
                      onClick={async () => {
                        await api("/photos/" + active + "/eye-annotations", {
                          method: "PATCH",
                          body: JSON.stringify({ head_angles: angles }),
                        });
                        setResult(await api("/photos/" + active + "/eyes"));
                      }}
                    >
                      Углы
                    </button>
                  </div>
                  <div className="gaze-control">
                    <span>Взгляд в камеру · проверка оператором</span>
                    <select
                      value={gaze}
                      onChange={async (e) => {
                        const v = e.target.value as typeof gaze;
                        setGaze(v);
                        await api("/photos/" + active + "/eye-annotations", {
                          method: "PATCH",
                          body: JSON.stringify({
                            gaze_ok: v === "unknown" ? null : v === "straight",
                          }),
                        });
                        setResult(await api("/photos/" + active + "/eyes"));
                      }}
                    >
                      <option value="unknown">Не проверен</option>
                      <option value="straight">Да · проверено</option>
                      <option value="not-straight">Нет · исключить</option>
                    </select>
                  </div>
                </div>
                <div className="eye-pair">
                  {result.eyes.map((eye: any) => (
                    <EyeView
                      key={eye.side}
                      data={result}
                      eye={eye}
                      onChange={(r) => {
                        setResult(r);
                        refreshMetrics();
                      }}
                    />
                  ))}
                </div>
                <p className="micro muted">
                  Бирюзовый контур — MediaPipe (16 точек), пунктирный лиловый —
                  3DDFA_V3 (шесть точек ldm68, спроецированных на фото). Точки
                  MediaPipe перетаскиваются. Масштаб — исходные пиксели; 1 px
                  ошибки заметно влияет на узкую щель.
                </p>
                <div className="eye-ratios">
                  {result.eyes.map((e: any) => (
                    <div key={e.side}>
                      <small>{e.label}</small>
                      <b>D / ширина {e.iris_width_ratio.toFixed(3)}</b>
                      <b>D / высота {e.iris_height_ratio.toFixed(3)}</b>
                      {e.mesh_aperture && (
                        <b className="mesh">
                          3DDFA D / высота{" "}
                          {(e.mesh_iris_height_ratio ?? 0).toFixed(3)} · щель{" "}
                          {e.mesh_aperture.width_px.toFixed(0)}×
                          {e.mesh_aperture.height_px.toFixed(0)} px
                        </b>
                      )}
                    </div>
                  ))}
                </div>
                <p className="eye-caution">
                  D / высота &gt; 1 само по себе нормально: часть радужки
                  закрыта веками. На кадрах с масками, закреплёнными за веко,
                  прорезь сужена намеренно — расхождение двух контуров и есть
                  предмет сравнения, а не ошибка разметки.
                </p>
                {result.quality_flags?.length > 0 && (
                  <>
                    <div className="flags-title">
                      Признаки (ничего не исключается)
                    </div>
                    <ul className="quality-reasons">
                      {result.quality_flags.map((r: string) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                  </>
                )}
                <button
                  className="text-button"
                  onClick={async () => {
                    setResult(
                      await api("/photos/" + active + "/eye-annotations", {
                        method: "PATCH",
                        body: JSON.stringify({ reviewed: !result.reviewed }),
                      }),
                    );
                    refreshMetrics();
                  }}
                >
                  <Check size={12} />
                  {result.reviewed
                    ? "Снять отметку проверки"
                    : "Разметка проверена вручную"}
                </button>
              </>
            ))}
          {tab === "selection" && (
            <div className="frontal-selection">
              <p className="micro">{report?.selection}</p>
              <div className="selection-count">
                {report?.selected?.length || 0} / {report?.rows?.length || 0}
                <span>
                  кадров с измерениями · отбора нет, признаки ничего не
                  исключают
                </span>
              </div>
              {report?.rows?.map((r: any) => (
                <button
                  key={r.id}
                  onClick={() => {
                    useStore.getState().selectPhoto(r.id);
                    setTab("eye");
                  }}
                  className={
                    (r.quality_flags || []).length ? "flagged" : "passed"
                  }
                >
                  <img src={"/api/photos/" + r.id + "/thumbnail"} />
                  <span>
                    <b>{r.name}</b>
                    <small>{`№${r.best_view_rank} · score ${r.frontal_score.toFixed(2)} · ${(r.quality_flags || [])[0] || "признаков нет"}`}</small>
                  </span>
                </button>
              ))}
              <p className="micro muted">
                Для группового сравнения нужны заданные пользователем группы, ≥5
                независимых дат в каждой и проверка разметки. α_id не
                устанавливает личность.
              </p>
              <a
                className="text-button"
                href={"/api/eyes/report.csv?group=" + encodeURIComponent(group)}
              >
                <Download size={12} />
                CSV с причинами отбора
              </a>
            </div>
          )}
          {tab === "metrics" && (
            <div className="ocular-metrics">
              {(result?.catalog || report?.catalog || []).map((m: any) => (
                <div key={m.id}>
                  <span title={m.description}>
                    {m.title}
                    <small>{m.description}</small>
                  </span>
                  <b>
                    {result?.metrics?.[m.id]?.toFixed(
                      m.unit === "deg" ? 1 : 3,
                    ) ?? "—"}
                    {m.unit === "deg" ? "°" : ""}
                  </b>
                </div>
              ))}
              <p className="micro muted">
                Проекции мягких тканей, не геометрия черепа. Нет нормативного
                «порога маски»; отклонения требуют контроля ракурса, взгляда,
                мимики и камеры.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
