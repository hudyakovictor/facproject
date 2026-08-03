import { useEffect, useMemo, useState } from "react";
import type { Photo, PhotoImageKind } from "../lib/types";
import { POSE_LABELS } from "../lib/types";
import { fmt, fmtDate, shortId } from "../lib/format";
import { fetchPhotoDetail, fetchSkinZones } from "../lib/api";
import PhotoArtifactImage from "../components/PhotoArtifactImage";
import KeysPanel from "../components/KeysPanel";
import { Banner, Button, Chip, Empty, Kv, Panel } from "../components/ui";
const LAYERS: Array<{ id: PhotoImageKind; label: string }> = [
  { id: "original", label: "original" }, { id: "face_crop", label: "face crop" },
  { id: "thumbnail", label: "thumbnail" }, { id: "uv_texture", label: "UV texture" }, { id: "zones_overlay", label: "zones" },
];
export default function InspectorPage({ photos, selectedId, onSelect }: { photos: Photo[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const photo = useMemo(() => photos.find(p => p.id === selectedId) || photos[0] || null, [photos, selectedId]);
  const [layer, setLayer] = useState<PhotoImageKind>("original");
  const [tab, setTab] = useState<"summary" | "keys" | "skin" | "raw">("keys");
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [skin, setSkin] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!photo) return;
    let dead = false; setDetail(null); setSkin(null); setErr("");
    Promise.allSettled([fetchPhotoDetail(photo.id), fetchSkinZones(photo.id)]).then(res => {
      if (dead) return;
      if (res[0].status === "fulfilled") setDetail(res[0].value);
      else setErr(String((res[0] as PromiseRejectedResult).reason?.message || (res[0] as PromiseRejectedResult).reason));
      if (res[1].status === "fulfilled") setSkin(res[1].value);
    });
    return () => { dead = true; };
  }, [photo?.id]);
  if (!photos.length) return <div className="page"><Empty title="Нет фото для инспекции">Сначала выполните Stage 1 extract.</Empty></div>;
  if (!photo) return null;
  const idx = photos.findIndex(p => p.id === photo.id);
  const prev = idx > 0 ? photos[idx - 1] : null;
  const next = idx < photos.length - 1 ? photos[idx + 1] : null;
  return (
    <div className="page">
      <div className="page-hd">
        <div><h1>Инспектор кадра</h1><p>Реальные Stage 1 артефакты и извлечённые ключи. Measurements ≠ identity verdict.</p></div>
        <div className="row"><Button size="sm" disabled={!prev} onClick={() => prev && onSelect(prev.id)}>← prev</Button><Button size="sm" disabled={!next} onClick={() => next && onSelect(next.id)}>next →</Button></div>
      </div>
      <div className="inspector-layout">
        <div className="inspector-media">
          <div className="inspector-stage">
            <PhotoArtifactImage photoId={photo.id} kind={layer} alt={photo.id} />
            <div style={{ position: "absolute", left: 10, top: 10 }} className="row-wrap"><Chip kind="info">{layer}</Chip><Chip>{POSE_LABELS[photo.bucket] || photo.bucket}</Chip></div>
          </div>
          <div className="layer-bar">{LAYERS.map(l => (<Button key={l.id} size="sm" variant={layer === l.id ? "primary" : "default"} onClick={() => setLayer(l.id)}>{l.label}</Button>))}</div>
        </div>
        <div className="stack scroll-y" style={{ maxHeight: "calc(100vh - 140px)" }}>
          <Panel title={shortId(photo.id, 28)} right={<Chip>{fmtDate(photo.t)}</Chip>}>
            <div className="stack">
              <Banner kind="info" title="Applicability">Ракурс: {POSE_LABELS[photo.bucket] || photo.bucket}. Качество: {fmt(photo.quality, 3)}. Confidence: {fmt(photo.confidence, 2)} (measurement, not identity).</Banner>
              {photo.exifAnomaly && <Banner kind="bad" title="Конфликт датировки">EXIF/source claim расходится с filename date.</Banner>}
              <Kv rows={[["ID", <span className="mono">{photo.id}</span>],["дата", fmtDate(photo.t)],["era", photo.era],["pose bin", photo.bucket],["yaw°", fmt(photo.yaw, 1)],["quality", fmt(photo.quality, 3)],["boneScore", fmt(photo.boneScore, 3)],["flags", photo.flags?.length ? photo.flags.join(", ") : "—"]]} />
            </div>
          </Panel>
          <div className="pill-tabs">{([["summary","сводка"],["keys","Stage 1 keys"],["skin","кожа/зоны"],["raw","raw detail"]] as const).map(([id, label]) => (<button key={id} type="button" className={tab===id?"active":""} onClick={() => setTab(id)}>{label}</button>))}</div>
          {tab === "summary" && <Panel title="Геометрия / текстура"><Kv rows={[["orbit / chin / jaw / cheek", `${fmt(photo.orbit)} / ${fmt(photo.chin)} / ${fmt(photo.jaw)} / ${fmt(photo.cheek)}`],["symmetry", fmt(photo.symmetry)],["z scores", `${fmt(photo.zOrbitDepth,2)} / ${fmt(photo.zChinProj,2)} / ${fmt(photo.zJawWidth,2)} / ${fmt(photo.zCheek,2)}`],["texture", `${fmt(photo.siliconeProb)} / ${fmt(photo.specular)} / ${fmt(photo.lbpEntropy)}`]]} /><div className="disclaimer" style={{ marginTop: 10 }}>Null/NaN → «—», никогда 0.</div></Panel>}
          {tab === "keys" && <KeysPanel photoId={photo.id} defaultOpen />}
          {tab === "skin" && <Panel title="Skin zones"><pre className="code">{JSON.stringify(skin || { note: "нет данных" }, null, 2)}</pre></Panel>}
          {tab === "raw" && <Panel title="GET /photos/id">{err && <Banner kind="warn">{err}</Banner>}<pre className="code">{JSON.stringify(detail || {}, null, 2)}</pre></Panel>}
        </div>
      </div>
    </div>
  );
}
