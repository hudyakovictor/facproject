import React from 'react';

export default function Controls({
  progress,
  setProgress,
  isPlaying,
  setIsPlaying,
  showLandmarks,
  setShowLandmarks,
  showHeatmap,
  setShowHeatmap,
  showUVDiff = false,
  setShowUVDiff = () => {},
  wireframe,
  setWireframe,
  lighting,
  setLighting,
  sequenceCount = 2,
  blendMode = 'timeline',
  setBlendMode = () => {},
  blendWeights = [1, 0, 0, 0],
  setBlendWeights = () => {},
  metadata,
  onDownloadGif,
  gifLoading,
  onDownloadWebm,
  webmLoading
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      
      {/* 1. СЛАЙДЕР МОРФИНГА */}
      <div style={{
        background: '#161b22',
        border: '1px solid #30363d',
        borderRadius: '12px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#58a6ff' }}>Лицо A (0%)</span>
          <span style={{ fontSize: '15px', fontWeight: 'bold', color: '#00ffaa' }}>{Math.round(progress * 100)}%</span>
          <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#f778ba' }}>{sequenceCount > 2 ? `A → B → ${String.fromCharCode(65 + sequenceCount - 1)}` : 'Лицо B (100%)'}</span>
        </div>

        <input
          type="range"
          min="0"
          max="1"
          step="0.002"
          value={progress}
          onChange={(e) => {
            setIsPlaying(false);
            setProgress(parseFloat(e.target.value));
          }}
          style={{
            width: '100%',
            accentColor: '#00ffaa',
            cursor: 'pointer'
          }}
        />

        {/* Быстрые пресеты */}
        <div style={{ display: 'flex', gap: '8px' }}>
          {[0, 0.25, 0.5, 0.75, 1.0].map((v) => (
            <button
              key={v}
              onClick={() => {
                setIsPlaying(false);
                setProgress(v);
              }}
              style={{
                flex: 1,
                padding: '4px 0',
                background: progress === v ? '#238636' : '#21262d',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#fff',
                fontSize: '11px',
                cursor: 'pointer'
              }}
            >
              {v * 100}%
            </button>
          ))}
        </div>
      </div>

      {sequenceCount >= 3 && (
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#d2a8ff' }}>🧬 Multi-face blend</span>
            <select value={blendMode} onChange={(event) => setBlendMode(event.target.value)} style={{ background: '#21262d', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: '5px', padding: '3px', fontSize: '10px' }}>
              <option value="timeline">Timeline spline</option>
              <option value="blend">Barycentric blend</option>
            </select>
          </div>
          {blendMode === 'blend' ? (
            <>
              <div style={{ fontSize: '10px', color: '#8b949e' }}>Одновременный blend: веса нормализуются к сумме 1. Треугольник для 3 лиц, тетраэдр для 4.</div>
              {Array.from({ length: sequenceCount }, (_, index) => (
                <label key={index} style={{ display: 'grid', gridTemplateColumns: '48px 1fr 38px', alignItems: 'center', gap: '7px', fontSize: '11px', color: '#c9d1d9' }}>
                  <span style={{ color: ['#1f6feb', '#ab7df8', '#f0883e', '#3fb950'][index] }}>Face {String.fromCharCode(65 + index)}</span>
                  <input type="range" min="0" max="1" step="0.01" value={blendWeights[index] || 0} onChange={(event) => { const next = [...blendWeights]; next[index] = parseFloat(event.target.value); setBlendWeights(next); }} style={{ accentColor: ['#1f6feb', '#ab7df8', '#f0883e', '#3fb950'][index] }} />
                  <span style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{Math.round((blendWeights[index] || 0) * 100)}%</span>
                </label>
              ))}
              <div style={{ fontSize: '10px', color: '#00ffaa' }}>Σ {blendWeights.slice(0, sequenceCount).reduce((sum, value) => sum + Number(value || 0), 0).toFixed(2)} → автоматически нормализуется</div>
            </>
          ) : <div style={{ fontSize: '10px', color: '#8b949e' }}>Плавная Catmull–Rom траектория проходит через все keyframes.</div>}
        </div>
      )}

      {/* 2. КНОПКА АВТОАНИМАЦИИ И ЭКСПОРТА GIF */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          style={{
            padding: '12px',
            background: isPlaying ? '#da3633' : '#238636',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontWeight: 'bold',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            transition: 'background 0.2s'
          }}
        >
          <span>{isPlaying ? '⏸ Остановить анимацию' : '▶️ Автоматический морфинг (A ↔ B)'}</span>
        </button>

        <button
          onClick={onDownloadGif}
          disabled={gifLoading || webmLoading}
          style={{
            padding: '10px',
            background: '#1f6feb',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontWeight: 'bold',
            cursor: gifLoading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            fontSize: '13px'
          }}
        >
          <span>{gifLoading ? '⏳ Рендеринг GIF...' : '📥 Скачать 3D Morphing GIF'}</span>
        </button>

        <button
          onClick={onDownloadWebm}
          disabled={webmLoading || gifLoading}
          title="Записать 4 секунды анимации с 3D-канваса в WebM"
          style={{
            padding: '10px',
            background: '#8957e5',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontWeight: 'bold',
            cursor: webmLoading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            fontSize: '13px'
          }}
        >
          <span>{webmLoading ? '⏳ Идёт запись 60 кадров...' : '🎬 Записать MP4 / WebM (60 кадров)'}</span>
        </button>
      </div>

      {/* 3. ОПЦИИ И СЛОИ */}
      <div style={{
        background: '#161b22',
        border: '1px solid #30363d',
        borderRadius: '12px',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px'
      }}>
        <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#8b949e', textTransform: 'uppercase' }}>
          Слои визуализации
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showLandmarks}
            onChange={(e) => setShowLandmarks(e.target.checked)}
            style={{ accentColor: '#00ffaa' }}
          />
          <span>Показать 106 3D ориентиров лица</span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showHeatmap}
            onChange={(e) => setShowHeatmap(e.target.checked)}
            style={{ accentColor: '#ff7b72' }}
          />
          <span>Тепловая карта анатомической разницы</span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showUVDiff}
            onChange={(e) => setShowUVDiff(e.target.checked)}
            style={{ accentColor: '#ffb86c' }}
          />
          <span>UV Diff текстур (пигментация и морщины)</span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={wireframe}
            onChange={(e) => setWireframe(e.target.checked)}
            style={{ accentColor: '#79c0ff' }}
          />
          <span>Режим 3D-полигональной сетки</span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={lighting}
            onChange={(e) => setLighting(e.target.checked)}
            style={{ accentColor: '#ffa657' }}
          />
          <span>Досвет Ламбертом (выпуклость, но цвет отличается от фото)</span>
        </label>
      </div>

      {/* 4. ИНФОРМАЦИЯ О ВЫРАВНИВАНИИ */}
      {metadata && (
        <div style={{
          background: 'rgba(56, 139, 253, 0.08)',
          border: '1px solid rgba(56, 139, 253, 0.3)',
          borderRadius: '8px',
          padding: '12px',
          fontSize: '12px',
          color: '#8b949e',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <div style={{ color: '#58a6ff', fontWeight: 'bold' }}>✓ Каноническое выравнивание в (0°, 0°, 0°)</div>
          {metadata.photo_a_yaw !== undefined && <div>Исходный ракурс A: <b>{metadata.photo_a_yaw > 0 ? `+${metadata.photo_a_yaw}°` : `${metadata.photo_a_yaw}°`}</b></div>}
          {metadata.photo_b_yaw !== undefined && <div>Исходный ракурс B: <b>{metadata.photo_b_yaw > 0 ? `+${metadata.photo_b_yaw}°` : `${metadata.photo_b_yaw}°`}</b></div>}
          {metadata.mean_3d_difference !== undefined && <div>Средняя 3D-девиация: <b>{metadata.mean_3d_difference}</b></div>}
          {metadata.mean_adjacent_difference !== undefined && <div>Средняя по соседним keyframes: <b>{metadata.mean_adjacent_difference}</b></div>}
          {metadata.method && <div>Траектория: <b>{metadata.method}</b></div>}
          {metadata.temporal_drift && <div>Temporal drift: <b>{metadata.temporal_drift.velocity_l2_per_year}</b> / год; anomalies: <b>{metadata.temporal_drift.anomaly_keyframes?.length || 0}</b></div>}
          {metadata.max_3d_difference !== undefined && (
            <div>Макс. 3D-девиация: <b>{metadata.max_3d_difference}</b></div>
          )}
          {metadata.morphability_score !== undefined && (
            <div>Morphability Score: <b style={{ color: '#00ffaa' }}>{metadata.morphability_score}%</b></div>
          )}
          {metadata.cosine_similarity !== undefined && (
            <div>Cosine Similarity: <b style={{ color: '#58a6ff' }}>{metadata.cosine_similarity}</b></div>
          )}
          <div>Текстура: <b>HD UV (uv_module / 1024px)</b></div>
        </div>
      )}

      {/* 5. ЛЕГЕНДА ГОРЯЧИХ КЛАВИШ */}
      <details style={{
        background: '#161b22',
        border: '1px solid #30363d',
        borderRadius: '8px',
        padding: '10px 14px',
        fontSize: '12px',
        color: '#8b949e'
      }}>
        <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#58a6ff' }}>
          ⌨ Горячие клавиши
        </summary>
        <ul style={{ margin: '8px 0 0', paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <li><kbd style={kbdStyle}>Space</kbd> — пуск / пауза анимации</li>
          <li><kbd style={kbdStyle}>←</kbd> / <kbd style={kbdStyle}>→</kbd> — шаг морфа ±5%</li>
          <li><kbd style={kbdStyle}>R</kbd> — сброс на середину (50%)</li>
          <li><kbd style={kbdStyle}>W</kbd> — вкл / выкл полигональную сетку</li>
          <li><kbd style={kbdStyle}>0</kbd> / <kbd style={kbdStyle}>1</kbd> — чистое лицо A / B</li>
        </ul>
      </details>

    </div>
  );
}

const kbdStyle = {
  background: '#21262d',
  border: '1px solid #30363d',
  borderRadius: '4px',
  padding: '1px 6px',
  fontSize: '11px',
  color: '#e6edf3',
  fontFamily: 'monospace',
};
