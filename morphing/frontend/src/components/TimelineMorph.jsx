import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import CanvasMulti from './CanvasMulti';

/**
 * 🎬 Timeline A→B→C→D — цепочка N фото со сплайновой (Catmull-Rom)
 * интерполяцией формы между всеми контрольными точками (M8). Использует тот
 * же /api/morph-multi эндпоинт, что и Multi-Face Blend — тут порядок фото
 * важен (control points сплайна), а не веса блендинга.
 *
 * Реализация нарочно не требует от бэкенда предрасчитывать десятки
 * промежуточных кадров: Catmull-Rom считается на GPU по 4 соседним
 * контрольным точкам текущего сегмента (см. MultiMorphShader.js) — при
 * пересечении playhead границы сегмента меняются только 4 атрибута буфера.
 */
export default function TimelineMorph() {
  const [photos, setPhotos] = useState([]); // File[]
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [playheadT, setPlayheadT] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [lighting, setLighting] = useState(false);
  const fileInputRef = useRef(null);

  const addFiles = (fileList) => {
    const files = Array.from(fileList).slice(0, 6 - photos.length);
    setPhotos((prev) => [...prev, ...files].slice(0, 6));
  };

  const removeAt = (idx) => setPhotos((prev) => prev.filter((_, i) => i !== idx));
  const moveAt = (idx, dir) => {
    setPhotos((prev) => {
      const next = [...prev];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    });
  };

  const handleProcess = async () => {
    if (photos.length < 2) {
      setError('Загрузите минимум 2 фото (рекомендуется 3–6 для заметной сплайновой траектории)');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      photos.forEach((file) => formData.append('photos', file));
      const res = await fetch('/api/morph-multi', { method: 'POST', body: formData });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errJson.detail || 'Не удалось построить timeline');
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

  // Autoplay: пинг-понг по всей временной шкале
  useEffect(() => {
    if (!isPlaying || !data) return;
    let forward = true;
    const interval = setInterval(() => {
      setPlayheadT((p) => {
        if (p >= maxT) forward = false;
        if (p <= 0) forward = true;
        const step = maxT > 0 ? maxT / 240 : 0;
        const next = forward ? p + step : p - step;
        return Math.max(0, Math.min(maxT, next));
      });
    }, 25);
    return () => clearInterval(interval);
  }, [isPlaying, data, maxT]);

  const { slotIndices, segT, segmentLabel } = useMemo(() => {
    if (!data) return { slotIndices: [0, 0, 1, 1], segT: 0, segmentLabel: '' };
    const n = data.count;
    const t = Math.max(0, Math.min(maxT, playheadT));
    const k = Math.min(Math.floor(t), Math.max(n - 2, 0));
    const localT = n > 1 ? t - k : 0;
    const p0 = Math.max(k - 1, 0);
    const p1 = k;
    const p2 = Math.min(k + 1, n - 1);
    const p3 = Math.min(k + 2, n - 1);
    return {
      slotIndices: [p0, p1, p2, p3],
      segT: localT,
      segmentLabel: n > 1 ? `Между фото ${p1 + 1} и ${p2 + 1} · t=${localT.toFixed(2)}` : 'Фото 1',
    };
  }, [data, playheadT, maxT]);

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%' }}>
      <div style={{
        width: '380px', minWidth: '380px', height: '100%', background: '#0d1117',
        borderRight: '1px solid #30363d', padding: '24px', boxSizing: 'border-box',
        overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '18px',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '22px' }}>🎬</span>
            <h2 style={{ margin: 0, fontSize: '17px', fontWeight: 'bold' }}>Timeline A→B→C→D</h2>
          </div>
          <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#8b949e' }}>
            Catmull-Rom интерполяция формы через N упорядоченных лиц. Полезно для
            хронологии изменений лица (криминалистика/документальные кейсы).
          </p>
        </div>

        {!data && (
          <>
            <input ref={fileInputRef} type="file" accept="image/*" multiple style={{ display: 'none' }}
              onChange={(e) => e.target.files && addFiles(e.target.files)} />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={photos.length >= 6}
              style={{ padding: '10px', background: '#21262d', border: '1.5px dashed #30363d', borderRadius: '8px', color: '#c9d1d9', fontSize: '13px', cursor: 'pointer' }}
            >
              📷 Добавить фото ({photos.length}/6)
            </button>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {photos.map((file, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '6px 10px' }}>
                  <img src={URL.createObjectURL(file)} alt="" style={{ width: '32px', height: '32px', objectFit: 'cover', borderRadius: '4px' }} />
                  <span style={{ flex: 1, fontSize: '12px', color: '#c9d1d9', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    #{idx + 1} {file.name}
                  </span>
                  <button onClick={() => moveAt(idx, -1)} disabled={idx === 0} style={miniBtnStyle}>↑</button>
                  <button onClick={() => moveAt(idx, 1)} disabled={idx === photos.length - 1} style={miniBtnStyle}>↓</button>
                  <button onClick={() => removeAt(idx)} style={{ ...miniBtnStyle, color: '#ff7b72' }}>✕</button>
                </div>
              ))}
            </div>

            <button
              onClick={handleProcess}
              disabled={loading || photos.length < 2}
              style={{ padding: '12px', background: loading ? '#30363d' : '#238636', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 'bold', fontSize: '14px', cursor: loading ? 'not-allowed' : 'pointer' }}
            >
              {loading ? '⏳ Реконструкция цепочки...' : `🚀 Построить timeline из ${photos.length} фото`}
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
              ↺ Новый timeline (сменить фото)
            </button>

            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span style={{ color: '#8b949e' }}>{segmentLabel}</span>
                <span style={{ color: '#00ffaa', fontWeight: 'bold' }}>{playheadT.toFixed(2)} / {maxT.toFixed(2)}</span>
              </div>
              <input type="range" min="0" max={maxT} step="0.005" value={playheadT}
                onChange={(e) => { setIsPlaying(false); setPlayheadT(parseFloat(e.target.value)); }}
                style={{ width: '100%', accentColor: '#00ffaa' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                {Array.from({ length: data.count }).map((_, i) => (
                  <button key={i} onClick={() => { setIsPlaying(false); setPlayheadT(i); }}
                    style={{ padding: '3px 8px', background: Math.round(playheadT) === i ? '#238636' : '#21262d', border: '1px solid #30363d', borderRadius: '6px', color: '#fff', fontSize: '10.5px', cursor: 'pointer' }}>
                    {i + 1}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setIsPlaying((p) => !p)}
                style={{ padding: '10px', background: isPlaying ? '#da3633' : '#238636', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer' }}
              >
                {isPlaying ? '⏸ Остановить' : '▶️ Воспроизвести всю хронологию'}
              </button>
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
            <div style={{ fontSize: '64px' }}>🎬</div>
            <div style={{ fontSize: '18px', fontWeight: '500' }}>Загрузите 2–6 фото по порядку и постройте временную траекторию</div>
          </div>
        )}
      </div>
    </div>
  );
}

const miniBtnStyle = {
  width: '22px', height: '22px', background: '#21262d', border: '1px solid #30363d',
  borderRadius: '4px', color: '#c9d1d9', fontSize: '11px', cursor: 'pointer', flexShrink: 0,
};
