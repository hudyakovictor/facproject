import { useEffect, useState } from "react";
import { modalProps, useModal } from "../useModal";
import type { Photo } from "../data";
import { fetchPhotoDetail, fetchPhotoFullMesh, photoImageUrl, type PhotoDetail, type FullMesh } from "../api";
import MeshViewer from "./LazyMeshViewer";
import Icon from "./Icon";
interface Props { photo: Photo; onClose: () => void }
export default function FullPhotoOverlay({photo,onClose}:Props){
  const ref=useModal<HTMLDivElement>(onClose); const [detail,setDetail]=useState<PhotoDetail|null>(null); const [mesh,setMesh]=useState<FullMesh|null>(null); const [error,setError]=useState("");
  useEffect(()=>{let dead=false; setDetail(null);setMesh(null);setError(""); fetchPhotoDetail(photo.id).then(d=>{if(dead)return;setDetail(d);if(d.full_mesh_available) return fetchPhotoFullMesh(photo.id).then(m=>{if(!dead)setMesh(m)});}).catch(e=>{if(!dead)setError(e instanceof Error?e.message:String(e))});return()=>{dead=true}},[photo.id]);
  return <div ref={ref} {...modalProps(`Real photo inspector: ${photo.id}`)} className="fixed inset-0 z-[100] bg-black/95 flex outline-none">
    <main className="flex-1 grid grid-cols-2 gap-2 p-4 min-w-0">
      <section className="border border-border bg-surface relative overflow-hidden"><img src={photoImageUrl(photo.id,"original")} alt={photo.id} className="w-full h-full object-contain"/><span className="absolute top-2 left-2 bg-bg/80 px-2 py-1 font-mono text-[9px]">STAGE 1 ORIGINAL</span></section>
      <section className="border border-border bg-surface relative">
        {/* The anomaly indicator is deliberately independent of async mesh loading:
            a failed API call must not erase the visible review cue. */}
        {(Math.abs(photo.zChinProj) > 2 || Math.abs(photo.zOrbitDepth) > 2) && <svg aria-label="geometry review cue" className="absolute inset-0 z-10 w-full h-full pointer-events-none" viewBox="0 0 100 100"><circle cx="50" cy="55" r="18" fill="none" stroke="#ff3b30" strokeWidth="0.5">{!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches && <animate attributeName="r" values="15;20;15" dur="1.4s" repeatCount="indefinite"/>}</circle></svg>}
        {error?<div role="alert" className="h-full flex items-center justify-center p-8 text-center"><div><Icon name="alert-octagon" size={28} color="#ff3b30" className="mx-auto mb-3"/><div className="font-display">GEOMETRY UNAVAILABLE</div><p className="font-mono text-[10px] text-text-muted mt-2 max-w-md">{error}</p><p className="font-mono text-[9px] text-warning mt-2">No substitute geometry was rendered.</p></div></div>:mesh?<MeshViewer fullMesh={{vertices:mesh.vertices,triangles:mesh.triangles}} wireframe showPoints={false} className="w-full h-full"/>:detail?<MeshViewer points106={detail.landmarks_106} points134={detail.landmarks_134} wireframe showPoints className="w-full h-full"/>:<div className="h-full flex items-center justify-center font-mono text-[10px] text-text-muted">Loading verified geometry…</div>}
        <span className="absolute top-2 left-2 bg-bg/80 px-2 py-1 font-mono text-[9px]">{mesh?'STAGE 1 BFM MESH':detail?'STAGE 1 LANDMARKS':'WAITING'}</span>
      </section>
    </main>
    <aside className="w-72 border-l border-border bg-surface p-4 font-mono text-[10px]"><div className="font-display text-sm tracking-forensic mb-4">{photo.id}</div><dl className="space-y-2"><div><dt className="text-text-muted">Date</dt><dd>{photo.date}</dd></div><div><dt className="text-text-muted">Pose bin</dt><dd>{photo.bucket}</dd></div><div><dt className="text-text-muted">Evidence state</dt><dd>{photo.fuzzy}</dd></div><div><dt className="text-text-muted">Geometry source</dt><dd>{mesh?'full mesh artifact':detail?'landmark artifact':'not available'}</dd></div></dl><button onClick={onClose} className="mt-6 w-full border border-border p-2 hover:bg-surface-2">CLOSE</button></aside>
  </div>
}
