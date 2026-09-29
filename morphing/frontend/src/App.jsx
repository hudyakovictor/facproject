import React, { useState, useEffect, useCallback, useMemo } from 'react';
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

  const [progress, setProgress] = useState(0.0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [lighting, setLighting] = useState(false);

  // ── KEYBOARD SHORTCUTS ──────────────────────────────────────────────────
  useEffect(() => {
    const handleKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      switch (e.key) {
        case ' ':
          e.preventDefault();
          setIsPlaying((prev) => !prev);
          break;
        case 'ArrowRight':
          e.preventDefault();
          setProgress((prev) => Math.min(1.0, parseFloat((prev + 0.05).toFixed(2))));
          break;
        case 'ArrowLeft':
          e.preventDefault();
          setProgress((prev) => Math.max(0.0, parseFloat((prev - 0.05).toFixed(2))));
          break;
        case 'r':
        case 'R':
          setProgress(0.5);
          setIsPlaying(false);
          break;
        case 'w':
        case 'W':
          setWireframe((prev) => !prev);
          break;
        case '0':
          setProgress(0.0);
          break;
        case '1':
          setProgress(1.0);
          break;
        default:
          break;
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  // ── SWAP A ↔ B ──────────────────────────────────────────────────────────
  const swapFaces = useCallback(() => {
    if (!morphData) return;
    setMorphData((prev) => ({
      ...prev,
      vertices_a: prev.vertices_b,
      vertices_b: prev.vertices_a,
      texture_a_base64: prev.texture_b_base64,
      texture_b_base64: prev.texture_a_base64,
      landmarks_a: prev.landmarks_b,
      landmarks_b: prev.landmarks_a,
      metadata: { ...prev.metadata },
    }));
    setProgress((prev) => 1.0 - prev);
  }, [morphData]);

  // ── LIVE METRICS (вычисляется на клиенте, без запросов) ─────────────────
  const liveMetrics = useMemo(() => {
    if (!morphData?.vertices_a || !morphData?.vertices_b) return null;
    const a = morphData.vertices_a;
    const b = morphData.vertices_b;
    const n = a.length / 3;
    const THRESHOLD = 0.025;
    let sumDist = 0, maxDist = 0, aboveThreshold = 0;
    for (let i = 0; i < a.length; i += 3) {
      const dx = a[i] - b[i];
      const dy = a[i + 1] - b[i + 1];
      const dz = a[i + 2] - b[i + 2];
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      sumDist += d;
      if (d > maxDist) maxDist = d;
      if (d > THRESHOLD) aboveThreshold++;
    }
    return {
      euclidean: (sumDist / n).toFixed(5),
      maxDelta: maxDist.toFixed(5),
      pctAbove: ((aboveThreshold / n) * 100).toFixed(1),
      totalVerts: n.toLocaleString(),
    };
  }, [morphData]);

  // ── GIF DOWNLOAD ────────────────────────────────────────────────────────
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

  // ── AUTO PLAY ───────────────────────────────────────────────────────────
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

  // ── PROCESS ─────────────────────────────────────────────────────────────
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
      const response = await fetch('/api/morph-pair', { method: 'POST', body: formData });
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

  // ── RENDER ──────────────────────────────────────────────────────────────
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

      {/* ── ЛЕВАЯ ПАНЕЛЬ ── */}
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
            GPU-морфинг 3DMM-формы и HD UV-текстур. Shortcuts: Space / ←→ / R / W / 0 / 1
          </p>
        </div>

        {/* Дроп-зоны + кнопка Swap */}
        <div style={{ position: 'relative' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <DropZone label="Фото A (0%)" photo={photoA} onPhotoSelect={setPhotoA} badgeColor="#1f6feb" />
            <DropZone label="Фото B (100%)" photo={photoB} onPhotoSelect={setPhotoB} badgeColor="#ab7df8" />
          </div>
          {/* Swap A↔B */}
          <button
            onClick={swapFaces}
            disabled={!morphData}
            title="Поменять A и B местами"
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              background: morphData ? '#238636' : '#30363d',
              border: '2px solid #0d1117',
              color: '#fff',
              fontSize: '14px',
              cursor: morphData ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.2s, transform 0.3s',
              zIndex: 10,
            }}
          >
            ⇄
          </button>
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

        {/* Live Metrics */}
        {liveMetrics && (
          <div style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '12px',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '8px',
          }}>
            <div style={{ fontSize: '11px', color: '#8b949e', marginBottom: '4px', gridColumn: '1/-1', fontWeight: 'bold', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              📐 Live Metrics
            </div>
            {[
              { label: 'Mean Dist', value: liveMetrics.euclidean },
              { label: 'Max Delta', value: liveMetrics.maxDelta },
              { label: '% > threshold', value: `${liveMetrics.pctAbove}%` },
              { label: 'Вершин', value: liveMetrics.totalVerts },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: '#0d1117', borderRadius: '6px', padding: '6px 10px' }}>
                <div style={{ fontSize: '10px', color: '#8b949e' }}>{label}</div>
                <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#e6edf3', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Controls */}
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
            lighting={lighting}
            setLighting={setLighting}
            metadata={morphData.metadata}
            onDownloadGif={handleDownloadGif}
            gifLoading={gifLoading}
          />
        )}

      </div>

      {/* ── ПРАВАЯ ОБЛАСТЬ: 3D СЦЕНА ── */}
      <div style={{ flex: 1, height: '100%', position: 'relative' }}>
        {morphData ? (
          <Canvas3D
            morphData={morphData}
            progress={progress}
            showLandmarks={showLandmarks}
            showHeatmap={showHeatmap}
            wireframe={wireframe}
            lighting={lighting}
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
              развернёт HD UV-текстуры и соберёт GPU-морфинг.
            </div>
            <div style={{ fontSize: '12px', color: '#30363d', marginTop: '8px' }}>
              Space · ←→ · R · W · 0 · 1
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
