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
  wireframe,
  setWireframe,
  metadata,
  onDownloadGif,
  gifLoading
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
          <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#f778ba' }}>Лицо B (100%)</span>
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
          disabled={gifLoading}
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
            checked={wireframe}
            onChange={(e) => setWireframe(e.target.checked)}
            style={{ accentColor: '#79c0ff' }}
          />
          <span>Режим 3D-полигональной сетки</span>
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
          <div>Исходный ракурс A: <b>{metadata.photo_a_yaw > 0 ? `+${metadata.photo_a_yaw}°` : `${metadata.photo_a_yaw}°`}</b></div>
          <div>Исходный ракурс B: <b>{metadata.photo_b_yaw > 0 ? `+${metadata.photo_b_yaw}°` : `${metadata.photo_b_yaw}°`}</b></div>
          <div>Средняя 3D-девиация: <b>{metadata.mean_3d_difference}</b></div>
          <div>Текстура: <b>HD UV (uv_module / 1024px)</b></div>
        </div>
      )}

    </div>
  );
}
