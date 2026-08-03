import { useEffect, useState } from "react";
import { fetchReportSection, fetchReportSummary } from "../lib/api";
import { Banner, Button, Empty, Panel } from "../components/ui";
export default function ReportPage() {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [section, setSection] = useState("");
  const [body, setBody] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState("");
  const load = async () => {
    setErr("");
    try {
      const s = await fetchReportSummary(); setSummary(s);
      const sections = (s.sections as string[]) || [];
      if (sections[0]) setSection(sections[0]);
    } catch (e) { setSummary(null); setErr(e instanceof Error ? e.message : String(e)); }
  };
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!section) return;
    let dead = false;
    fetchReportSection(section).then(d => { if (!dead) setBody(d); })
      .catch(e => { if (!dead) setBody({ error: e instanceof Error ? e.message : String(e) }); });
    return () => { dead = true; };
  }, [section]);
  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ summary, section, body, not_a_verdict: true, exported_at: new Date().toISOString() }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `deeputin-report-${Date.now()}.json`; a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="page">
      <div className="page-hd">
        <div><h1>Отчёт</h1><p>Stage 3 sections · observation-only · not a verdict.</p></div>
        <div className="row"><Button onClick={() => void load()}>обновить</Button><Button variant="primary" onClick={exportJson}>экспорт JSON</Button></div>
      </div>
      <Banner kind="ok" title="not_a_verdict">Автоотчёт не утверждает личность или подмену.</Banner>
      {err && <Banner kind="warn" title="report недоступен">{err}</Banner>}
      {!summary && !err && <Empty title="Загрузка отчёта" />}
      {summary && (<>
        <Panel title="Summary"><pre className="code">{JSON.stringify(summary, null, 2)}</pre></Panel>
        <Panel title="Секции">
          <div className="pill-tabs" style={{ marginBottom: 12 }}>
            {((summary.sections as string[]) || []).map(s => (<button key={s} type="button" className={section===s?"active":""} onClick={() => setSection(s)}>{s}</button>))}
          </div>
          <pre className="code">{JSON.stringify(body || {}, null, 2)}</pre>
        </Panel>
      </>)}
    </div>
  );
}
