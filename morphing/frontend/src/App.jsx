import React, { useState, useEffect } from 'react';
import Canvas3D from './components/Canvas3D';
import DropZone from './components/DropZone';
import Controls from './components/Controls';

export default function App() {
  const [photoA, setPhotoA] = useState(null);
  const [photoB, setPhotoB] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [morphData, setMorphData] = useState(null);
  const [gifLoading, setGifLoading] = useState(false);

  // Скачивание GIF
  const handleDownloadGif = async () => {
    if (!photoA || !photoB) return;
    setGifLoading(true);
    try {
      const formData = new FormData();
      formData.append('photo_a', photoA);
      formData.append('photo_b', photoB);
      const res = await fetch('/api/export-gif', { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Ошибка генерации GIF');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `3d_morph_${Date.now()}.gif`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      alert('Ошибка при скачивании GIF: ' + e.message);
    } finally {
      setGifLoading(false);
    }
  };

  // Состояния интерактивности
  const [progress, setProgress] = useState(0.0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [wireframe, setWireframe] = useState(false);

  // Цикл плавной автоанимации
  useEffect(() => {
    if (!isPlaying) return;
    let forward = true;
    const interval = setInterval(() => {
      setProgress((p) => {
        if (p >= 1.0) forward = false;
        if (p <= 0.0) forward = true;
        const next = forward ? p + 0.015 : p - 0.015;
        return Math.max(0.0, Math.min(1.0, next));
      });
    }, 25);
    return () => clearInterval(interval);
  }, [isPlaying]);

  // Запуск 3D-реконструкции и выравнивания
  const handleProcess = async () => {
    if (!photoA || !photoB) {
      setError('Пожалуйста, выберите оба фото для морфинга.');
      return;
    }

    setLoading(true);
    setError(null);
    setIsPlaying(false);

    const formData = new FormData();
    formData.append('photo_a', photoA);
    formData.append('photo_b', photoB);

    try {
      const response = await fetch('/api/morph-pair', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errJson.detail || 'Не удалось выполнить реконструкцию');
      }

      const data = await response.json();
      setMorphData(data);
      setProgress(0.0);
    } catch (err) {
      setError(err.message || 'Ошибка соединения с бэкендом');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      width: '100vw',
      height: '100vh',
      background: '#0b0c10',
      color: '#e6edf3',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      overflow: 'hidden'
    }}>
      
      {/* ── ЛЕВАЯ ПАНЕЛЬ УПРАВЛЕНИЯ ── */}
      <div style={{
        width: '380px',
        minWidth: '380px',
        height: '100%',
        background: '#0d1117',
        borderRight: '1px solid #30363d',
        padding: '24px',
        boxSizing: 'border-box',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px'
      }}>
        
        {/* Заголовок */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '24px' }}>🎭</span>
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold' }}>3D Face Morphing</h2>
          </div>
          <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#8b949e' }}>
            Плавный GPU-морфинг формы и HD UV-текстур кожи с каноническим выравниванием в (0°, 0°, 0°).
          </p>
        </div>

        {/* Зоны загрузки двух фото */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <DropZone
            label="Фото A (0%)"
            photo={photoA}
            onPhotoSelect={setPhotoA}
            badgeColor="#1f6feb"
          />
          <DropZone
            label="Фото B (100%)"
            photo={photoB}
            onPhotoSelect={setPhotoB}
            badgeColor="#ab7df8"
          />
        </div>

        {/* Кнопка запуска */}
        <button
          onClick={handleProcess}
          disabled={loading || !photoA || !photoB}
          style={{
            padding: '12px',
            background: loading ? '#30363d' : '#238636',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            fontWeight: 'bold',
            fontSize: '14px',
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s',
          }}
        >
          {loading ? '⏳ Выравнивание в (0,0,0) и генерация HD UV...' : '🚀 Запустить 3D Morphing'}
        </button>

        {error && (
          <div style={{
            background: 'rgba(248, 81, 73, 0.15)',
            border: '1px solid #f85149',
            borderRadius: '8px',
            padding: '10px 14px',
            color: '#ff7b72',
            fontSize: '13px'
          }}>
            ⚠️ {error}
          </div>
        )}

        {/* Контролы морфинга (доступны после расчёта) */}
        {morphData && (
          <Controls
            progress={progress}
            setProgress={setProgress}
            isPlaying={isPlaying}
            setIsPlaying={setIsPlaying}
            showLandmarks={showLandmarks}
            setShowLandmarks={setShowLandmarks}
            showHeatmap={showHeatmap}
            setShowHeatmap={setShowHeatmap}
            wireframe={wireframe}
            setWireframe={setWireframe}
            metadata={morphData.metadata}
            onDownloadGif={handleDownloadGif}
            gifLoading={gifLoading}
          />
        )}

      </div>

      {/* ── ПРАВАЯ ОБЛАСТЬ: 3D THREE.JS СЦЕНА ── */}
      <div style={{ flex: 1, height: '100%', position: 'relative' }}>
        {morphData ? (
          <Canvas3D
            morphData={morphData}
            progress={progress}
            showLandmarks={showLandmarks}
            showHeatmap={showHeatmap}
            wireframe={wireframe}
          />
        ) : (
          <div style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#484f58',
            gap: '16px'
          }}>
            <div style={{ fontSize: '64px' }}>🗿</div>
            <div style={{ fontSize: '18px', fontWeight: '500' }}>
              Загрузите 2 фотографии лица и нажмите «Запустить 3D Morphing»
            </div>
            <div style={{ fontSize: '13px', maxWidth: '420px', textAlign: 'center', color: '#6e7681' }}>
              Нейросеть построит 3DMM-форму, выровняет оба черепа в канонические (0°, 0°, 0°), 
              развернёт улучшенные HD UV-текстуры (uv_module) и соберёт GPU-морфинг.
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
