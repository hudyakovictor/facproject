import React, { useState, useMemo, useEffect, useRef } from 'react';
import DropZone from './DropZone';
import CanvasMulti from './CanvasMulti';

/**
 * 🌊 Fluid Dynamics Morphing — As-Rigid-As-Possible интерполяция формы между
 * двумя лицами вместо наивной линейной V(t)=(1-t)VA+t·VB (см.
 * morphing/backend/arap.py — Alexa et al. 2000). Бэкенд отдаёт K=9
 * предрасчитанных ARAP-кадров в схеме /api/morph-multi; здесь они просто
 * проигрываются через уже существующий Timeline-плеер (CanvasMulti,
 * Catmull-Rom между соседними кадрами) — ноль нового шейдерного кода.
 */
export default function FluidMorph() {
  const [photoA, setPhotoA] = useState(null);
  const [photoB, setPhotoB] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [playheadT, setPlayheadT] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [lighting, setLighting] = useState(false);

  const handleProcess = async () => {
    if (!photoA || !photoB) { setError('Загрузите оба фото (A и B)'); return; }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('photo_a', photoA);
      formData.append('photo_b', photoB);
      const res = await fetch('/api/morph-pair-fluid', { method: 'POST', body: formData });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errJson.detail || 'Не удалось построить ARAP-морф');
      }
      const json = await res.json();
      setData(json);
      setPlayheadT(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const maxT = data ? data.count - 1 : 0;

  useEffect(() => {
    if (!isPlaying || !data) return;
    let forward = true;
    const interval = setInterval(() => {
      setPlayheadT((p) => {
        if (p >= maxT) forward = false;
        if (p <= 0) forward = true;
        const step = maxT > 0 ? maxT / 200 : 0;
        return Math.max(0, Math.min(maxT, forward ? p + step : p - step));
      });
    }, 25);
    return () => clearInterval(interval);
  }, [isPlaying, data, maxT]);

  const { slotIndices, segT } = useMemo(() => {
    if (!data) return { slotIndices: [0, 0, 1, 1], segT: 0 };
    const n = data.count;
    const t = Math.max(0, Math.min(maxT, playheadT));
    const k = Math.min(Math.floor(t), Math.max(n - 2, 0));
    const localT = n > 1 ? t - k : 0;
    return {
      slotIndices: [Math.max(k - 1, 0), k, Math.min(k + 1, n - 1), Math.min(k + 2, n - 1)],
      segT: localT,
    };
  }, [data, playheadT, maxT]);

  const currentMaxDist = data?.metadata?.arap_vs_linear_max_dist
    ? data.metadata.arap_vs_linear_max_dist[Math.round(Math.max(0, Math.min(maxT, playheadT)))]
    : null;

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%' }}>
      <div style={{
        width: '380px', minWidth: '380px', height: '100%', background: '#0d1117',
        borderRight: '1px solid #30363d', padding: '24px', boxSizing: 'border-box',
        overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '18px',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '22px' }}>🌊</span>
            <h2 style={{ margin: 0, fontSize: '17px', fontWeight: 'bold' }}>Fluid Morph (ARAP)</h2>
          </div>
          <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#8b949e' }}>
            As-Rigid-As-Possible интерполяция вместо линейной: сохраняет локальную
            жёсткость (Alexa et al. 2000) — меньше "сминания" геометрии там, где
            части лица поворачиваются друг относительно друга.
          </p>
        </div>

        {!data && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <DropZone label="Лицо A" photo={photoA} onPhotoSelect={setPhotoA} badgeColor="#58a6ff" />
              <DropZone label="Лицо B" photo={photoB} onPhotoSelect={setPhotoB} badgeColor="#f778ba" />
            </div>
            <button
              onClick={handleProcess}
              disabled={loading || !photoA || !photoB}
              style={{ padding: '12px', background: loading ? '#30363d' : '#238636', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 'bold', fontSize: '14px', cursor: loading ? 'not-allowed' : 'pointer' }}
            >
              {loading ? '⏳ Реконструкция + ARAP-решение (K=9)...' : '🌊 Построить fluid-морф'}
            </button>
          </>
        )}

        {error && (
          <div style={{ background: 'rgba(248, 81, 73, 0.15)', border: '1px solid #f85149', borderRadius: '8px', padding: '10px 14px', color: '#ff7b72', fontSize: '13px' }}>
            ⚠️ {error}
          </div>
        )}

        {data && (
          <>
            <button
              onClick={() => { setData(null); setError(null); setIsPlaying(false); }}
              style={{ padding: '8px', background: '#21262d', border: '1px solid #30363d', borderRadius: '8px', color: '#c9d1d9', fontSize: '12px', cursor: 'pointer' }}
            >
              ↺ Новая пара (сменить фото)
            </button>

            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: '#8b949e' }}>Прогресс A→B</span>
                <span style={{ color: '#00ffaa', fontWeight: 'bold' }}>{((playheadT / (maxT || 1)) * 100).toFixed(0)}%</span>
              </div>
              <input type="range" min="0" max={maxT} step="0.01" value={playheadT}
                onChange={(e) => { setIsPlaying(false); setPlayheadT(parseFloat(e.target.value)); }}
                style={{ width: '100%', accentColor: '#00ffaa' }} />
              <button
                onClick={() => setIsPlaying((p) => !p)}
                style={{ padding: '10px', background: isPlaying ? '#da3633' : '#238636', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer' }}
              >
                {isPlaying ? '⏸ Остановить' : '▶️ Воспроизвести'}
              </button>
              {currentMaxDist !== null && (
                <div style={{ fontSize: '11px', color: '#8b949e' }}>
                  Расхождение ARAP vs линейная интерполяция в этом кадре (макс. по вершинам):{' '}
                  <b style={{ color: '#e6edf3' }}>{currentMaxDist.toFixed(4)}</b>
                </div>
              )}
            </div>

            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '10px 14px', fontSize: '10.5px', color: '#6e7681', lineHeight: 1.4 }}>
              ℹ️ {data.metadata.note}
            </div>

            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#8b949e', textTransform: 'uppercase' }}>Слои</div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
                <input type="checkbox" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} style={{ accentColor: '#ff7b72' }} />
                <span>Heatmap разницы текущего сегмента</span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
                <input type="checkbox" checked={wireframe} onChange={(e) => setWireframe(e.target.checked)} style={{ accentColor: '#79c0ff' }} />
                <span>Полигональная сетка</span>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
                <input type="checkbox" checked={lighting} onChange={(e) => setLighting(e.target.checked)} style={{ accentColor: '#ffa657' }} />
                <span>Досвет Ламбертом</span>
              </label>
            </div>
          </>
        )}
      </div>

      <div style={{ flex: 1, height: '100%', position: 'relative' }}>
        {data ? (
          <CanvasMulti
            data={data}
            slotIndices={slotIndices}
            mode="timeline"
            segT={segT}
            activeMask={[0, 1, 1, 0]}
            showHeatmap={showHeatmap}
            wireframe={wireframe}
            lighting={lighting}
          />
        ) : (
          <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#484f58', gap: '16px' }}>
            <div style={{ fontSize: '64px' }}>🌊</div>
            <div style={{ fontSize: '18px', fontWeight: '500' }}>Загрузите 2 фото и постройте ARAP-морф</div>
          </div>
        )}
      </div>
    </div>
  );
}
