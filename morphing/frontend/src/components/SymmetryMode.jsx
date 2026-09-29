import React, { useState } from 'react';
import Canvas3D from './Canvas3D';
import DropZone from './DropZone';

const ZONE_LABELS = {
  forehead: 'Лоб',
  left_eye: 'Л. глаз',
  right_eye: 'П. глаз',
  nose: 'Нос',
  left_cheek: 'Л. щека',
  right_cheek: 'П. щека',
  mouth_chin: 'Рот/Подб.',
};

function scoreColor(v) {
  if (v >= 75) return '#3fb950';
  if (v >= 50) return '#d29922';
  if (v >= 25) return '#f0883e';
  return '#f85149';
}

/**
 * 🪞 Facial Symmetry Analysis — отражает 3D-форму по срединной плоскости,
 * находит зеркальные соответствия (backend: scipy.spatial.cKDTree) и красит
 * heatmap по локальной асимметрии. Переиспользует Canvas3D/MorphShader:
 * vertices_b от бэкенда — не "второе лицо", а зеркальное соответствие
 * исходной формы, поэтому "diff" heatmap уже готовой инфраструктуры = карта
 * асимметрии без единой новой строчки шейдера.
 */
export default function SymmetryMode() {
  const [photo, setPhoto] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [mirrorPreview, setMirrorPreview] = useState(0); // 0 = оригинал, 1 = полное зеркало

  const handleProcess = async () => {
    if (!photo) { setError('Загрузите фото'); return; }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('photo', photo);
      const res = await fetch('/api/symmetry', { method: 'POST', body: formData });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errJson.detail || 'Не удалось выполнить анализ симметрии');
      }
      const json = await res.json();
      setData(json);
      setMirrorPreview(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const meta = data?.metadata;

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%' }}>
      <div style={{
        width: '380px', minWidth: '380px', height: '100%', background: '#0d1117',
        borderRight: '1px solid #30363d', padding: '24px', boxSizing: 'border-box',
        overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '18px',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '22px' }}>🪞</span>
            <h2 style={{ margin: 0, fontSize: '17px', fontWeight: 'bold' }}>Facial Symmetry</h2>
          </div>
          <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#8b949e' }}>
            Отражение по x=0 + ближайшее соответствие (cKDTree) → heatmap локальной асимметрии.
          </p>
        </div>

        {!data && (
          <>
            <DropZone label="Фото" photo={photo} onPhotoSelect={setPhoto} badgeColor="#d2a8ff" />
            <button
              onClick={handleProcess}
              disabled={loading || !photo}
              style={{ padding: '12px', background: loading ? '#30363d' : '#238636', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 'bold', fontSize: '14px', cursor: loading ? 'not-allowed' : 'pointer' }}
            >
              {loading ? '⏳ Анализ...' : '🚀 Анализировать симметрию'}
            </button>
          </>
        )}

        {error && (
          <div style={{ background: 'rgba(248, 81, 73, 0.15)', border: '1px solid #f85149', borderRadius: '8px', padding: '10px 14px', color: '#ff7b72', fontSize: '13px' }}>
            ⚠️ {error}
          </div>
        )}

        {data && meta && (
          <>
            <button
              onClick={() => { setData(null); setError(null); }}
              style={{ padding: '8px', background: '#21262d', border: '1px solid #30363d', borderRadius: '8px', color: '#c9d1d9', fontSize: '12px', cursor: 'pointer' }}
            >
              ↺ Новое фото
            </button>

            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '10px 14px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '12px', color: '#8b949e' }}>Symmetry Score</span>
              <span style={{ fontSize: '22px', fontWeight: 'bold', color: scoreColor(meta.global_symmetry_score) }}>
                {meta.global_symmetry_score}/100
              </span>
            </div>

            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 'bold', textTransform: 'uppercase' }}>Зоны</div>
              {Object.entries(meta.zones).map(([key, val]) => (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '64px', fontSize: '11px', color: '#8b949e', flexShrink: 0 }}>{ZONE_LABELS[key] || key}</div>
                  <div style={{ flex: 1, height: '6px', background: '#21262d', borderRadius: '999px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${val.symmetry_score}%`, background: scoreColor(val.symmetry_score), borderRadius: '999px' }} />
                  </div>
                  <div style={{ width: '38px', fontSize: '11px', color: scoreColor(val.symmetry_score), textAlign: 'right' }}>{val.symmetry_score.toFixed(0)}%</div>
                </div>
              ))}
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
                <span style={{ color: '#8b949e' }}>Оригинал ↔ Зеркало (превью)</span>
                <span style={{ fontVariantNumeric: 'tabular-nums' }}>{Math.round(mirrorPreview * 100)}%</span>
              </div>
              <input type="range" min="0" max="1" step="0.01" value={mirrorPreview}
                onChange={(e) => setMirrorPreview(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: '#d2a8ff' }} />
            </div>

            <div style={{ fontSize: '10.5px', color: '#6e7681', lineHeight: 1.5 }}>
              ⚠️ {meta.note}
            </div>
          </>
        )}
      </div>

      <div style={{ flex: 1, height: '100%', position: 'relative' }}>
        {data ? (
          <Canvas3D
            morphData={data}
            progress={mirrorPreview}
            showLandmarks={false}
            showHeatmap
            heatmapSource="diff"
            wireframe={false}
            lighting={false}
          />
        ) : (
          <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#484f58', gap: '16px' }}>
            <div style={{ fontSize: '64px' }}>🪞</div>
            <div style={{ fontSize: '18px', fontWeight: '500' }}>Загрузите одно фото для анализа фациальной симметрии</div>
          </div>
        )}
      </div>
    </div>
  );
}
