import { useEffect, useMemo, useState } from "react";
import { loadGuideStatus, loadRun, loadRunEvents, startRun } from "./api";
import type { GuideStatus, GuideStep, RunEvent, RunRecord } from "./types";
import { uiLog } from "./logStore";

const terminal = new Set(["succeeded", "failed", "cancelled", "timed_out", "interrupted"]);
const PHASE_LABELS: Record<string, string> = { setup: "Настройка", validation: "Проверка", implementation: "Разработка", release: "Готовность" };
const DEVELOPMENT_CRITERIA: Record<string, string> = {
  "photo-index": "API возвращает реальные файлы с датой и pose hint; исходники не изменяются; ошибки дат явно отмечены; тесты проходят.",
  timeline: "Девять дорожек используют свежий Stage-1 pose, quality и реальные metric series; 1700+ фото виртуализированы; выбор точки открывает инспектор.",
  "pair-workbench": "Выбор A/B работает из хронологии; raw, correction, calibration noise и residual разделены; ограничения и альтернативные объяснения видимы.",
  "calibration-lab": "Семь лиц × девять pose bins, coverage, LOO, holdout и provenance отображаются; production thresholds не меняются автоматически.",
};

function StepIcon({ status, index }: { status: string; index: number }) {
  if (status === "complete") return <span className="guide-step-icon complete">✓</span>;
  if (status === "current") return <span className="guide-step-icon current">{index + 1}</span>;
  return <span className="guide-step-icon locked">⌁</span>;
}

function CurrentAction({ step, onRefresh, onRun }: { step: GuideStep; onRefresh: () => void; onRun: (runnerId: string) => void }) {
  return <section className="guide-action-card">
    <p className="eyebrow">СЕЙЧАС НУЖНО СДЕЛАТЬ</p>
    <h2>{step.title}</h2>
    <p>{step.purpose}</p>
    {step.blocking_reason && <div className="guide-reason"><b>Почему остановились</b><span>{step.blocking_reason}</span></div>}
    <div className="guide-instructions">
      <b>Ваше действие</b>
      {step.action === "refresh" && <ol><li>Проверьте указанный путь или подключение диска.</li><li>Нажмите кнопку проверки.</li><li>Не переходите дальше, пока шаг не станет зелёным.</li></ol>}
      {step.action === "run" && <ol><li>Нажмите запуск проверки.</li><li>Не закрывайте приложение во время выполнения.</li><li>При ошибке консоль откроется автоматически и покажет причину.</li></ol>}
      {step.action === "development" && <ol><li>Это не настройка параметра, а следующий участок разработки.</li><li>Сохраните сформированное ТЗ и передайте разработчику.</li><li>Шаг разблокируется только после API, тестов и живой проверки.</li></ol>}
    </div>
    {step.action === "refresh" && <button className="guide-primary" onClick={onRefresh}>{step.action_label ?? "Проверить"}</button>}
    {step.action === "run" && step.runner_id && <button className="guide-primary" onClick={() => onRun(step.runner_id!)}>{step.action_label}</button>}
    {step.action === "development" && <div className="development-spec"><b>Критерий завершения</b><span>{DEVELOPMENT_CRITERIA[step.id] ?? "Функция реализована, имеет объективный gate, regression tests и живую UI-проверку."}</span></div>}
  </section>;
}

export function GuidedSetup({ onGateChange }: { onGateChange?: (foundationComplete: boolean, analysisUnlocked: boolean) => void }) {
  const [status, setStatus] = useState<GuideStatus | null>(null);
  const [error, setError] = useState("");
  const [run, setRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setError("");
    try {
      const next = await loadGuideStatus();
      setStatus(next); onGateChange?.(next.foundation_complete, next.analysis_unlocked);
      uiLog("info", "guide", `Текущий шаг: ${next.current_step_id ?? "все завершено"}; выполнено ${next.completed}/${next.total}`);
    } catch (e) { const message = String(e); setError(message); uiLog("error", "guide", `Не удалось загрузить маршрут: ${message}`); }
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    if (!run || terminal.has(run.status)) {
      if (run?.status === "succeeded") void refresh();
      return;
    }
    let stopped = false;
    const tick = async () => {
      try {
        const next = await loadRun(run.id); if (stopped) return;
        setRun(next); const nextEvents = await loadRunEvents(run.id); setEvents(nextEvents);
        for (const event of nextEvents.slice(events.length)) {
          if (event.type === "log") uiLog("info", `run·${run.runner_id}`, String(event.payload.text ?? ""));
        }
        if (terminal.has(next.status)) uiLog(next.status === "succeeded" ? "info" : "error", "guide", `Проверка ${next.runner_id}: ${next.status}`);
      } catch (e) { if (!stopped) { setError(String(e)); uiLog("error", "guide", String(e)); } }
    };
    const id = window.setInterval(() => void tick(), 500); void tick();
    return () => { stopped = true; window.clearInterval(id); };
  }, [run?.id, run?.status, events.length]);

  async function launch(runnerId: string) {
    if (busy || (run && !terminal.has(run.status))) return;
    setBusy(true); setError(""); setEvents([]);
    uiLog("info", "guide", `Запуск обязательной проверки: ${runnerId}`);
    try { setRun(await startRun(runnerId, 0)); }
    catch (e) { setError(String(e)); uiLog("error", "guide", `Запуск не выполнен: ${String(e)}`); }
    finally { setBusy(false); }
  }

  const current = useMemo(() => status?.steps.find((x) => x.status === "current") ?? null, [status]);
  if (!status && !error) return <div className="guide-loading">Строим безопасный пошаговый маршрут…</div>;
  return <div className="guided-workspace">
    <header className="guide-header"><div><p className="eyebrow">ПОШАГОВЫЙ РЕЖИМ · ПАРАМЕТРЫ ЗАБЛОКИРОВАНЫ</p><h1>Мастер настройки и разработки</h1><p>Интерфейс показывает ровно одно следующее действие. Пропустить обязательный этап нельзя.</p></div>{status && <div className="guide-progress"><b>{status.completed}/{status.total}</b><span>обязательных шагов</span><i><em style={{ width: `${status.completed / status.total * 100}%` }} /></i></div>}</header>
    {error && <div className="guide-error"><b>Маршрут остановлен</b><span>{error}</span><button onClick={refresh}>Повторить</button></div>}
    {status && <div className="guide-layout"><section className="guide-roadmap">{status.steps.map((step, index) => <article className={`guide-step ${step.status}`} key={step.id}><StepIcon status={step.status} index={index} /><div><small>{PHASE_LABELS[step.phase] ?? step.phase}</small><b>{step.title}</b><p>{step.purpose}</p>{step.evidence && <span className="guide-evidence">{step.evidence}</span>}{step.status === "locked" && step.blocking_reason && <span className="guide-lock-reason">{step.blocking_reason}</span>}</div></article>)}</section><aside className="guide-current">{current ? <CurrentAction step={current} onRefresh={refresh} onRun={launch} /> : <section className="guide-action-card"><h2>Все шаги завершены</h2><p>Аналитическая рабочая станция разблокирована.</p></section>}{run && <section className={`guide-run status-${run.status}`}><div><b>{run.runner_id}</b><span>{run.status}</span></div><code>{run.id}</code><pre>{events.filter((e) => e.type === "log").slice(-12).map((e) => String(e.payload.text ?? "")).join("\n") || "Ожидаем вывод…"}</pre></section>}</aside></div>}
  </div>;
}
