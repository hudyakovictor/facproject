import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Canvas3D from './components/Canvas3D';
import DropZone from './components/DropZone';
import Controls from './components/Controls';
import TimelineUploader from './components/TimelineUploader';
import FaceSpacePlot from './components/FaceSpacePlot';
import { catmullRomWeights } from './utils/timeline';

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
  const [symmetryData, setSymmetryData] = useState(null);
  const [symmetryLoading, setSymmetryLoading] = useState(false);
  const [timelineFiles, setTimelineFiles] = useState([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineMode, setTimelineMode] = useState(false);
  const [blendMode, setBlendMode] = useState('timeline');
  const [blendWeights, setBlendWeights] = useState([1, 0, 0, 0]);
  const [deformationMode, setDeformationMode] = useState('linear');

  const [progress, setProgress] = useState(0.0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showLandmarks, setShowLandmarks] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showUVDiff, setShowUVDiff] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [lighting, setLighting] = useState(false);

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
      landmarks_106_a: prev.landmarks_106_b,
      landmarks_106_b: prev.landmarks_106_a,
      sequence_vertices: [prev.vertices_b, prev.vertices_a],
      sequence_landmarks: [prev.landmarks_106_b, prev.landmarks_106_a],
      sequence_textures: [prev.texture_b_base64, prev.texture_a_base64],
      metadata: { ...prev.metadata },
      timeline: { method: 'linear pair', keyframe_count: 2, labels: ['Face A', 'Face B'] },
    }));
    setProgress((prev) => 1.0 - prev);
  }, [morphData]);

  // ── LIVE METRICS: recomputed on every timeline tick, without a network call ──
  const liveMetrics = useMemo(() => {
    const sequence = morphData?.sequence_vertices;
    if (!sequence?.length || sequence.length < 2) return null;
    const weights = blendMode === 'blend'
      ? normalizeWeights(blendWeights, sequence.length)
      : catmullRomWeights(progress, sequence.length);
    const current = new Float32Array(sequence[0].length);
    for (let faceIndex = 0; faceIndex < sequence.length; faceIndex += 1) {
      const weight = weights[faceIndex];
      if (!weight) continue;
      for (let index = 0; index < current.length; index += 1) current[index] += sequence[faceIndex][index] * weight;
    }
    const anchor = sequence[0];
    const endpoint = sequence[sequence.length - 1];
    const n = current.length / 3;
    const THRESHOLD = 0.025;
    let sumDist = 0; let maxDist = 0; let aboveThreshold = 0;
    let dot = 0; let normCurrent = 0; let normEndpoint = 0;
    let sumEndpointDelta = 0;
    for (let index = 0; index < current.length; index += 3) {
      const dx = current[index] - anchor[index];
      const dy = current[index + 1] - anchor[index + 1];
      const dz = current[index + 2] - anchor[index + 2];
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      sumDist += d; maxDist = Math.max(maxDist, d); if (d > THRESHOLD) aboveThreshold += 1;
      const ex = current[index] - endpoint[index];
      const ey = current[index + 1] - endpoint[index + 1];
      const ez = current[index + 2] - endpoint[index + 2];
      sumEndpointDelta += Math.sqrt(ex * ex + ey * ey + ez * ez);
      dot += current[index] * endpoint[index] + current[index + 1] * endpoint[index + 1] + current[index + 2] * endpoint[index + 2];
      normCurrent += current[index] ** 2 + current[index + 1] ** 2 + current[index + 2] ** 2;
      normEndpoint += endpoint[index] ** 2 + endpoint[index + 1] ** 2 + endpoint[index + 2] ** 2;
    }
    const meanDist = sumDist / n;
    return {
      euclidean: meanDist.toFixed(5),
      maxDelta: maxDist.toFixed(5),
      pctAbove: ((aboveThreshold / n) * 100).toFixed(1),
      totalVerts: n.toLocaleString(),
      cosine: (dot / (Math.sqrt(normCurrent) * Math.sqrt(normEndpoint) + 1e-9)).toFixed(4),
      morphability: Math.max(0, Math.min(100, (1 - meanDist / 0.15) * 100)).toFixed(1),
      toEndpoint: (sumEndpointDelta / n).toFixed(5),
      keyframeCount: sequence.length,
    };
  }, [morphData, progress, blendMode, blendWeights]);

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

  // ── VIDEO RECORD: exact 60 timeline frames via canvas.captureStream ──
  const handleDownloadWebm = useCallback(() => {
    const canvas = document.querySelector('canvas');
    if (!canvas) { alert('Канвас не найден. Запустите морфинг перед записью.'); return; }
    if (!canvas.captureStream || !window.MediaRecorder) { alert('Браузер не поддерживает canvas.captureStream / MediaRecorder.'); return; }
    const candidates = [
      ['video/mp4;codecs=avc1.42E01E', 'mp4'],
      ['video/webm;codecs=vp9', 'webm'],
      ['video/webm;codecs=vp8', 'webm'],
      ['video/webm', 'webm'],
    ];
    const selected = candidates.find(([mime]) => MediaRecorder.isTypeSupported(mime));
    if (!selected) { alert('В этом браузере нет поддерживаемого MP4/WebM кодека.'); return; }
    const [mimeType, extension] = selected;
    const stream = canvas.captureStream(60);
    const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 8_000_000 });
    const chunks = [];
    let frame = 0;
    let previousPlaying = isPlaying;
    setWebmLoading(true);
    setIsPlaying(false);
    setProgress(0);
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
    recorder.onerror = () => { stream.getTracks().forEach((track) => track.stop()); setWebmLoading(false); alert('Не удалось записать видео.'); };
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: mimeType });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `3d_morph_${Date.now()}.${extension}`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      stream.getTracks().forEach((track) => track.stop());
      setWebmLoading(false);
      setIsPlaying(previousPlaying);
    };
    recorder.start();
    const capture = () => {
      const t = frame / 59;
      setProgress(t);
      frame += 1;
      if (frame < 60) window.requestAnimationFrame(capture);
      else window.setTimeout(() => recorder.stop(), 120);
    };
    window.requestAnimationFrame(capture);
  }, [isPlaying]);

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

  const selectFaceSpace = useCallback((index) => {
    const count = morphData?.sequence_vertices?.length || 2;
    setBlendMode('timeline');
    setProgress(count > 1 ? index / (count - 1) : 0);
  }, [morphData]);

  const fetchSymmetry = useCallback(async () => {
    const source = timelineMode ? timelineFiles[0] : photoA;
    if (!source) return;
    setSymmetryLoading(true);
    try {
      const formData = new FormData();
      formData.append('photo', source);
      const response = await fetch('/api/symmetry', { method: 'POST', body: formData });
      if (!response.ok) throw new Error(`symmetry: HTTP ${response.status}`);
      const data = await response.json();
      if (data.status === 'ok') setSymmetryData(data);
    } catch (e) {
      setError(`Не удалось рассчитать symmetry: ${e.message}`);
    } finally {
      setSymmetryLoading(false);
    }
  }, [photoA, timelineFiles, timelineMode]);

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
    formData.append('deformation', deformationMode);
    try {
      const response = await fetch('/api/morph-pair', { method: 'POST', body: formData });
      if (!response.ok) {
        const errJson = await response.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errJson.detail || 'Не удалось выполнить реконструкцию');
      }
      const data = await response.json();
      setMorphData(data);
      setTimelineMode(false);
      setBlendMode('timeline');
      setBlendWeights([1, 0, 0, 0]);
      setProgress(0.0);
      setForensicData(null);
      setSymmetryData(null);
      // Фоновый запрос зонального forensic-score — не блокирует отображение морфа
      fetchForensicScore();
    } catch (err) {
      setError(err.message || 'Ошибка соединения с бэкендом');
    } finally {
      setLoading(false);
    }
  };

  // ── MULTI-FACE TIMELINE ─────────────────────────────────────────────
  const handleBuildTimeline = async (years) => {
    if (timelineFiles.length < 2) return;
    setTimelineLoading(true);
    setError(null);
    setIsPlaying(false);
    try {
      const formData = new FormData();
      timelineFiles.forEach((file) => formData.append('photos', file));
      formData.append('metadata', JSON.stringify(timelineFiles.map((file, index) => ({
        label: file.name.replace(/\\.[^.]+$/, '') || `Face ${String.fromCharCode(65 + index)}`,
        year: years[index] || null,
      }))));
      const response = await fetch('/api/morph-sequence', { method: 'POST', body: formData });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || 'Не удалось построить timeline');
      }
      const data = await response.json();
      setMorphData(data);
      setTimelineMode(true);
      setBlendMode('timeline');
      setBlendWeights(Array.from({ length: timelineFiles.length }, (_, index) => (index === 0 ? 1 : 0)));
      setProgress(0);
      setForensicData(null);
      setSymmetryData(null);
    } catch (err) {
      setError(err.message || 'Ошибка timeline-морфинга');
    } finally {
      setTimelineLoading(false);
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
            disabled={!morphData?.vertices_a || timelineMode}
            title={timelineMode ? 'Для timeline используйте порядок keyframes' : 'Поменять A и B местами'}
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

        <label style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', alignItems: 'center', fontSize: '12px', color: '#8b949e' }}>
          <span>Smooth deformation</span>
          <select value={deformationMode} onChange={(event) => setDeformationMode(event.target.value)} style={{ background: '#161b22', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: '6px', padding: '6px', fontSize: '11px' }}>
            <option value="linear">Linear correspondence</option>
            <option value="tps">Thin-plate spline (TPS)</option>
          </select>
        </label>

        <TimelineUploader
          files={timelineFiles}
          setFiles={(files) => { setTimelineFiles(files); setTimelineMode(files.length >= 2); }}
          onBuild={handleBuildTimeline}
          loading={timelineLoading}
        />

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
                { label: 'До финала', value: liveMetrics.toEndpoint },
                { label: '% > 0.025', value: `${liveMetrics.pctAbove}%` },
                { label: 'Вершин', value: liveMetrics.totalVerts },
                { label: 'Keyframes', value: liveMetrics.keyframeCount },
              ].map(({ label, value }) => (
                <div key={label} style={{ background: '#0d1117', borderRadius: '6px', padding: '6px 10px' }}>
                  <div style={{ fontSize: '10px', color: '#8b949e' }}>{label}</div>
                  <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#e6edf3', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        {morphData && Number(morphData.metadata?.morphability_score ?? morphData.metadata?.first_last_similarity?.morphability_score) < 50 && (
          <div style={{ background: 'rgba(248, 81, 73, 0.12)', border: '1px solid rgba(248, 81, 73, 0.5)', color: '#ff7b72', borderRadius: '8px', padding: '9px 12px', fontSize: '11px', lineHeight: 1.4 }}>
            ⚠️ Низкая геометрическая совместимость. Морфинг может давать артефакты; проверьте ракурс, выражение и качество реконструкции.
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

        {morphData?.metadata?.face_space && <FaceSpacePlot faceSpace={morphData.metadata.face_space} onSelect={selectFaceSpace} />}

        {morphData && (
          <SymmetryPanel data={symmetryData} loading={symmetryLoading} onCalculate={fetchSymmetry} />
        )}

        {morphData?.parameter_heatmap?.length > 0 && (
          <ParameterHeatmapPanel items={morphData.parameter_heatmap} />
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
            showUVDiff={showUVDiff}
            setShowUVDiff={setShowUVDiff}
            wireframe={wireframe}
            setWireframe={setWireframe}
            lighting={lighting}
            setLighting={setLighting}
            metadata={morphData.metadata}
            sequenceCount={morphData.sequence_vertices?.length || 2}
            blendMode={blendMode}
            setBlendMode={setBlendMode}
            blendWeights={blendWeights}
            setBlendWeights={setBlendWeights}
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
            blendMode={blendMode}
            blendWeights={blendWeights}
            showLandmarks={showLandmarks}
            showHeatmap={showHeatmap}
            showUVDiff={showUVDiff}
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

function normalizeWeights(values, count) {
  const next = Array.from({ length: 4 }, (_, index) => Math.max(0, Number(values[index] || 0)));
  const total = next.slice(0, count).reduce((sum, value) => sum + value, 0) || 1;
  return next.map((value, index) => (index < count ? value / total : 0));
}

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

function SymmetryPanel({ data, loading, onCalculate }) {
  return (
    <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: '11px', color: '#79c0ff', fontWeight: 'bold', letterSpacing: '0.05em', textTransform: 'uppercase' }}>🪞 Bilateral symmetry</div>
        <button type="button" onClick={onCalculate} disabled={loading} style={{ padding: '3px 8px', background: '#21262d', border: '1px solid #30363d', borderRadius: '6px', color: '#8b949e', fontSize: '10px', cursor: loading ? 'not-allowed' : 'pointer' }}>
          {loading ? '⏳ Расчёт…' : data ? '↻ Пересчитать' : 'Рассчитать'}
        </button>
      </div>
      {!data && <div style={{ color: '#8b949e', fontSize: '10px', lineHeight: 1.4 }}>Отражение canonical mesh относительно x=0 и nearest-neighbour сравнение.</div>}
      {data && <>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ fontSize: '22px', fontWeight: 'bold', color: data.score >= 0.8 ? '#3fb950' : data.score >= 0.6 ? '#d29922' : '#f85149' }}>{(data.score * 100).toFixed(1)}%</div>
          <div style={{ flex: 1, height: '7px', background: '#21262d', borderRadius: '99px', overflow: 'hidden' }}><div style={{ width: `${data.score * 100}%`, height: '100%', background: data.score >= 0.8 ? '#3fb950' : '#d29922' }} /></div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '4px' }}>
          {Object.entries(data.regions || {}).slice(0, 6).map(([name, value]) => <div key={name} style={{ background: '#0d1117', borderRadius: '4px', padding: '5px', color: '#8b949e', fontSize: '9px' }}>{ZONE_LABELS[name] || name}<b style={{ display: 'block', color: '#e6edf3', fontSize: '11px' }}>{(value.score * 100).toFixed(0)}%</b></div>)}
        </div>
        <div style={{ color: '#6e7681', fontSize: '9px' }}>{data.interpretation}</div>
      </>}
    </div>
  );
}

function ParameterHeatmapPanel({ items }) {
  const groups = [...new Set(items.map((item) => item.group))];
  return (
    <details style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '12px' }}>
      <summary style={{ cursor: 'pointer', color: '#ffb86c', fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase' }}>
        🔬 Stage2 v2 · {items.length} параметров
      </summary>
      <div style={{ fontSize: '10px', color: '#8b949e', lineHeight: 1.4, margin: '8px 0' }}>
        Интенсивность — прокси от dense-mesh delta, а не новый калиброванный Stage 2 замер. Нажмите группу, чтобы увидеть ключи.
      </div>
      {groups.map((group) => {
        const groupItems = items.filter((item) => item.group === group);
        return (
          <div key={group} style={{ marginTop: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#c9d1d9', fontSize: '10px', marginBottom: '3px' }}>
              <span>{group}</span><span>{groupItems.length}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '3px' }}>
              {groupItems.map((item) => (
                <div key={item.key} title={`${item.title} · ${item.source}`} style={{ background: `linear-gradient(90deg, rgba(255,123,114,${0.12 + item.signal * 0.7}) ${item.signal * 100}%, #21262d ${item.signal * 100}%)`, borderRadius: '3px', padding: '3px 4px', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', color: '#c9d1d9', fontSize: '9px' }}>
                  {item.key}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </details>
  );
}

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
          🦷 Зональный Forensic Score{globalScore !== null && globalScore !== undefined ? ` · ${globalScore}%` : ''}
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
          ? (val.identity_score ?? val.similarity ?? 0)
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
