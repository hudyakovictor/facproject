import { useEffect, useState } from "react";
import { fetchRunKeys, fetchRunSummary } from "../lib/api";
import { Banner, Button, Chip, Empty, Panel, Stat } from "../components/ui";
export default function RunPage() {
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [keysName, setKeysName] = useState("technical_summary");
  const [keys, setKeys] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState("");
  const load = async () => {
    setErr("");
    try { setSummary(await fetchRunSummary()); }
    catch (e) { setSummary(null); setErr(e instanceof Error ? e.message : String(e)); }
  };
  useEffect(() => { void load(); }, []);
  const hashes = (summary?.hashes || {}) as Record<string, string>;
  return (
    <div className="page">
      <div className="page-hd"><div><h1>Сводка прогона</h1><p>Hash quartet, limitations, technical summary.</p></div><Button onClick={() => void load()}>обновить</Button></div>
      {err && <Banner kind="warn" title="run/summary недоступен">{err}</Banner>}
      {!summary && !err && <Empty title="Загрузка сводки" />}
      {summary && (<>
        <div className="grid-4">
          <Stat k="photos" v={String(summary.photo_count ?? "—")} />
          <Stat k="pairs" v={String(summary.pair_count ?? "—")} />
          <Stat k="source" v={String(summary.source_mode ?? "—")} />
          <Stat k="schema" v={String(summary.schema ?? "—")} />
        </div>
        <Panel title="Hash quartet">
          <div className="row-wrap" style={{ marginBottom: 10 }}>
            {Object.keys(hashes).length ? Object.entries(hashes).map(([k, v]) => (<Chip key={k} kind="info">{k}: {String(v).slice(0, 12)}…</Chip>)) : <span className="muted">Хеши не пришли в summary.</span>}
          </div>
          <pre className="code">{JSON.stringify(hashes, null, 2)}</pre>
        </Panel>
        <Panel title="Full summary"><pre className="code">{JSON.stringify(summary, null, 2)}</pre></Panel>
        <Panel title="Run keys" right={<>
          <select className="select" style={{ width: 220 }} value={keysName} onChange={e => setKeysName(e.target.value)}>
            <option value="technical_summary">technical_summary</option>
            <option value="analysis_manifest">analysis_manifest</option>
            <option value="limitations">limitations</option>
            <option value="metric_catalog">metric_catalog</option>
          </select>
          <Button size="sm" onClick={() => void fetchRunKeys(keysName).then(setKeys).catch(e => setKeys({ error: String(e) }))}>загрузить</Button>
        </>}>
          <pre className="code">{JSON.stringify(keys || { note: "выберите artifact" }, null, 2)}</pre>
        </Panel>
      </>)}
    </div>
  );
}
