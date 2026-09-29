import React, { useState, useMemo, useEffect, useRef } from 'react';
import CanvasMulti from './CanvasMulti';
import { fitAlphaTrend } from '../lib/temporalTrend';

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
 *
 * Если для всех фото указан год съёмки — дополнительно доступен блок
 * Temporal Identity Drift / 4D Age Progression (M15/M19): линейная регрессия
 * alpha_id по годам, остатки-аномалии, экстраполяция в "будущее" (всегда
 * помечена как synthetic/exploratory — 3DMM не различает причину изменения
 * формы, только его геометрическое направление).
 */
export default function TimelineMorph() {
  const [photos, setPhotos] = useState([]); // File[]
  const [years, setYears] = useState([]);   // string[] (год съёмки, опционально), параллельно photos
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [playheadT, setPlayheadT] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [wireframe, setWireframe] = useState(false);
  const [lighting, setLighting] = useState(false);
  const [extrapolateYears, setExtrapolateYears] = useState('10');
  const [extrapolatedFrame, setExtrapolatedFrame] = useState(null); // { vertices, texture, year }
  const [extrapolateLoading, setExtrapolateLoading] = useState(false);
  const [extrapolateError, setExtrapolateError] = useState(null);
  const fileInputRef = useRef(null);

  const addFiles = (fileList) => {
    const files = Array.from(fileList).slice(0, 6 - photos.length);
    setPhotos((prev) => [...prev, ...files].slice(0, 6));
    setYears((prev) => [...prev, ...files.map(() => '')].slice(0, 6));
  };

  const removeAt = (idx) => {
    setPhotos((prev) => prev.filter((_, i) => i !== idx));
    setYears((prev) => prev.filter((_, i) => i !== idx));
  };
  const moveAt = (idx, dir) => {
    const swap = (arr) => {
      const next = [...arr];
      const j = idx + dir;
      if (j < 0 || j >= next.length) return arr;
      [next[idx], next[j]] = [next[j], next[idx]];
      return next;
    };
    setPhotos((prev) => swap(prev));
    setYears((prev) => swap(prev));
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
      setExtrapolatedFrame(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // "Расширенные" данные с добавленным синтетическим кадром экстраполяции (если построен)
  const displayData = useMemo(() => {
    if (!data) return null;
    if (!extrapolatedFrame) return data;
    return {
      ...data,
      count: data.count + 1,
      vertices: [...data.vertices, extrapolatedFrame.vertices],
      textures: [...data.textures, data.textures[data.textures.length - 1]],
    };
  }, [data, extrapolatedFrame]);

  const maxT = displayData ? displayData.count - 1 : 0;

  // Autoplay: пинг-понг по всей временной шкале
  useEffect(() => {
    if (!isPlaying || !displayData) return;
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
  }, [isPlaying, displayData, maxT]);

  const { slotIndices, segT, segmentLabel } = useMemo(() => {
    if (!displayData) return { slotIndices: [0, 0, 1, 1], segT: 0, segmentLabel: '' };
    const n = displayData.count;
    const t = Math.max(0, Math.min(maxT, playheadT));
    const k = Math.min(Math.floor(t), Math.max(n - 2, 0));
    const localT = n > 1 ? t - k : 0;
    const p0 = Math.max(k - 1, 0);
    const p1 = k;
    const p2 = Math.min(k + 1, n - 1);
    const p3 = Math.min(k + 2, n - 1);
    const label2 = extrapolatedFrame && p2 === n - 1 ? `🔮 прогноз (+${extrapolatedFrame.years} лет)` : `${p2 + 1}`;
    return {
      slotIndices: [p0, p1, p2, p3],
      segT: localT,
      segmentLabel: n > 1 ? `Между фото ${p1 + 1} и ${label2} · t=${localT.toFixed(2)}` : 'Фото 1',
    };
  }, [displayData, playheadT, maxT, extrapolatedFrame]);

  // ── TEMPORAL DRIFT / 4D AGE PROGRESSION ──────────────────────────
  const parsedYears = useMemo(() => years.map((y) => parseFloat(y)), [years]);
  const yearsValid = data && parsedYears.length === data.count && parsedYears.every((y) => Number.isFinite(y));

  const trend = useMemo(() => {
    if (!data || !yearsValid || data.count < 3 || !data.alpha_id) return null;
    try {
      return fitAlphaTrend(parsedYears, data.alpha_id);
    } catch {
      return null;
    }
  }, [data, yearsValid, parsedYears]);

  const handleExtrapolate = async () => {
    if (!trend || !data) return;
    const dy = parseFloat(extrapolateYears);
    if (!Number.isFinite(dy)) { setExtrapolateError('Введите число лет'); return; }
    setExtrapolateLoading(true);
    setExtrapolateError(null);
    try {
      const lastYear = Math.max(...parsedYears);
      const targetYear = lastYear + dy;
      const alphaPred = Array.from(trend.predict(targetYear));
      const res = await fetch('/api/alpha-to-mesh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alpha_id: alphaPred }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({ detail: 'Ошибка сервера' }));
        throw new Error(errJson.detail || 'Не удалось построить прогноз');
      }
      const json = await res.json();
      setExtrapolatedFrame({ vertices: json.vertices, years: dy, year: targetYear });
    } catch (e) {
      setExtrapolateError(e.message);
    } finally {
      setExtrapolateLoading(false);
    }
  };

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
            Catmull-Rom интерполяция формы через N упорядоченных лиц. Впишите год
            съёмки у каждого фото, чтобы открыть Temporal Drift / 4D-прогноз.
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
                  <input
                    type="number" placeholder="год" value={years[idx] || ''}
                    onChange={(e) => setYears((prev) => { const n = [...prev]; n[idx] = e.target.value; return n; })}
                    style={{ width: '58px', background: '#0d1117', border: '1px solid #30363d', borderRadius: '4px', color: '#c9d1d9', fontSize: '11px', padding: '3px 4px' }}
                  />
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
              onClick={() => { setData(null); setError(null); setIsPlaying(false); setExtrapolatedFrame(null); }}
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
                {Array.from({ length: displayData.count }).map((_, i) => (
                  <button key={i} onClick={() => { setIsPlaying(false); setPlayheadT(i); }}
                    style={{ padding: '3px 8px', background: Math.round(playheadT) === i ? '#238636' : (extrapolatedFrame && i === displayData.count - 1 ? '#8957e5' : '#21262d'), border: '1px solid #30363d', borderRadius: '6px', color: '#fff', fontSize: '10.5px', cursor: 'pointer' }}>
                    {extrapolatedFrame && i === displayData.count - 1 ? '🔮' : i + 1}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setIsPlaying((p) => !p)}
                style={{ padding: '10px', background: isPlaying ? '#da3633' : '#238636', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 'bold', cursor: 'pointer' }}
              >
                {isPlaying ? '⏸ Остановить' : '▶️ Воспроизвести всю хронологию'}
              </button>
              {extrapolatedFrame && playheadT >= data.count - 1 && (
                <div style={{ fontSize: '10.5px', color: '#d2a8ff', background: 'rgba(137,87,229,0.12)', border: '1px solid rgba(137,87,229,0.4)', borderRadius: '6px', padding: '6px 8px' }}>
                  🔮 Синтетический кадр (экстраполяция +{extrapolatedFrame.years} лет) — НЕ реальное фото,
                  геометрия формы построена линейным трендом α_id, текстура переиспользована с последнего фото.
                </div>
              )}
            </div>

            {/* Temporal Identity Drift / 4D Age Progression */}
            <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#8b949e', textTransform: 'uppercase' }}>
                📈 Temporal Drift / 4D Age Progression
              </div>
              {!yearsValid || data.count < 3 ? (
                <div style={{ fontSize: '11px', color: '#6e7681' }}>
                  Впишите год съёмки для всех {data.count} фото (минимум 3 точки), чтобы построить
                  регрессию α_id по времени и прогноз.
                </div>
              ) : trend ? (
                <>
                  <div style={{ fontSize: '11px', color: '#8b949e' }}>
                    Скорость дрейфа формы: <b style={{ color: '#e6edf3' }}>{trend.driftSpeedPerYear.toFixed(5)}</b> (‖Δα_id‖/год)
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {parsedYears.map((y, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                        <span style={{ color: '#8b949e' }}>#{i + 1} ({y})</span>
                        <span style={{ color: trend.anomalyFlags[i] ? '#ff9492' : '#7ee787' }}>
                          {trend.anomalyFlags[i] ? '⚠️ аномалия' : '✓ на тренде'} · residual {trend.residualNorms[i].toFixed(3)}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: '10px', color: '#6e7681', lineHeight: 1.4 }}>
                    ⚠️ "Аномалия" = отклонение от линейного тренда формы (&gt;1.5 стандартных отклонения по
                    остаткам). При N&lt;5 точках статистика ненадёжна — ориентир, не вывод. 3DMM НЕ различает
                    причину изменения (старение / хирургия / ракурс) — это не медицинское заключение.
                  </div>

                  <div style={{ borderTop: '1px solid #21262d', paddingTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ fontSize: '11px', color: '#8b949e' }}>🔮 Прогноз (exploratory, синтетика):</div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px' }}>+</span>
                      <input type="number" value={extrapolateYears} onChange={(e) => setExtrapolateYears(e.target.value)}
                        style={{ width: '60px', background: '#0d1117', border: '1px solid #30363d', borderRadius: '4px', color: '#c9d1d9', fontSize: '11px', padding: '4px 6px' }} />
                      <span style={{ fontSize: '11px' }}>лет от последней даты</span>
                    </div>
                    <button
                      onClick={handleExtrapolate}
                      disabled={extrapolateLoading}
                      style={{ padding: '8px', background: '#8957e5', color: '#fff', border: 'none', borderRadius: '8px', fontWeight: 'bold', fontSize: '12px', cursor: extrapolateLoading ? 'not-allowed' : 'pointer' }}
                    >
                      {extrapolateLoading ? '⏳ Строим прогноз...' : '🔮 Добавить синтетический кадр в timeline'}
                    </button>
                    {extrapolateError && <div style={{ color: '#ff7b72', fontSize: '11px' }}>⚠️ {extrapolateError}</div>}
                  </div>
                </>
              ) : (
                <div style={{ fontSize: '11px', color: '#6e7681' }}>Недостаточно данных для регрессии.</div>
              )}
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
        {displayData ? (
          <CanvasMulti
            data={displayData}
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
