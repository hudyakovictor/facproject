import { useMemo, useState } from "react";
import type { Photo, PoseBucket } from "../lib/types";
import { POSE_BUCKETS, POSE_LABELS } from "../lib/types";
import { fmt, fmtDate } from "../lib/format";
import PhotoArtifactImage from "../components/PhotoArtifactImage";
import { Empty, Input, Select } from "../components/ui";
export default function GalleryPage({ photos, onOpen }: { photos: Photo[]; onOpen: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [bucket, setBucket] = useState<"all" | PoseBucket>("all");
  const [onlyFlags, setOnlyFlags] = useState(false);
  const filtered = useMemo(() => {
    const qq = q.trim().toLowerCase();
    return photos.filter(p => {
      if (bucket !== "all" && p.bucket !== bucket) return false;
      if (onlyFlags && !(p.flags?.length || p.exifAnomaly)) return false;
      if (!qq) return true;
      return p.id.toLowerCase().includes(qq) || p.date.includes(qq) || p.bucket.includes(qq) || p.era.toLowerCase().includes(qq);
    });
  }, [photos, q, bucket, onlyFlags]);
  return (
    <div className="page">
      <div className="page-hd"><div><h1>Галерея</h1><p>Реальные Stage 1 артефакты. Клик открывает инспектор.</p></div></div>
      <div className="row-wrap">
        <Input style={{ maxWidth: 280 }} placeholder="поиск: id, дата, bin…" value={q} onChange={e => setQ(e.target.value)} />
        <Select value={bucket} onChange={e => setBucket(e.target.value as "all" | PoseBucket)} style={{ maxWidth: 220 }}>
          <option value="all">все ракурсы</option>
          {POSE_BUCKETS.map(b => <option key={b} value={b}>{POSE_LABELS[b]}</option>)}
        </Select>
        <label className="row muted" style={{ gap: 6 }}><input type="checkbox" checked={onlyFlags} onChange={e => setOnlyFlags(e.target.checked)} /> только с флагами</label>
        <div className="spacer" /><span className="mono faint">{filtered.length}/{photos.length}</span>
      </div>
      {filtered.length === 0 ? <Empty title="Нет фото по фильтру">Сбросьте поиск или выберите другой ракурс.</Empty> : (
        <div className="photo-grid">{filtered.map(p => (
          <button key={p.id} type="button" className="photo-card" onClick={() => onOpen(p.id)}>
            <div className="thumb"><PhotoArtifactImage photoId={p.id} kind="thumbnail" cover alt={p.id} /></div>
            <div className="meta"><div className="id" title={p.id}>{p.id}</div><div className="sub">{fmtDate(p.t)} · {POSE_LABELS[p.bucket] || p.bucket}</div><div className="sub">q={fmt(p.quality, 2)} · yaw={fmt(p.yaw, 1)}°</div></div>
          </button>
        ))}</div>
      )}
    </div>
  );
}
