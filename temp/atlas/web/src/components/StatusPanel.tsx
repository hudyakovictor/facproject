import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  LoaderCircle,
  RefreshCw,
  X,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import { api } from "../api";
import { useStore } from "../store";
import type { Job } from "../types";

// Порог «нет прогресса», после которого пишем, что задача могла зависнуть.
const STALL_SECONDS = 20;
// Два пропущенных опроса /api/health (по 6 с) — считаем, что API не отвечает.
const OFFLINE_SECONDS = 12;
const TICK = 1000;

const KINDS: Record<string, string> = {
  process: "Реконструкция",
  morph: "Морф-видео",
  register: "Регистрация",
  projection: "Проекция",
};
const STATUS_TEXT: Record<Job["status"], string> = {
  queued: "в очереди",
  running: "идёт",
  completed: "готово",
  cancelled: "отменено",
  failed: "ошибка",
};

type Tone = "ok" | "work" | "warn" | "error" | "idle";

function duration(n: number) {
  if (!isFinite(n) || n < 0) return "—";
  if (n < 0.1) return "< 0.1 с";
  if (n < 10) return `${n.toFixed(1)} с`;
  if (n < 60) return `${Math.round(n)} с`;
  const m = Math.floor(n / 60);
  return `${m} мин ${Math.round(n % 60)} с`;
}
function Row({
  label,
  tone,
  children,
}: {
  label: string;
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <div className="status-row">
      <span className="status-row-label">{label}</span>
      <span className={"status-row-value" + (tone ? " " + tone : "")}>
        {children}
      </span>
    </div>
  );
}

function JobLine({
  job,
  now,
  stall,
  onCancel,
}: {
  job: Job;
  now: number;
  stall: number;
  onCancel: () => void;
}) {
  const active = job.status === "running" || job.status === "queued";
  const elapsed =
    job.status === "running"
      ? now / 1000 - job.created
      : job.status === "queued"
        ? 0
        : (job.finished ?? job.created) - job.created;
  const Icon =
    job.status === "failed"
      ? XCircle
      : job.status === "cancelled"
        ? AlertTriangle
        : job.status === "completed"
          ? CheckCircle2
          : LoaderCircle;
  return (
    <div className={"status-job-line " + job.status}>
      <div className="status-job-top">
        <Icon
          size={12}
          className={
            job.status === "running"
              ? "spin"
              : job.status === "queued"
                ? "spin"
                : ""
          }
        />
        <b>{KINDS[job.kind] || job.kind}</b>
        <span className="status-job-status">{STATUS_TEXT[job.status]}</span>
        <span className="status-job-time">{duration(elapsed)}</span>
        {active && (
          <button
            className="icon-btn"
            title="Отменить задачу"
            onClick={onCancel}
          >
            <X size={12} />
          </button>
        )}
      </div>
      <div className="status-job-message">
        {job.message && job.message.toLowerCase() !== STATUS_TEXT[job.status]
          ? job.message
          : ""}
      </div>
      {active && (
        <div className="progress-track">
          <i
            className={job.progress > 0 ? "" : "indeterminate"}
            style={{ width: `${Math.round(job.progress * 100)}%` }}
          />
        </div>
      )}
      {job.status === "running" && stall > STALL_SECONDS && (
        <div className="status-job-stall">
          нет прогресса {duration(stall)} — задача могла зависнуть
        </div>
      )}
      {job.status === "completed" && job.result?.errors?.length > 0 && (
        <div className="status-job-stall">
          {job.result.errors.length} фото с ошибкой
        </div>
      )}
    </div>
  );
}

export function StatusPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const jobs = useStore((s) => s.jobs);
  const photos = useStore((s) => s.photos);
  const group = useStore((s) => s.group);
  const sse = useStore((s) => s.sse);
  const eventsAt = useStore((s) => s.eventsAt);
  const apiOk = useStore((s) => s.apiOk);
  const apiAt = useStore((s) => s.apiAt);
  const latency = useStore((s) => s.apiLatency);
  const health = useStore((s) => s.health);
  const refresh = useStore((s) => s.refresh);
  const notify = useStore((s) => s.notify);
  const [now, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const marks = useRef(new Map<string, { progress: number; at: number }>());

  // Тик для таймеров «прошло», «нет прогресса», «событие N с назад».
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), TICK);
    return () => clearInterval(t);
  }, []);

  // Пульс сервера: отличает «долгая задача» от «сервер не отвечает».
  // Ниже — только метки прогресса; пульс API и список задач ведёт App.
  // Метка времени последнего изменения прогресса каждой задачи.
  useEffect(() => {
    const map = marks.current;
    const seen = new Set<string>();
    for (const j of jobs) {
      seen.add(j.id);
      const prev = map.get(j.id);
      if (!prev || prev.progress !== j.progress) {
        map.set(j.id, { progress: j.progress, at: Date.now() });
      }
    }
    for (const id of [...map.keys()]) if (!seen.has(id)) map.delete(id);
  }, [jobs]);

  const active = jobs.filter(
    (j) => j.status === "running" || j.status === "queued",
  );
  const running = active.find((j) => j.status === "running");
  const queued = jobs.filter((j) => j.status === "queued");
  const finished = jobs
    .filter((j) => !["running", "queued"].includes(j.status))
    .slice(0, 5);
  const ready = photos.filter((p) => p.status === "ready");
  const pending = photos.filter((p) => p.status === "pending");
  const failedPhotos = photos.filter((p) => p.error);
  const stallOf = (j: Job) =>
    (now - (marks.current.get(j.id)?.at ?? now)) / 1000;
  const stalled = running ? stallOf(running) : 0;
  const pingAge = (now - apiAt) / 1000;
  const online = apiOk && pingAge < OFFLINE_SECONDS;
  const sseAge = eventsAt ? (now - eventsAt) / 1000 : null;

  let tone: Tone = "ok";
  let summary = "Готово · очередь пуста";
  if (apiAt === 0) {
    tone = "idle";
    summary = "Проверяем связь с сервером…";
  } else if (!online) {
    tone = "error";
    summary = "Сервер не отвечает";
  } else if (running && stalled > STALL_SECONDS) {
    tone = "warn";
    summary = `Похоже, зависло: ${Math.round(stalled)} с без прогресса`;
  } else if (running) {
    tone = "work";
    // Прогресс считается между фото, поэтому на одном кадре показываем
    // не «0%», а сколько эта фотография уже считается.
    summary = `${KINDS[running.kind] || running.kind} · ${
      running.progress > 0
        ? Math.round(running.progress * 100) + "%"
        : duration(now / 1000 - running.created)
    }`;
  } else if (queued.length) {
    tone = "work";
    summary = `В очереди ${queued.length}`;
  } else if (failedPhotos.length) {
    tone = "warn";
    summary = `${failedPhotos.length} фото с ошибкой`;
  }

  const reload = async () => {
    setBusy(true);
    try {
      const live = await api("/jobs");
      useStore.setState({ jobs: live });
      await refresh();
      notify("Статус обновлён");
    } catch (e) {
      notify(String(e));
    } finally {
      setBusy(false);
    }
  };

  const cancel = (id: string) => {
    fetch("/api/jobs/" + id + "/cancel", { method: "POST" })
      .then(() => notify("Отмена запрошена"))
      .catch((e) => notify(String(e)));
  };

  if (!open) return null;

  return (
    <div className="status-dock" role="dialog" aria-label="Статус системы">
      <div className={"status-dock-head " + tone}>
        <span className="status-pulse" />
        <div className="status-dock-title">
          <b>Статус</b>
          <small>{summary}</small>
        </div>
        <button
          className="icon-btn"
          title={collapsed ? "Развернуть" : "Свернуть"}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
        <button className="icon-btn" title="Закрыть" onClick={onClose}>
          <X size={14} />
        </button>
      </div>
      {!collapsed && (
        <div className="status-dock-body">
          <section>
            <h6>
              Связь
              {apiAt > 0 && !online && (
                <span className="status-badge error">нет</span>
              )}
            </h6>
            <Row label="SSE" tone={sse === "open" ? "ok" : "warn"}>
              {sse === "open"
                ? "подключено"
                : sse === "closed"
                  ? "переподключение"
                  : "подключение"}
            </Row>
            <Row
              label="Обновления"
              tone={
                active.length > 0 &&
                (sseAge === null || sseAge > OFFLINE_SECONDS)
                  ? "warn"
                  : undefined
              }
            >
              {sseAge === null
                ? "ещё не было"
                : sseAge < 2
                  ? "только что"
                  : `${duration(sseAge)} назад`}
            </Row>
            <Row
              label="API"
              tone={apiAt === 0 ? undefined : online ? "ok" : "error"}
            >
              {apiAt === 0
                ? "проверка…"
                : online
                  ? `отвечает · ${latency ?? "—"} мс`
                  : `молчит ${Math.round(pingAge)} с`}
            </Row>
          </section>

          <section>
            <h6>
              Задачи
              {active.length > 0 && (
                <span className="status-badge work">{active.length}</span>
              )}
            </h6>
            {active.length === 0 && (
              <p className="status-empty">Нет запущенных задач</p>
            )}
            {active.map((j) => (
              <JobLine
                key={j.id}
                job={j}
                now={now}
                stall={stallOf(j)}
                onCancel={() => cancel(j.id)}
              />
            ))}
          </section>

          {finished.length > 0 && (
            <section>
              <h6>Последние</h6>
              {finished.map((j) => (
                <JobLine
                  key={j.id}
                  job={j}
                  now={now}
                  stall={0}
                  onCancel={() => {}}
                />
              ))}
            </section>
          )}

          <section>
            <h6>Библиотека</h6>
            <Row label="Группа">
              {group === "__all" ? "все группы" : group || "—"}
            </Row>
            <Row label="Фото">{photos.length}</Row>
            <Row label="Готовы" tone="ok">
              {ready.length}
            </Row>
            <Row label="В ожидании" tone={pending.length ? "warn" : undefined}>
              {pending.length}
            </Row>
            <Row
              label="С ошибкой"
              tone={failedPhotos.length ? "error" : undefined}
            >
              {failedPhotos.length}
            </Row>
          </section>

          <section>
            <h6>Сервер</h6>
            <Row label="Версия">{health?.version || "—"}</Row>
            <Row label="Потоки CPU">
              {health ? `${health.cpu} · рабочий 1` : "—"}
            </Row>
            <Row label="FFmpeg" tone={health?.ffmpeg ? "ok" : "warn"}>
              {health ? (health.ffmpeg ? "есть" : "нет") : "—"}
            </Row>
            <Row
              label="MediaPipe"
              tone={health?.mediapipe?.available ? "ok" : undefined}
            >
              {health ? (health.mediapipe?.available ? "есть" : "нет") : "—"}
            </Row>
          </section>

          <div className="status-dock-foot">
            <button className="subtle-button" onClick={reload} disabled={busy}>
              <RefreshCw size={12} className={busy ? "spin" : ""} /> Обновить
            </button>
            {active.length > 0 && (
              <button
                className="subtle-button danger"
                onClick={() => active.forEach((j) => cancel(j.id))}
              >
                <X size={12} /> Отменить все
              </button>
            )}
            <span className="muted">журнал · {jobs.length}</span>
          </div>
        </div>
      )}
    </div>
  );
}
