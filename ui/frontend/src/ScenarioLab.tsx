import { useEffect, useMemo, useState } from "react";
import { createMaximumScenarioPlan, loadMaximumScenarioResults, loadScenarioPlan, loadScenarios } from "./api";
import type { Scenario, ScenarioMaximumPlan, ScenarioMaximumResults, ScenarioPlan, ScenarioResultGroup } from "./types";
import { uiLog } from "./logStore";

const STATE_COPY = {
  passed: { icon: "✓", title: "ВСЕ ПРОШЛО", text: "Все ожидаемые случаи имеют успешный check_result.json." },
  failed: { icon: "×", title: "ЕСТЬ ОШИБКИ", text: "Хотя бы один сценарный случай завершился ошибкой." },
  incomplete: { icon: "!", title: "ПРОВЕРКА НЕ ЗАВЕРШЕНА", text: "Часть случаев прошла, но полного покрытия ещё нет." },
  not_run: { icon: "○", title: "ЕЩЁ НЕ ЗАПУСКАЛОСЬ", text: "План можно создать, но это не означает успешное прохождение." },
} as const;

function ResultBadge({ state, compact = false }: { state: keyof typeof STATE_COPY; compact?: boolean }) {
  const copy = STATE_COPY[state];
  return <span className={`scenario-state state-${state} ${compact ? "compact" : ""}`}><i>{copy.icon}</i><b>{copy.title}</b>{!compact && <small>{copy.text}</small>}</span>;
}

export function ScenarioLab() {
  const [items, setItems] = useState<Scenario[]>([]);
  const [id, setId] = useState("S01_stability_frontal_A");
  const [pose, setPose] = useState("frontal");
  const [count, setCount] = useState(1);
  const [plan, setPlan] = useState<ScenarioPlan | null>(null);
  const [maximumPlan, setMaximumPlan] = useState<ScenarioMaximumPlan | null>(null);
  const [results, setResults] = useState<ScenarioMaximumResults | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);

  async function refreshResults() {
    try {
      const next = await loadMaximumScenarioResults(); setResults(next);
      uiLog(next.overall_state === "failed" ? "error" : next.overall_state === "passed" ? "info" : "warning", "scenarios", `MAXIMUM status=${next.overall_state}; passed=${next.passed}; failed=${next.failed}; not_run=${next.not_run}`);
    } catch (e) { setError(String(e)); uiLog("error", "scenarios", `Результаты недоступны: ${String(e)}`); }
  }

  useEffect(() => {
    Promise.all([loadScenarios(), loadMaximumScenarioResults()]).then(([scenarios, status]) => {
      setItems(scenarios); setResults(status);
      uiLog("info", "scenarios", `Загружено ${scenarios.length} типов сценариев; MAXIMUM=${status.overall_state}`);
    }).catch((e) => { setError(String(e)); uiLog("error", "scenarios", String(e)); });
  }, []);

  async function buildSingle() {
    if (busy) return; setError(""); setBusy(true); setPlan(null);
    try { const next = await loadScenarioPlan(id, pose, count); setPlan(next); uiLog("info", "scenarios", `План создан: ${id}, cases=${next.case_count}. Это ещё не PASS.`); }
    catch (e) { setError(String(e)); uiLog("error", "scenarios", String(e)); }
    finally { setBusy(false); }
  }

  async function buildMaximum() {
    if (busy) return; setError(""); setBusy(true); setMaximumPlan(null);
    try { const next = await createMaximumScenarioPlan(); setMaximumPlan(next); uiLog("info", "scenarios", `MAXIMUM план сохранён: ${next.scenario_count}×${next.pose_count}×${next.combination_count}=${next.case_count}. План не считается прохождением.`); await refreshResults(); }
    catch (e) { setError(String(e)); uiLog("error", "scenarios", String(e)); }
    finally { setBusy(false); }
  }

  const groups = useMemo(() => new Map((results?.groups ?? []).map((x) => [x.scenario_id, x])), [results]);
  const visibleItems = showAll ? items : items.slice(0, 6);
  const overall = results?.overall_state ?? "not_run";

  return <section className="scenario-lab-v2">
    <header className="scenario-head"><div><p className="eyebrow">SCIENTIFIC VALIDATION CORE</p><h2>Сценарии проверки</h2><p>Создание плана и успешное прохождение теперь показаны раздельно.</p></div><button className="scenario-refresh" onClick={refreshResults} disabled={busy}>↻ Обновить результат</button></header>

    <div className="scenario-overall"><ResultBadge state={overall} /><div className="scenario-numbers"><span><b>{results?.passed ?? 0}</b> прошли</span><span><b>{results?.failed ?? 0}</b> упали</span><span><b>{results?.not_run ?? 1323}</b> не запускались</span><span><b>{results?.expected_total ?? 1323}</b> всего</span></div></div>

    <div className="scenario-max-card"><div><span className="max-label">MAXIMUM</span><h3>Все виды · все 9 ракурсов · все 7 комбинаций</h3><p>21 тип × 9 pose bins × 7 комбинаций людей = <b>1323 тестовых случая</b>.</p><small>Кнопка создаёт и сохраняет безопасный план в control plane. Она не изменяет app6 и не выдаёт план за пройденный тест.</small></div><button onClick={buildMaximum} disabled={busy}>{busy ? "Создаём…" : "Создать максимум · 1323"}</button></div>

    {maximumPlan && <div className="plan-created"><i>✓</i><div><b>МАКСИМАЛЬНЫЙ ПЛАН СОЗДАН</b><span>{maximumPlan.case_count} случаев · {maximumPlan.scenario_count} видов · сохранено в control plane</span><strong>ЭТО НЕ PASS — результаты появятся только после фактического запуска и check_result.json.</strong></div></div>}
    {error && <div className="scenario-error-v2"><b>ОШИБКА</b><span>{error}</span></div>}

    <div className="scenario-grid">
      <section className="scenario-types"><header><h3>Состояние 21 вида</h3><button onClick={() => setShowAll((x) => !x)}>{showAll ? "Свернуть" : "Показать все 21"}</button></header>{visibleItems.map((scenario) => <ScenarioRow key={scenario.id} scenario={scenario} result={groups.get(scenario.id)} />)}</section>
      <section className="scenario-builder"><h3>Один выборочный план</h3><p>Используйте только для быстрой точечной проверки. Для полного покрытия нажмите MAXIMUM выше.</p><label>Вид сценария<select value={id} onChange={(e) => setId(e.target.value)}>{items.map((x) => <option key={x.id} value={x.id}>{x.id} — {x.description}</option>)}</select></label><div className="scenario-builder-row"><label>Ракурсы<select value={pose} onChange={(e) => setPose(e.target.value)}><option value="frontal">Только frontal</option><option value="all">Все 9</option>{[1,2,3,4,5,6,7,8,9].map((x) => <option value={String(x)} key={x}>Pose {x}</option>)}</select></label><label>Комбинации<select value={count} onChange={(e) => setCount(Number(e.target.value))}>{[1,3,7].map((x) => <option value={x} key={x}>{x}</option>)}</select></label></div><button className="scenario-build-one" disabled={busy} onClick={buildSingle}>Создать выборочный план</button>{plan && <div className="single-plan-result"><b>ПЛАН ГОТОВ</b><span>{plan.case_count} случаев · {plan.poses.map((x) => x.pose_bin).join(" · ")}</span><strong>Не запускался · PASS/FAIL пока отсутствует</strong></div>}</section>
    </div>

    {results && results.failed_cases.length > 0 && <details className="scenario-failures"><summary>Показать упавшие случаи ({results.failed})</summary>{results.failed_cases.map((x) => <div key={x.scenario_id}><b>{x.scenario_id}</b><span>{x.failed_checks.join(", ") || "причина не записана"}</span><code>{x.path}</code></div>)}</details>}
    <p className="scenario-boundary">Synthetic и curated scenarios проверяют контракты и регрессии. Даже полный PASS не является доказательством личности или forensic accuracy.</p>
  </section>;
}

function ScenarioRow({ scenario, result }: { scenario: Scenario; result?: ScenarioResultGroup }) {
  const state = result?.state ?? "not_run";
  return <article className={`scenario-row state-${state}`}><ResultBadge state={state} compact /><div><b>{scenario.id}</b><p>{scenario.description}</p><small>{scenario.block} · {scenario.priority} · {scenario.frame_count} кадров</small></div><dl><span><b>{result?.passed ?? 0}</b>/63</span><small>успешно</small></dl></article>;
}
