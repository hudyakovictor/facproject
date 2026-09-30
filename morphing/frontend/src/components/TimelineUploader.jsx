import React, { useMemo, useRef, useState } from 'react';

const palette = ['#1f6feb', '#ab7df8', '#f0883e', '#3fb950'];

export default function TimelineUploader({ files, setFiles, onBuild, loading }) {
  const inputRef = useRef(null);
  const [years, setYears] = useState([]);
  const [futureYear, setFutureYear] = useState('');
  const previews = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);

  const chooseFiles = (event) => {
    const selected = Array.from(event.target.files || []).slice(0, 4);
    setFiles(selected);
    setYears(selected.map((_, index) => years[index] || ''));
    event.target.value = '';
  };
  const remove = (index) => {
    setFiles(files.filter((_, itemIndex) => itemIndex !== index));
    setYears(years.filter((_, itemIndex) => itemIndex !== index));
  };
  const updateYear = (index, value) => {
    const next = [...years];
    next[index] = value;
    setYears(next);
  };

  return (
    <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '10px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#d2a8ff', textTransform: 'uppercase' }}>🎬 Timeline · 2–4 лица</div>
        <span style={{ fontSize: '11px', color: '#8b949e' }}>Catmull–Rom</span>
      </div>
      <div style={{ fontSize: '11px', lineHeight: 1.45, color: '#8b949e' }}>
        Загрузите кадры в хронологическом порядке. Год необязателен и используется только для подписи keyframe.
      </div>
      <button type="button" onClick={() => inputRef.current?.click()} style={secondaryButton}>
        {files.length ? '＋ Заменить keyframes' : '＋ Выбрать 2–4 фотографии'}
      </button>
      <input ref={inputRef} type="file" accept="image/*" multiple onChange={chooseFiles} style={{ display: 'none' }} />
      {files.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
          {files.map((file, index) => (
            <div key={`${file.name}-${index}`} style={{ position: 'relative', minWidth: 0 }}>
              <img src={previews[index]} alt={`Keyframe ${index + 1}`} style={{ width: '100%', aspectRatio: '1', objectFit: 'cover', borderRadius: '6px', border: `2px solid ${palette[index]}` }} />
              <div style={{ color: palette[index], fontWeight: 'bold', fontSize: '10px', marginTop: '3px' }}>{String.fromCharCode(65 + index)}</div>
              <input aria-label={`Год keyframe ${index + 1}`} value={years[index] || ''} onChange={(event) => updateYear(index, event.target.value)} placeholder="год" inputMode="numeric" style={{ width: '100%', padding: '3px', marginTop: '3px', background: '#0d1117', border: '1px solid #30363d', borderRadius: '4px', color: '#e6edf3', fontSize: '10px' }} />
              <button type="button" onClick={() => remove(index)} title="Удалить keyframe" style={{ position: 'absolute', top: '3px', right: '3px', width: '18px', height: '18px', border: 0, borderRadius: '50%', background: 'rgba(13,17,23,.85)', color: '#ff7b72', cursor: 'pointer', lineHeight: 1 }}>×</button>
            </div>
          ))}
        </div>
      )}
      {files.length >= 3 && (
        <label style={{ display: 'grid', gridTemplateColumns: '1fr 90px', gap: '8px', alignItems: 'center', color: '#8b949e', fontSize: '11px' }}>
          <span>Опционально спрогнозировать mesh на год</span>
          <input value={futureYear} onChange={(event) => setFutureYear(event.target.value)} placeholder="2035" inputMode="numeric" style={{ width: '100%', padding: '5px', background: '#0d1117', border: '1px solid #30363d', borderRadius: '4px', color: '#e6edf3', fontSize: '11px' }} />
        </label>
      )}
      {files.length >= 2 && (
        <button type="button" onClick={() => onBuild(years, futureYear)} disabled={loading} style={{ ...primaryButton, opacity: loading ? 0.65 : 1 }}>
          {loading ? '⏳ Строим spline…' : `🧬 Построить timeline (${files.length} keyframes)`}
        </button>
      )}
    </div>
  );
}

const primaryButton = { padding: '10px', background: '#8957e5', color: '#fff', border: 0, borderRadius: '7px', fontWeight: 'bold', cursor: 'pointer', fontSize: '12px' };
const secondaryButton = { padding: '8px', background: '#21262d', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: '7px', cursor: 'pointer', fontSize: '12px' };
