import React, { useMemo, useState } from 'react';

const numberFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 });

function distanceColor(value, maxValue) {
  const ratio = maxValue > 0 ? Math.max(0, Math.min(1, value / maxValue)) : 0;
  const hue = 205 - ratio * 190;
  const lightness = 22 + ratio * 18;
  return `hsl(${hue} 76% ${lightness}%)`;
}

function cosineColor(value) {
  const normalized = Math.max(0, Math.min(1, (value + 1) / 2));
  const hue = 6 + normalized * 128;
  return `hsl(${hue} 66% 32%)`;
}

function displayLabel(name, index) {
  const label = String(name || `Face ${index + 1}`);
  return label.length > 15 ? `${label.slice(0, 12)}…` : label;
}

export default function SimilarityMatrixPanel({ files = [], onSelect }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState('distance');
  const [error, setError] = useState('');
  const labels = useMemo(() => files.map((file, index) => displayLabel(file?.name, index)), [files]);

  const calculate = async () => {
    if (files.length < 2 || files.length > 16 || loading) return;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    try {
      const form = new FormData();
      files.forEach((file) => form.append('photos', file));
      const response = await fetch('/api/similarity-matrix', {
        method: 'POST',
        body: form,
        signal: controller.signal,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      setResult(payload);
    } catch (requestError) {
      if (requestError.name !== 'AbortError') setError(requestError.message || 'Matrix request failed');
    } finally {
      setLoading(false);
    }
  };

  const activeMatrix = view === 'distance'
    ? result?.mean_distance_matrix
    : result?.cosine_similarity_matrix;
  const matrixMaximum = view === 'distance'
    ? Math.max(0, ...(activeMatrix || []).flat())
    : 1;

  return (
    <details style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: 10 }}>
      <summary style={{ cursor: 'pointer', color: '#8b949e', fontSize: 11, fontWeight: 700, textTransform: 'uppercase' }}>
        🧩 Pairwise similarity matrix · {files.length} keyframes
      </summary>
      <div style={{ color: '#8b949e', fontSize: 10, lineHeight: 1.5, margin: '8px 0' }}>
        Вычисляет попарные расстояния между уже загруженными фотографиями. Каждая ячейка кликабельна и выбирает соответствующий keyframe.
      </div>
      <button type="button" onClick={calculate} disabled={loading || files.length < 2 || files.length > 16}
        style={{ width: '100%', padding: '7px 9px', borderRadius: 6, border: '1px solid #30363d', background: loading ? '#30363d' : '#21262d', color: '#c9d1d9', cursor: loading ? 'wait' : 'pointer', fontSize: 10 }}>
        {loading ? '⏳ Сравнение лиц…' : result ? '↻ Пересчитать matrix' : 'Рассчитать pairwise matrix'}
      </button>
      {error && <div role="alert" style={{ marginTop: 7, color: '#ff7b72', fontSize: 10 }}>{error}</div>}
      {result && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {[['distance', 'Mean distance'], ['cosine', 'Cosine']].map(([key, text]) => (
              <button type="button" key={key} onClick={() => setView(key)} aria-pressed={view === key}
                style={{ flex: 1, padding: '5px 7px', background: view === key ? '#1f6feb' : '#0d1117', color: '#e6edf3', border: '1px solid #30363d', borderRadius: 5, cursor: 'pointer', fontSize: 9 }}>
                {text}
              </button>
            ))}
          </div>
          <div style={{ overflowX: 'auto', paddingBottom: 3 }}>
            <div style={{ display: 'grid', gridTemplateColumns: `66px repeat(${labels.length}, minmax(45px, 1fr))`, gap: 3, minWidth: Math.max(260, labels.length * 49 + 70) }}>
              <div />
              {labels.map((label, index) => <button key={`col-${index}`} type="button" title={`Select ${label}`} onClick={() => onSelect?.(index)} style={labelStyle}>{label}</button>)}
              {labels.map((rowLabel, row) => (
                <React.Fragment key={`row-${row}`}>
                  <button type="button" title={`Select ${rowLabel}`} onClick={() => onSelect?.(row)} style={{ ...labelStyle, textAlign: 'right' }}>{rowLabel}</button>
                  {labels.map((columnLabel, column) => {
                    const value = Number(activeMatrix?.[row]?.[column] ?? 0);
                    const background = view === 'distance' ? distanceColor(value, matrixMaximum) : cosineColor(value);
                    return <button key={`${row}-${column}`} type="button" onClick={() => onSelect?.(column)}
                      title={`${rowLabel} ↔ ${columnLabel}: ${view === 'distance' ? `mean distance ${numberFormat.format(value)}` : `cosine ${numberFormat.format(value)}`}. Click to select ${columnLabel}.`}
                      aria-label={`${rowLabel} compared with ${columnLabel}: ${numberFormat.format(value)}; select ${columnLabel}`}
                      style={{ minHeight: 34, padding: '3px', border: '1px solid #30363d', borderRadius: 4, background, color: '#fff', fontSize: 9, fontVariantNumeric: 'tabular-nums', cursor: 'pointer' }}>
                      {numberFormat.format(value)}
                    </button>;
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
          {result.peer_outlier_ranking?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ color: '#8b949e', fontSize: 9, fontWeight: 700, marginBottom: 5 }}>MOST DIFFERENT FROM PEERS</div>
              {result.peer_outlier_ranking.slice(0, 3).map((item) => (
                <button key={item.index} type="button" onClick={() => onSelect?.(item.index)}
                  style={{ width: '100%', display: 'flex', justifyContent: 'space-between', gap: 8, padding: '5px 7px', marginTop: 3, border: '1px solid #30363d', borderRadius: 5, background: '#0d1117', color: '#c9d1d9', textAlign: 'left', fontSize: 9, cursor: 'pointer' }}>
                  <span>{item.label}{item.is_geometric_outlier ? ' · outlier' : ''}</span>
                  <span>{numberFormat.format(item.mean_distance_to_peers)}</span>
                </button>
              ))}
            </div>
          )}
          <div style={{ color: '#8b949e', fontSize: 9, lineHeight: 1.4, marginTop: 8 }}>{result.interpretation}. Pose, expression and reconstruction error may affect distances.</div>
        </div>
      )}
    </details>
  );
}

const labelStyle = {
  minHeight: 28,
  padding: '3px 4px',
  border: '1px solid #30363d',
  borderRadius: 4,
  background: '#0d1117',
  color: '#8b949e',
  fontSize: 9,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  cursor: 'pointer',
};
