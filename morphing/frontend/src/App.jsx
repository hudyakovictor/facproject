import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  const [webmLoading, setWebmLoading] = useState(false);
  // Данные специализированного эндпоинта /api/forensic-score (зональные identity-скоры)
  const [forensicData, setForensicData] = useState(null);
  const [forensicLoading, setForensicLoading] = useState(false);

  const [progress, setProgress] = useState(0.0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [lighting, setLighting] = useState(false);

  // Ссылка на <canvas> внутри Canvas3D для WebM-записи
  const canvasRef = useRef(null);

  // ── KEYBOARD SHORTCUTS ───────────────────────────────────────────
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

  // ── SWAP A ↔ B ────────────────────────────────────────────
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

  // ── LIVE METRICS (вычисляется на клиенте, без запросов) ──────────────
  const liveMetrics = useMemo(() => {
    if (!morphData?.vertices_a || !morphData?.vertices_b) return null;
    const a = morphData.vertices_a;
    const b = morphData.vertices_b;
    const n = a.length / 3;
    const THRESHOLD = 0.025;
    let sumDist = 0, maxDist = 0, aboveThreshold = 0;
    let dotAB = 0, normA = 0, normB = 0;
    for (let i = 0; i < a.length; i += 3) {
      const dx = a[i] - b[i];
      const dy = a[i + 1] - b[i + 1];
      const dz = a[i + 2] - b[i + 2];
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      sumDist += d;
      if (d > maxDist) maxDist = d;
      if (d > THRESHOLD) aboveThreshold++;
      dotAB += a[i] * b[i] + a[i + 1] * b[i + 1] + a[i + 2] * b[i + 2];
      normA += a[i] * a[i] + a[i + 1] * a[i + 1] + a[i + 2] * a[i + 2];
      normB += b[i] * b[i] + b[i + 1] * b[i + 1] + b[i + 2] * b[i + 2];
    }
    const meanDist = sumDist / n;
    const cosine = dotAB / (Math.sqrt(normA) * Math.sqrt(normB) + 1e-9);
    const morphability = Math.max(0, Math.min(100, (1.0 - meanDist / 0.15) * 100));
    return {
      euclidean: meanDist.toFixed(5),
      maxDelta: maxDist.toFixed(5),
      pctAbove: ((aboveThreshold / n) * 100).toFixed(1),
      totalVerts: n.toLocaleString(),
      cosine: cosine.toFixed(4),
      morphability: morphability.toFixed(1),
    };
  }, [morphData]);

  // ── GIF DOWNLOAD ───────────────────────────────────────────
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

  // ── WEBM RECORD (запись с canvas через MediaRecorder) ───────────────
  const handleDownloadWebm = useCallback(() => {
    // Находим <canvas> в DOM (тег r3f рисует сцену в <canvas>)
    const canvas = document.querySelector('canvas');
    if (!canvas) { alert('Канвас не найден. Запустите морфинг перед записью.'); return; }
    if (!canvas.captureStream) { alert('Ваш браузер не поддерживает captureStream.'); return; }

    const DURATION_MS = 4000;   // 4 секунды
    const FPS = 30;
    const stream = canvas.captureStream(FPS);
    const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
      ? 'video/webm;codecs=vp9'
      : 'video/webm';
    const recorder = new MediaRecorder(stream, { mimeType });
    const chunks = [];

    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `3d_morph_${Date.now()}.webm`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setWebmLoading(false);
    };

    // Автозапуск анимации для записи
    setIsPlaying(true);
    setProgress(0);
    setWebmLoading(true);
    recorder.start();
    setTimeout(() => {
      recorder.stop();
      setIsPlaying(false);
    }, DURATION_MS);
  }, []);

  // ── AUTO PLAY ─────────────────────────────────────────────
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

  // ── FORENSIC SCORE (запрос к /api/forensic-score) ─────────────────
  const fetchForensicScore = useCallback(async () => {
    if (!photoA || !photoB) return;
    setForensicLoading(true);
    try {
      const formData = new FormData();
      formData.append('photo_a', photoA);
      formData.append('photo_b', photoB);
      const res = await fetch('/api/forensic-score', { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`forensic-score: HTTP ${res.status}`);
      const data = await res.json();
      if (data.status === 'ok') setForensicData(data);
    } catch (e) {
      console.warn('Forensic score недоступен:', e.message);
    } finally {
      setForensicLoading(false);
    }
  }, [photoA, photoB]);

  // ── PROCESS ─────────────────────────────────────────────
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
      setForensicData(null);
      // Фоновый запрос зонального forensic-score — не блокирует отображение морфа
      fetchForensicScore();
    } catch (err) {
      setError(err.message || 'Ошибка соединения с бэкендом');
    } finally {
      setLoading(false);
    }
  };

  // ── RENDER ─────────────────────────────────────────────
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

        {/* ── LIVE METRICS + MORPHABILITY SCORE ── */}
        {liveMetrics && (
          <div style={{
            background: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}>
            <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 'bold', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              📐 Live Metrics
            </div>

            {/* Morphability Score — главная метрика */}
            <div style={{
              background: '#0d1117',
              borderRadius: '8px',
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
            }}>
              <div>
                <div style={{ fontSize: '10px', color: '#8b949e', marginBottom: '2px' }}>Morphability Score</div>
                <div style={{ fontSize: '22px', fontWeight: 'bold', color: getMorphabilityColor(parseFloat(liveMetrics.morphability)), fontVariantNumeric: 'tabular-nums' }}>
                  {liveMetrics.morphability}%
                </div>
              </div>
              <MorphabilityBar value={parseFloat(liveMetrics.morphability)} />
            </div>

            {/* Остальные метрики в сетке */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              {[
                { label: 'Cosine Sim', value: liveMetrics.cosine },
                { label: 'Mean Dist', value: liveMetrics.euclidean },
                { label: 'Max Delta', value: liveMetrics.maxDelta },
                { label: '% > 0.025', value: `${liveMetrics.pctAbove}%` },
                { label: 'Вершин', value: liveMetrics.totalVerts },
              ].map(({ label, value }) => (
                <div key={label} style={{ background: '#0d1117', borderRadius: '6px', padding: '6px 10px' }}>
                  <div style={{ fontSize: '10px', color: '#8b949e' }}>{label}</div>
                  <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#e6edf3', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Зональные скоры: предпочитает /api/forensic-score, иначе sidecar из morph-pair */}
        {(forensicData || morphData?.metadata?.zone_scores) && (
          <ZoneScoresPanel
            zones={forensicData ? forensicData.zones : morphData.metadata.zone_scores}
            globalScore={forensicData ? forensicData.global_forensic_score : null}
            onRecompute={fetchForensicScore}
            recomputing={forensicLoading}
          />
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
            onDownloadWebm={handleDownloadWebm}
            webmLoading={webmLoading}
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

// ── HELPERS ─────────────────────────────────────────────────

function getMorphabilityColor(v) {
  if (v >= 75) return '#3fb950';  // зелёный — очень похожи
  if (v >= 50) return '#d29922';  // жёлтый — похож
  if (v >= 25) return '#f0883e';  // оранжевый — мало похож
  return '#f85149';               // красный — сильно различаются
}

function MorphabilityBar({ value }) {
  const color = getMorphabilityColor(value);
  return (
    <div style={{ flex: 1 }}>
      <div style={{ height: '8px', background: '#21262d', borderRadius: '999px', overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${value}%`,
          background: color,
          borderRadius: '999px',
          transition: 'width 0.5s ease',
        }} />
      </div>
      <div style={{ fontSize: '10px', color: '#8b949e', marginTop: '4px', textAlign: 'right' }}>
        {value >= 75 ? 'Очень похожи' : value >= 50 ? 'Похожи' : value >= 25 ? 'Мало похожи' : 'Сильно различаются'}
      </div>
    </div>
  );
}

const ZONE_LABELS = {
  forehead: 'Лоб',
  left_eye: 'Л. глаз',
  right_eye: 'П. глаз',
  nose: 'Нос',
  left_cheek: 'Л. щека',
  right_cheek: 'П. щека',
  mouth_chin: 'Рот/Подб.',
};

function ZoneScoresPanel({ zones, globalScore, onRecompute, recomputing }) {
  return (
    <div style={{
      background: '#161b22',
      border: '1px solid #30363d',
      borderRadius: '8px',
      padding: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 'bold', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          🦷 Зональный Forensic Score{globalScore !== null && globalScore !== undefined ? ` · ${globalScore}` : ''}
        </div>
        {onRecompute && (
          <button
            onClick={onRecompute}
            disabled={recomputing}
            title="Пересчитать через /api/forensic-score"
            style={{
              padding: '3px 8px',
              background: '#21262d',
              border: '1px solid #30363d',
              borderRadius: '6px',
              color: '#8b949e',
              fontSize: '10px',
              cursor: recomputing ? 'not-allowed' : 'pointer',
            }}
          >
            {recomputing ? '⏳ Расчёт...' : '↻ Пересчитать'}
          </button>
        )}
      </div>
      {Object.entries(zones).map(([key, val]) => {
        // forensic-score отдаёт объект {mean_dist, max_dist, identity_score};
        // morph-pair отдаёт плоский mean_dist по зоне
        const score = (val !== null && typeof val === 'object')
          ? val.identity_score
          : Math.max(0, Math.min(100, (1.0 - val / 0.15) * 100));
        const color = getMorphabilityColor(score);
        return (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '64px', fontSize: '11px', color: '#8b949e', flexShrink: 0 }}>{ZONE_LABELS[key] || key}</div>
            <div style={{ flex: 1, height: '6px', background: '#21262d', borderRadius: '999px', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${score.toFixed(0)}%`, background: color, borderRadius: '999px', transition: 'width 0.5s' }} />
            </div>
            <div style={{ width: '38px', fontSize: '11px', color, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>{score.toFixed(0)}%</div>
          </div>
        );
      })}
    </div>
  );
}
