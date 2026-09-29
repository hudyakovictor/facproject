import React, { useState, useMemo, useCallback } from 'react';
import DropZone from './DropZone';
import CanvasMulti from './CanvasMulti';
import TriangleBarycentricPicker from './TriangleBarycentricPicker';

const SLOT_COLORS = ['#58a6ff', '#f778ba', '#d29922', '#3fb950'];

/**
 * 🧬 Multi-Face Blend — barycentric-блендинг 3–4 лиц через общий эндпоинт
 * /api/morph-multi. V = Σ wᵢ·Vᵢ, Σwᵢ = 1. Для 3 лиц — интерактивный
 * треугольный барицентрический пикер (M7); для 4 — упрощённые линейные
 * нормированные слайдеры (честная альтернатива тетраэдральному UI, см.
 * docs/30_MORPHING_ANALYSES.md M7).
 */
export default function MultiFaceBlend() {
  const [faceCount, setFaceCount] = useState(3); // 3 или 4
  const [photos, setPhotos] = useState([null, null, null, null]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null); // ответ /api/morph-multi
  const [weights3, setWeights3] = useState([1 / 3, 1 / 3, 1 / 3]);
  const [weights4Raw, setWeights4Raw] = useState([1, 1, 1, 1]);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [lighting, setLighting] = useState(false);

  const setPhotoAt = (idx, file) => {
    setPhotos((prev) => {
      const next = [...prev];
      next[idx] = file;
      return next;
    });
  };

  const activeSlots = photos.slice(0, faceCount);
  const canProcess = activeSlots.every((p) => !!p);

  const handleProcess = async () => {
    if (!canProcess) {
      setError(`Загрузите все ${faceCount} фото`);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      activeSlots.forEach((file) => formData.append('photos', file));
      const res = await fetch('/api/morph-multi', { method: 'POST', body: formData });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errJson.detail || 'Не удалось выполнить multi-морфинг');
      }
      const json = await res.json();
      setData(json);
      setWeights3([1 / 3, 1 / 3, 1 / 3]);
      setWeights4Raw([1, 1, 1, 1]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // Нормированные веса для шейдера (всегда длины 4, лишние слоты = 0)
  const weights = useMemo(() => {
    if (faceCount === 3) return [...weights3, 0];
    const sum = weights4Raw.reduce((a, b) => a + b, 0) || 1;
    return weights4Raw.map((w) => w / sum);
  }, [faceCount, weights3, weights4Raw]);

  const slotIndices = useMemo(() => [0, 1, 2, faceCount === 4 ? 3 : 0], [faceCount]);
  const activeMask = useMemo(() => [1, 1, 1, faceCount === 4 ? 1 : 0], [faceCount]);

  // Максимальная попарная дистанция среди лиц с заметным весом (>5%) — живая метрика смеси
  const dominantPairMax = useMemo(() => {
    if (!data?.metadata?.pairwise_mean_dist) return null;
    const active = weights.map((w, i) => (w > 0.05 ? i : -1)).filter((i) => i >= 0 && i < data.count);
    let max = 0;
    for (let i = 0; i < active.length; i++) {
      for (let j = i + 1; j < active.length; j++) {
        max = Math.max(max, data.metadata.pairwise_mean_dist[active[i]][active[j]]);
      }
    }
    return active.length >= 2 ? max : null;
  }, [data, weights]);

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%' }}>
      <div style={{
        width: '380px', minWidth: '380px', height: '100%', background: '#0d1117',
        borderRight: '1px solid #30363d', padding: '24px', boxSizing: 'border-box',
        overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '18px',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '22px' }}>🧬</span>
            <h2 style={{ margin: 0, fontSize: '17px', fontWeight: 'bold' }}>Multi-Face Blend</h2>
          </div>
          <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#8b949e' }}>
            V(w) = Σ wᵢ·Vᵢ, Σwᵢ = 1. Барицентрический блендинг {faceCount} лиц.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          {[3, 4].map((n) => (
            <button
              key={n}
              onClick={() => setFaceCount(n)}
              disabled={!!data}
              title={data ? 'Пересоберите смесь заново, чтобы сменить число лиц' : ''}
              style={{
                flex: 1, padding: '8px', borderRadius: '8px',
                background: faceCount === n ? '#238636' : '#21262d',
                border: '1px solid #30363d', color: '#fff', fontSize: '13px',
                cursor: data ? 'not-allowed' : 'pointer', fontWeight: 'bold',
              }}
            >
              {n} лица
            </button>
          ))}
        </div>

        {!data && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              {Array.from({ length: faceCount }).map((_, idx) => (
                <DropZone
                  key={idx}
                  label={`Лицо ${String.fromCharCode(65 + idx)}`}
                  photo={photos[idx]}
                  onPhotoSelect={(f) => setPhotoAt(idx, f)}
                  badgeColor={SLOT_COLORS[idx]}
                />
              ))}
            </div>
            <button
              onClick={handleProcess}
              disabled={loading || !canProcess}
              style={{
                padding: '12px', background: loading ? '#30363d' : '#238636', color: '#fff',
                border: 'none', borderRadius: '8px', fontWeight: 'bold', fontSize: '14px',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? '⏳ Реконструкция N лиц...' : `🚀 Собрать смесь из ${faceCount} лиц`}
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
              onClick={() => { setData(null); setError(null); }}
              style={{ padding: '8px', background: '#21262d', border: '1px solid #30363d', borderRadius: '8px', color: '#c9d1d9', fontSize: '12px', cursor: 'pointer' }}
            >
              ↺ Новая смесь (сменить фото)
            </button>

            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'center' }}>
              <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 'bold', textTransform: 'uppercase', alignSelf: 'flex-start' }}>
                Барицентрический вес
              </div>
              {faceCount === 3 ? (
                <TriangleBarycentricPicker weights={weights3} onChange={setWeights3} labels={['A', 'B', 'C']} />
              ) : (
                <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {weights4Raw.map((w, idx) => (
                    <div key={idx}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                        <span style={{ color: SLOT_COLORS[idx] }}>Лицо {String.fromCharCode(65 + idx)}</span>
                        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{(weights[idx] * 100).toFixed(0)}%</span>
                      </div>
                      <input
                        type="range" min="0" max="1" step="0.01" value={w}
                        onChange={(e) => {
                          const next = [...weights4Raw];
                          next[idx] = parseFloat(e.target.value);
                          setWeights4Raw(next);
                        }}
                        style={{ width: '100%', accentColor: SLOT_COLORS[idx] }}
                      />
                    </div>
                  ))}
                  <div style={{ fontSize: '10px', color: '#6e7681' }}>
                    Упрощённый тетраэдральный UI: 4 независимых слайдера, автонормировка суммы к 100%.
                  </div>
                </div>
              )}
            </div>

            {dominantPairMax !== null && (
              <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '10px 14px', fontSize: '12px', color: '#8b949e' }}>
                Макс. попарная дистанция среди лиц с весом &gt;5%: <b style={{ color: '#e6edf3' }}>{dominantPairMax.toFixed(4)}</b>
              </div>
            )}

            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#8b949e', textTransform: 'uppercase' }}>Слои</div>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
                <input type="checkbox" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} style={{ accentColor: '#ff7b72' }} />
                <span>Heatmap разброса вершин между лицами</span>
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
            mode="blend"
            weights={weights}
            activeMask={activeMask}
            showHeatmap={showHeatmap}
            wireframe={wireframe}
            lighting={lighting}
          />
        ) : (
          <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#484f58', gap: '16px' }}>
            <div style={{ fontSize: '64px' }}>🧬</div>
            <div style={{ fontSize: '18px', fontWeight: '500' }}>Загрузите {faceCount} фото и соберите барицентрическую смесь</div>
          </div>
        )}
      </div>
    </div>
  );
}
