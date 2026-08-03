import { useMemo } from "react";
import { Photo, FUZZY_COLORS } from "../data";
import { photoImageUrl } from "../api";
import Icon from "./Icon";

export function EraCompareView({ photos, onSelectPhoto, onDoubleClick, selectedId }: {
  photos: Photo[]; onSelectPhoto: (id: string) => void; onDoubleClick: (p: Photo) => void; selectedId: string | null;
}) {
  const groups = useMemo(() => {
    const out: Record<string, Photo[]> = {};
    for (const p of photos) (out[p.era] ??= []).push(p);
    return Object.entries(out).sort((a,b)=>(a[1][0]?.t??0)-(b[1][0]?.t??0));
  }, [photos]);
  return <div className="w-full h-full flex bg-bg/40 overflow-x-auto">
    {groups.map(([era,list]) => <section key={era} className="min-w-72 flex-1 border-r border-border flex flex-col">
      <header className="p-3 border-b border-border bg-surface-2"><div className="font-display text-sm tracking-forensic">{era}</div><div className="font-mono text-[10px] text-text-muted">{list.length} real records</div></header>
      <div className="grid grid-cols-3 gap-1 p-2 overflow-y-auto">
        {list.map(p => <button key={p.id} onClick={()=>onSelectPhoto(p.id)} onDoubleClick={()=>onDoubleClick(p)} className={`relative aspect-[3/4] border bg-surface-2 overflow-hidden ${selectedId===p.id?'ring-2 ring-info':''}`} title={`${p.id} · ${p.date}`}>
          <img src={photoImageUrl(p.id,"original")} alt={p.id} className="w-full h-full object-cover" loading="lazy" />
          <span className="absolute inset-x-0 bottom-0 bg-bg/85 px-1 py-0.5 font-mono text-[8px] truncate" style={{color:FUZZY_COLORS[p.fuzzy]}}>{p.date} · {p.fuzzy}</span>
        </button>)}
      </div>
    </section>)}
  </div>;
}

/** Projection is intentionally unavailable until Stage 2 provides a versioned embedding artifact. */
export function ClusterView(_props: { photos: Photo[]; onSelectPhoto: (id:string)=>void; onDoubleClick:(p:Photo)=>void; selectedId:string|null }) {
  return <div className="w-full h-full flex items-center justify-center bg-bg"><div role="status" className="max-w-xl border border-warning/60 bg-warning/10 p-6 text-center"><Icon name="alert-triangle" size={28} color="#e8af34" className="mx-auto mb-3"/><h2 className="font-display tracking-forensic">PROJECTION NOT MEASURED</h2><p className="font-mono text-[11px] text-text-muted mt-2">Stage 2 did not provide a versioned identity embedding/PCA artifact. The UI will not construct proxy coordinates.</p></div></div>;
}
