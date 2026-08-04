import { useEffect, useMemo, useState } from "react";
import {
  activateDataset,
  cancelJob,
  clearExtractedData,
  fetchAnalysisRun,
  fetchAnalysisRunPairs,
  fetchAnalysisRuns,
  fetchDatasetInventory,
  fetchDatasetIssues,
  listJobs,
  submitExtractJob,
  type AnalysisRunPairsResponse,
  type AnalysisRunSummary,
  type DatasetInventory,
  type DatasetIssueReport,
  type JobRow,
} from "../../shared/api";

type Mode = "limited" | "full" | "per_year";
const DEFAULT_INPUT = "/Volumes/SDCARD/photo/main";
const POSE_ORDER = [
  "left_profile", "left_deep", "left_mid", "left_light", "frontal",
  "right_light", "right_mid", "right_deep", "right_profile",
] as const;

function formatCell(value: unknown): string {
  if (value === undefined || value === null || value === "") return "—";
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(value >= 1 ? 4 : 6).replace(/0+$/, "").replace(/\.$/, "");
  }
  return String(value);
}

export default function DataManager() {
  const [mode, setMode] = useState<Mode>("limited");
  const [limit, setLimit] = useState(100);
  const [inputDir, setInputDir] = useState(() => localStorage.getItem("deeputin.input_dir") || DEFAULT_INPUT);
  const [device, setDevice] = useState("auto");
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [confirmClear, setConfirmClear] = useState("");
  const [inventory, setInventory] = useState<DatasetInventory | null>(null);
  const [issuesOpen, setIssuesOpen] = useState(false);
  const [issueCategory, setIssueCategory] = useState("");
  const [issueOffset, setIssueOffset] = useState(0);
  const [issueReport, setIssueReport] = useState<DatasetIssueReport | null>(null);
  const [analysisRuns, setAnalysisRuns] = useState<AnalysisRunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<AnalysisRunSummary | null>(null);
  const [runPairs, setRunPairs] = useState<AnalysisRunPairsResponse | null>(null);
  const [pairsOffset, setPairsOffset] = useState(0);
  const [pairsLoading, setPairsLoading] = useState(false);
  const [runFilter, setRunFilter] = useState("");
  const running = useMemo(() => jobs.some(j => j.status === "queued" || j.status === "running"), [jobs]);

  const refresh = async () => {
    try { setJobs(await listJobs()); } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
  };
  const loadInventory = async () => {
    try {
      setInventory(await fetchDatasetInventory());
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
      setInventory(null);
    }
  };
  const loadIssues = async (offset = issueOffset, category = issueCategory) => {
    try {
      setIssueReport(await fetchDatasetIssues({ offset, limit: 100, category: category || undefined }));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => { void refresh(); void loadInventory(); void loadAnalysisRuns(); }, []);
  useEffect(() => {
    const id = window.setInterval(() => { void refresh(); void loadAnalysisRuns(); }, running ? 1500 : 5000);
    return () => clearInterval(id);
  }, [running]);
  useEffect(() => {
    if (issuesOpen) void loadIssues(issueOffset, issueCategory);
  }, [issuesOpen, issueOffset, issueCategory]);
  useEffect(() => {
    if (selectedRun?.run_id && selectedRun.has_stage2) {
      void loadAnalysisRunPairs(selectedRun.run_id);
    } else {
      setRunPairs(null);
    }
  }, [selectedRun, pairsOffset]);

  const run = async () => {
    setBusy(true); setMessage(""); localStorage.setItem("deeputin.input_dir", inputDir);
    try {
      const payload: Record<string, unknown> = { input_dir: inputDir, device };
      if (mode === "limited") payload.limit = Math.max(1, Math.floor(limit));
      if (mode === "per_year") { payload.sampling_mode = "per_year"; payload.per_year = 5; }
      const id = await submitExtractJob(payload);
      setMessage(`Задание ${id} поставлено в очередь`); await refresh();
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const clear = async () => {
    if (confirmClear !== "ОЧИСТИТЬ") return;
    setBusy(true); setMessage("");
    try {
      const r = await clearExtractedData();
      setMessage(`${r.note || "Данные очищены"}${r.removed?.length ? ` · удалено: ${r.removed.length}` : ""}`);
      setConfirmClear(""); await refresh(); await loadInventory();
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const activate = async () => {
    setBusy(true); setMessage("");
    try {
      const result = await activateDataset({ label: "active-stage1" });
      setMessage(`Dataset активирован · ${result.path}`);
      await loadInventory();
    } catch (e) { setMessage(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const stage1 = inventory?.stage1;
  const calibration = inventory?.calibration;
  const yearEntries = Object.entries(stage1?.year_counts || {}) as Array<[string, number]>;
  const maxYear = Math.max(1, ...yearEntries.map(([, count]) => Number(count) || 0));
  const poseCounts = stage1?.pose_counts || {} as Record<string, number>;
  const issueTotal = Object.values(stage1?.issue_counts || {}).reduce((sum: number, value) => sum + Number(value || 0), 0);

  const loadAnalysisRuns = async () => {
    try {
      const data = await fetchAnalysisRuns({ limit: 50 });
      setAnalysisRuns(data.runs || []);
    } catch (error) {
      setMessage((current) => current || (error instanceof Error ? error.message : String(error)));
    }
  };

  const loadAnalysisRunPairs = async (runId: string) => {
    setPairsLoading(true);
    try {
      const next = await fetchAnalysisRunPairs(runId, { offset: pairsOffset, limit: 25 });
      setRunPairs(next);
    } catch (error) {
      setRunPairs(null);
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setPairsLoading(false);
    }
  };

  const openRunDetail = async (runId: string) => {
    try {
      const detail = await fetchAnalysisRun(runId);
      setSelectedRun(detail);
      setPairsOffset(0);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  };

  const filteredRuns = useMemo(() => {
    const needle = runFilter.trim().toLowerCase();
    if (!needle) return analysisRuns;
    return analysisRuns.filter((item) =>
      item.run_id.toLowerCase().includes(needle) ||
      (item.profile_id || "").toLowerCase().includes(needle),
    );
  }, [analysisRuns, runFilter]);

  return <div className="page-shell manager-page">
    <div className="page-heading">
      <div>
        <small>PIPELINE CONTROL</small>
        <h1>Data Manager</h1>
        <p>Подключение готового Stage 1 и калибровки. Исходные артефакты анализируются только для чтения.</p>
      </div>
      <button className="ghost" onClick={() => { void refresh(); void loadInventory(); }}>↻ Проверить данные</button>
    </div>
    {message && <div className="notice wide">{message}</div>}

    <section className="card dataset-card">
      <header>
        <span>00</span>
        <div><b>Готовый Stage 1 и calibration</b><small>Read-only inventory · без повторного извлечения</small></div>
        <em className={`dataset-overall ${inventory?.status || "blocked"}`}>{(inventory?.status || "…").toUpperCase()}</em>
      </header>
      <div className="dataset-paths">
        <div><span>STAGE 1</span><code title={stage1?.root}>{stage1?.root || "—"}</code></div>
        <div><span>CALIBRATION</span><code title={calibration?.root}>{calibration?.root || "—"}</code></div>
      </div>
      <div className="dataset-stats">
        <div><strong>{stage1?.record_count ?? "—"}</strong><span>фотографий</span></div>
        <div><strong>{stage1?.ready_record_count ?? "—"}</strong><span>готовы полностью</span></div>
        <div><strong>{stage1?.incomplete_record_count ?? "—"}</strong><span>неполные</span></div>
        <div><strong>{calibration?.person_count ?? "—"}</strong><span>calibration persons</span></div>
        <div><strong>{stage1?.date_range?.start || "—"}</strong><span>первая дата</span></div>
        <div><strong>{stage1?.date_range?.end || "—"}</strong><span>последняя дата</span></div>
      </div>
      <div className="pose-coverage">
        {POSE_ORDER.map(pose => (
          <div key={pose} className={(poseCounts[pose] || 0) > 0 ? "has" : "empty"}>
            <b>{poseCounts[pose] || 0}</b>
            <span>{pose.replaceAll("_", " ")}</span>
          </div>
        ))}
      </div>
      <div className="dataset-secondary-grid">
        <article className="year-coverage">
          <header><b>По годам</b><span>{yearEntries.length} лет</span></header>
          <div>
            {yearEntries.map(([year, count]) => (
              <i key={year} style={{ height: `${Math.max(8, (count / maxYear) * 84)}px` }} title={`${year}: ${count}`}>
                <span>{year}</span>
              </i>
            ))}
            {!yearEntries.length && <em className="empty-row">Нет данных по годам</em>}
          </div>
        </article>
        <article className="provenance-overview">
          <header><b>Provenance</b><span>conflicts / duplicates</span></header>
          <div>
            <dl><dt>Date conflicts</dt><dd>{stage1?.provenance?.date_conflict_count ?? 0}</dd></dl>
            <dl><dt>Near duplicates</dt><dd>{stage1?.provenance?.near_duplicate_count ?? 0}</dd></dl>
            <dl><dt>Exact duplicate links</dt><dd>{stage1?.provenance?.exact_duplicate_count ?? 0}</dd></dl>
            <dl><dt>Issue rows</dt><dd>{issueTotal}</dd></dl>
          </div>
        </article>
      </div>
      <div className="hash-line">
        <span>index SHA-256</span>
        <code>{stage1?.index_sha256 || "—"}</code>
        <span>manifest SHA-256</span>
        <code>{stage1?.manifest_sha256 || "—"}</code>
      </div>
      <div className="dataset-actions">
        <div>
          <button className="primary" disabled={busy || !stage1 || stage1.status === "unavailable"} onClick={() => void activate()}>Подключить Stage 1</button>
          <button className="ghost" disabled={!stage1 || stage1.status === "unavailable"} onClick={() => { setIssuesOpen(true); setIssueOffset(0); }}>Реестр проблем ({issueTotal})</button>
          <button className="ghost" disabled={!stage1 || stage1.status === "unavailable"} onClick={() => window.dispatchEvent(new CustomEvent("deeputin:navigate", { detail: { view: "runs" } }))} title="Следующий шаг: Stage 2">Прогоны Stage 2 →</button>
          <button className="ghost" disabled={!stage1 || stage1.status === "unavailable"} onClick={() => window.dispatchEvent(new CustomEvent("deeputin:navigate", { detail: { view: "calibration" } }))} title="Проверить калибровку">Калибровка →</button>
        </div>
        <small>Stage 1 и calibration не изменяются. Регистрация пишется только в storage/registry.</small>
      </div>
    </section>

    <div className="manager-grid">
      <section className="card run-card"><header><span>01</span><div><b>Источник данных</b><small>Каталог читается backend-процессом app6</small></div></header>
        <label className="field"><span>INPUT DIRECTORY</span><input value={inputDir} onChange={e => setInputDir(e.target.value)} spellCheck={false}/><small>По умолчанию: {DEFAULT_INPUT}</small></label>
        <label className="field"><span>DEVICE</span><select value={device} onChange={e => setDevice(e.target.value)}><option value="auto">Auto</option><option value="cpu">CPU</option><option value="cuda">CUDA</option><option value="mps">Apple MPS</option></select></label>
      </section>
      <section className="card run-card"><header><span>02</span><div><b>Режим извлечения</b><small>Выберите ровно один reproducible режим</small></div></header>
        <div className="mode-list">
          <button className={mode === "limited" ? "selected" : ""} onClick={() => setMode("limited")}><i>1</i><div><b>Указать количество</b><small>Первые N фотографий в нормативном порядке</small></div></button>
          {mode === "limited" && <label className="inline-number">Количество<input type="number" min="1" max="100000" value={limit} onChange={e => setLimit(Number(e.target.value))}/></label>}
          <button className={mode === "full" ? "selected" : ""} onClick={() => setMode("full")}><i>2</i><div><b>Полный анализ</b><small>Все поддерживаемые фотографии каталога</small></div></button>
          <button className={mode === "per_year" ? "selected" : ""} onClick={() => setMode("per_year")}><i>3</i><div><b>Тест: 5 фото за год</b><small>Детерминированная выборка до пяти кадров каждого года</small></div></button>
        </div>
        <button className="primary run-button" disabled={busy || running || !inputDir.trim()} onClick={() => void run()}>{running ? "Задание уже выполняется" : busy ? "Отправка…" : "▶ Начать извлечение"}</button>
      </section>
      <section className="card danger-card"><header><span>!</span><div><b>Очистить API outputs</b><small>api_stage1/api_stage2; immutable Stage 1 не трогается</small></div></header><p>Введите <strong>ОЧИСТИТЬ</strong>, затем подтвердите операцию.</p><div className="danger-line"><input value={confirmClear} onChange={e => setConfirmClear(e.target.value)} placeholder="ОЧИСТИТЬ"/><button disabled={busy || confirmClear !== "ОЧИСТИТЬ"} onClick={() => void clear()}>Удалить outputs</button></div></section>
    </div>
    <section className="card jobs-card"><header><span>03</span><div><b>Очередь заданий</b><small>Реальный статус `/api/v1/jobs`</small></div></header>{jobs.length === 0 ? <div className="empty-row">Заданий пока нет</div> : <div className="job-list">{jobs.map(j => { const phases = (j.phases || []) as Array<{ name: string; status: string; progress?: { done: number; total: number }; note?: string | null; title?: string }>; return (<article key={j.id}><div className={`job-state ${j.status}`}>{j.status}</div><div className="job-main"><b>{j.kind} · {j.id}{j.profile_id ? ` · ${j.profile_id}` : ""}{j.run_id ? ` · ${j.run_id}` : ""}</b><small>{j.created_at || "—"}</small><div className="progress"><i style={{width: `${j.progress?.total ? Math.min(100, j.progress.done / j.progress.total * 100) : 0}%`}}/></div>{phases.length > 0 && (<ol className="phase-list">{phases.map((phase) => (<li key={phase.name} className={`phase-${phase.status}`}><b>{phase.title || phase.name}</b><span>{phase.status}</span><i>{phase.progress?.total ? `${phase.progress.done}/${phase.progress.total}` : "—"}</i>{phase.note && <em>{phase.note}</em>}</li>))}</ol>)}<pre>{(j.logs || []).slice(-4).join("\n") || j.error || "Ожидание лога…"}</pre></div>{(j.status === "queued" || j.status === "running") && <button onClick={() => void cancelJob(j.id).then(refresh)}>Отменить</button>}</article>);})}</div>}</section>

    <section className="card runs-card"><header><span>04</span><div><b>Результаты расчётов</b><small>`/api/v1/analysis-runs` · завершённые Stage 2 + Stage 3 прогоны профилей</small></div></header>
      <div className="runs-toolbar">
        <input value={runFilter} onChange={e => setRunFilter(e.target.value)} placeholder="Фильтр по run_id или profile_id" />
        <button className="ghost" onClick={() => void loadAnalysisRuns()}>↻ Обновить</button>
        <span>{filteredRuns.length} из {analysisRuns.length}</span>
      </div>
      {filteredRuns.length === 0 ? (
        <div className="empty-row">Прогонов пока нет · запустите Stage 2 + Stage 3 из Profiles</div>
      ) : (
        <div className="runs-table">
          <div className="runs-head"><span>Run ID</span><span>Профиль</span><span>Статус</span><span>Фото</span><span>Phases</span><span>Действие</span></div>
          {filteredRuns.map(run => {
            const failedPhase = (run.phases || []).find((p) => p.status === "failed");
            return (
              <div key={run.run_id} className={`runs-row ${selectedRun?.run_id === run.run_id ? "active" : ""}`}>
                <code>{run.run_id}</code>
                <span>{run.profile_id || "—"}</span>
                <b className={`run-status ${run.status || "unknown"}`}>{run.status || "—"}</b>
                <span>{run.included_count ?? "—"}</span>
                <span>{(run.phases || []).filter(p => p.status === "complete").length}/{(run.phases || []).length}{failedPhase ? ` · ⚠ ${failedPhase.name}` : ""}</span>
                <button disabled={!run.has_summary} onClick={() => void openRunDetail(run.run_id)}>Детали</button>
              </div>
            );
          })}
        </div>
      )}

      {selectedRun && (
        <article className="run-detail">
          <header>
            <b>{selectedRun.run_id}</b>
            <span>{selectedRun.profile_id || "—"} · {selectedRun.status || "—"} · {selectedRun.included_count ?? "—"} фото</span>
            <button className="ghost" onClick={() => setSelectedRun(null)}>×</button>
          </header>
          {selectedRun.phases && selectedRun.phases.length > 0 && (
            <div className="run-phases">
              <b>Фазы</b>
              <ol>
                {selectedRun.phases.map((phase) => (
                  <li key={phase.name} className={`phase-${phase.status}`}>
                    <b>{phase.title || phase.name}</b>
                    <span>{phase.status}</span>
                    <i>{phase.progress?.total ? `${phase.progress.done}/${phase.progress.total}` : "—"}</i>
                    {phase.note && <em>{phase.note}</em>}
                  </li>
                ))}
              </ol>
            </div>
          )}
          <div className="run-paths">
            <div><span>stage2_output</span><code title={selectedRun.stage2_output || ""}>{selectedRun.stage2_output || "—"}</code></div>
            <div><span>stage3_output</span><code title={selectedRun.stage3_output || ""}>{selectedRun.stage3_output || "—"}</code></div>
            <div><span>run_dir</span><code title={selectedRun.run_dir || ""}>{selectedRun.run_dir || "—"}</code></div>
            <div><span>manifest_digest</span><code title={selectedRun.selection_manifest_digest || ""}>{(selectedRun.selection_manifest_digest || "—").slice(0, 18)}…</code></div>
          </div>
          {selectedRun.has_stage2 ? (
            <div className="run-pairs">
              <header><b>Пары</b><span>{runPairs ? `${runPairs.count} всего · ${runPairs.pairs.length} показано` : "загрузка…"}</span></header>
              {!runPairs || pairsLoading ? (
                <div className="empty-row">Загрузка пар…</div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Pair</th>
                      <th>Pose bin</th>
                      {(runPairs.fields || []).filter((f) => f !== "photo_a" && f !== "photo_b" && f !== "pose_bin").map((field) => (
                        <th key={field}>{field}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {runPairs.pairs.map((pair, index) => (
                      <tr key={`${pair.pair || ""}-${index}`}>
                        <td>{pairsOffset + index + 1}</td>
                        <td><code>{pair.pair || "—"}</code></td>
                        <td><code>{pair.pose_bin || "—"}</code></td>
                        {(runPairs.fields || []).filter((f) => f !== "photo_a" && f !== "photo_b" && f !== "pose_bin").map((field) => (
                          <td key={field}>{formatCell(pair[field])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <footer>
                <button disabled={pairsOffset <= 0} onClick={() => setPairsOffset((value) => Math.max(0, value - 25))}>← Назад</button>
                <button disabled={!runPairs || !runPairs.has_more} onClick={() => setPairsOffset((value) => value + 25)}>Вперёд →</button>
              </footer>
            </div>
          ) : (
            <div className="empty-row">Stage 2 ещё не завершён — пары появятся позже</div>
          )}
        </article>
      )}
    </section>

    {issuesOpen && <div className="issues-backdrop" onClick={() => setIssuesOpen(false)}>
      <section className="issues-dialog" onClick={e => e.stopPropagation()}>
        <header>
          <div>
            <small>STAGE 1 VALIDATION</small>
            <h2>Реестр проблем</h2>
            <p>Все строки Stage 1 либо видны на timeline, либо перечислены здесь с причиной.</p>
          </div>
          <button onClick={() => setIssuesOpen(false)}>×</button>
        </header>
        <div className="issues-toolbar">
          <label>Категория
            <select value={issueCategory} onChange={e => { setIssueCategory(e.target.value); setIssueOffset(0); }}>
              <option value="">Все категории</option>
              {Object.keys(issueReport?.category_counts || stage1?.issue_counts || {}).map(key => (
                <option key={key} value={key}>{key}</option>
              ))}
            </select>
          </label>
          <span>Показаны {issueReport ? `${issueReport.offset + 1}–${Math.min(issueReport.offset + issueReport.issues.length, issueReport.total)} из ${issueReport.total}` : "…"}</span>
        </div>
        <div className="issues-table">
          <div className="issues-head"><span>Фото</span><span>Категория</span><span>Деталь</span><span>Row</span></div>
          {(issueReport?.issues || []).map((issue: import("../../shared/api").DatasetIssue, index: number) => (
            <div className="issues-row" key={`${issue.photo_id}-${issue.category}-${issue.row}-${index}`}>
              <code>{issue.photo_id || "—"}</code>
              <b>{issue.category}</b>
              <span>{issue.detail}</span>
              <em>{issue.row ?? "—"}</em>
            </div>
          ))}
          {issueReport && issueReport.issues.length === 0 && <div className="issues-empty">Проблем в выбранной категории нет</div>}
        </div>
        <footer>
          <button disabled={!issueReport || issueOffset <= 0} onClick={() => setIssueOffset(value => Math.max(0, value - 100))}>← Назад</button>
          <button disabled={!issueReport || issueOffset + 100 >= issueReport.total} onClick={() => setIssueOffset(value => value + 100)}>Вперёд →</button>
        </footer>
      </section>
    </div>}
  </div>;
}
