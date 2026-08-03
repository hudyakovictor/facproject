import { useEffect, useState, useRef } from "react";
import { Photo } from "../data";
import Icon from "./Icon";
import { comparePhotosFullMesh, FullMeshCompareResult } from "../api";
import MeshViewer from "./LazyMeshViewer";

interface Props {
  photos: Photo[];
  onClose: () => void;
}

export default function MorphPlayerOverlay({ photos, onClose }: Props) {
  const [index, setIndex] = useState(0);
  const [morphT, setMorphT] = useState(0);
  const [meshData, setMeshData] = useState<FullMeshCompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(true);
  const frameRef = useRef<number>(0);
  const lastTimeRef = useRef<number>(0);

  // Filter photos to only those that have reasonable quality to prevent crash/empty
  const validPhotos = photos.filter(p => !p.hidden && p.quality > 0.3);

  useEffect(() => {
    if (validPhotos.length < 2) return;
    let cancelled = false;
    
    const loadPair = async () => {
      if (index >= validPhotos.length - 1) {
        setPlaying(false);
        return;
      }
      setLoading(true);
      try {
        const res = await comparePhotosFullMesh(validPhotos[index].id, validPhotos[index + 1].id);
        if (cancelled) return;
        setMeshData(res);
        setMorphT(0);
        lastTimeRef.current = performance.now();
      } catch (err) {
        console.warn("MorphPlayer skipped pair due to error:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    
    if (playing) {
      loadPair();
    }

    return () => { cancelled = true; };
  }, [index, validPhotos, playing]);

  useEffect(() => {
    if (!playing || loading || !meshData) return;
    
    const animate = (time: number) => {
      const dt = time - lastTimeRef.current;
      lastTimeRef.current = time;
      
      setMorphT(prev => {
        const next = prev + (dt / 1500); // 1.5 seconds per morph
        if (next >= 1) {
          // Move to next pair
          setTimeout(() => setIndex(i => i + 1), 500); // hold at 100% for 500ms
          return 1;
        }
        return next;
      });
      
      if (morphT < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };
    
    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [playing, loading, meshData, morphT]);

  if (validPhotos.length < 2) {
    return (
      <div className="fixed inset-0 z-50 bg-[#000]/90 backdrop-blur-sm flex items-center justify-center">
        <div className="bg-[#0a0a0a] border border-[#333] p-6 max-w-md text-center shadow-2xl">
          <Icon name="alert-triangle" size={24} color="#e8af34" className="mx-auto mb-3" />
          <h2 className="font-mono text-sm tracking-forensic text-[#e2e2e8] mb-2 uppercase">Insufficient Data</h2>
          <p className="font-mono text-[10px] text-[#797876] mb-6">Need at least 2 valid photos to play morphological evolution.</p>
          <button onClick={onClose} className="px-4 py-2 border border-[#333] text-[#e2e2e8] hover:bg-[#141414] font-mono text-[10px] uppercase">Close</button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-[#000]/95 backdrop-blur-md flex flex-col">
      <div className="flex-shrink-0 border-b border-[#222] bg-[#0a0a0a] p-3 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h2 className="font-mono text-[11px] tracking-[0.2em] text-[#e2e2e8] flex items-center gap-2 uppercase">
            <Icon name="play" size={14} color="#5591c7" /> Chronological Morph
          </h2>
          <div className="font-mono text-[9px] text-[#797876] flex items-center gap-2">
            <span>{index + 1} / {validPhotos.length - 1}</span>
            <span>·</span>
            <span className="text-[#5591c7]">{validPhotos[index]?.id}</span>
            <Icon name="chevron-right" size={10} />
            <span className="text-[#e8af34]">{validPhotos[index + 1]?.id}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => { setPlaying(!playing); if(!playing) setIndex(0); }} className="p-2 border border-[#333] hover:bg-[#141414] text-[#e2e2e8]">
            <Icon name={playing ? "x" : "play"} size={14} />
          </button>
          <button onClick={onClose} className="p-2 border border-[#333] hover:bg-[#ff3b30]/10 text-[#797876] hover:text-[#ff3b30] transition-colors">
            <Icon name="x" size={14} />
          </button>
        </div>
      </div>
      
      <div className="flex-1 relative bg-[#050505]">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="font-mono text-[10px] tracking-forensic text-[#5591c7] animate-pulse">Computing Mesh Algebra...</div>
          </div>
        )}
        
        {meshData && (
          <MeshViewer
            fullMesh={{
              vertices: meshData.vertices_a,
              verticesTarget: meshData.vertices_b_aligned,
              triangles: meshData.triangles,
              vertexValues: meshData.residuals
            }}
            morphT={morphT}
            wireframe={true}
            className="w-full h-full"
            backgroundColor="#050505"
          />
        )}
        
        {/* Timeline Progress Bar */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-128 max-w-full px-4">
          <div className="flex justify-between font-mono text-[9px] text-[#797876] mb-2 uppercase">
            <span>{validPhotos[index]?.date || "Unknown"}</span>
            <span className="text-white">{(morphT * 100).toFixed(0)}%</span>
            <span>{validPhotos[index + 1]?.date || "Unknown"}</span>
          </div>
          <div className="h-1 bg-[#141414] border border-[#222] relative overflow-hidden">
            <div className="absolute top-0 bottom-0 left-0 bg-[#5591c7]" style={{ width: `${morphT * 100}%` }} />
          </div>
          <div className="flex justify-between font-mono text-[8px] text-[#4d4d4d] mt-1 tracking-forensic">
            <span>{validPhotos[index]?.era}</span>
            <span>{validPhotos[index + 1]?.era}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
