import { useMemo, useState } from "react";
import type { Photo } from "../lib/types";
import { fetchPairMetrics } from "../lib/api";
import PhotoArtifactImage from "../components/PhotoArtifactImage";
import { Banner, Button, Empty, Panel, Select } from "../components/ui";
export default function PairsPage({ photos }: { photos: Photo[] }) {
  const groups = useMemo(() => {
    const m = new Map<string, Photo[]>();
    for (const p of photos) { const a = m.get(p.bucket) || []; a.push(p); m.set(p.bucket, a); }
    return m;
  }, [photos]);
  const defaultBin = [...groups.entries()].find(([, arr]) => arr.length >= 2)?.[0] || photos[0]?.bucket || "";
  const [bin, setBin] = useState(defaultBin);
  const list = groups.get(bin) || [];
  const [a, setA] = useState(list[0]?.id || "");
  const [b, setB] = useState(list[1]?.id || list[0]?.id || "");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const run = async () => {
    if (!a || !b || a === b) { setErr("Выберите два разных кадра"); return; }
    setLoading(true); setErr(""); setData(null);
    try {
      const pa = photos.find(p => p.id === a); const pb = photos.find(p => p.id === b);
      if (pa && pb && pa.bucket !== pb.bucket) { setErr("Primary comparison только inside same pose bin."); setLoading(false); return; }
      setData(await fetchPairMetrics(a, b));
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };
  if (photos.length < 2) return <div className="page"><Empty title="Недостаточно фото">Нужно ≥2 кадра одного pose bin.</Empty></div>;
  return (
    <div className="page">
      <div className="page-hd"><div><h1>Сравнение пар</h1><p>Primary geometry только в одном pose bin.</p></div></div>
      <Panel title="Выбор пары">
        <div className="grid-3">
          <div className="field"><label>Pose bin</label>
            <Select value={bin} onChange={e => { const nb = e.target.value; setBin(nb); const arr = groups.get(nb) || []; setA(arr[0]?.id || ""); setB(arr[1]?.id || arr[0]?.id || ""); }}>
              {[...groups.entries()].map(([k, arr]) => <option key={k} value={k}>{k} · {arr.length}</option>)}
            </Select>
          </div>
          <div className="field"><label>Фото A</label><Select value={a} onChange={e => setA(e.target.value)}>{list.map(p => <option key={p.id} value={p.id}>{p.date} · {p.id}</option>)}</Select></div>
          <div className="field"><label>Фото B</label><Select value={b} onChange={e => setB(e.target.value)}>{list.map(p => <option key={p.id} value={p.id}>{p.date} · {p.id}</option>)}</Select></div>
        </div>
        <div className="row" style={{ marginTop: 12 }}><Button variant="primary" disabled={loading || !a || !b} onClick={() => void run()}>{loading ? "загрузка…" : "сравнить"}</Button></div>
      </Panel>
      <div className="grid-2">
        <Panel title={`A · ${a || "—"}`}>{a ? <div style={{ height: 280 }}><PhotoArtifactImage photoId={a} kind="original" /></div> : null}</Panel>
        <Panel title={`B · ${b || "—"}`}>{b ? <div style={{ height: 280 }}><PhotoArtifactImage photoId={b} kind="original" /></div> : null}</Panel>
      </div>
      {err && <Banner kind="bad" title="Пара ограничена">{err}</Banner>}
      {data && <Panel title="pair metrics"><Banner kind="info" title="not a verdict">Observation/candidate для ручной проверки.</Banner><pre className="code">{JSON.stringify(data, null, 2)}</pre></Panel>}
    </div>
  );
}
