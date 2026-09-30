import React from 'react';

const labels = {
  forehead: 'Лоб',
  left_eye: 'Л. орбита',
  right_eye: 'П. орбита',
  nose: 'Нос',
  left_cheek: 'Л. скула',
  right_cheek: 'П. скула',
  mouth_chin: 'Рот / подбородок',
};

export default function TemporalDriftPanel({ drift }) {
  if (!drift) return null;
  const residuals = drift.residuals || [];
  const maxResidual = Math.max(...residuals, 1e-9);
  const maxVelocity = Math.max(...Object.values(drift.zone_velocity || {}), 1e-9);
  const points = residuals.map((value, index) => `${residuals.length === 1 ? 50 : (index / (residuals.length - 1)) * 100},${36 - (value / maxResidual) * 28}`).join(' ');
  const anomalyPositions = new Set(drift.anomaly_positions || []);

  return (
    <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: '11px', color: '#f0883e', fontWeight: 'bold', letterSpacing: '0.05em', textTransform: 'uppercase' }}>⏳ Temporal identity drift</div>
        <span style={{ color: '#8b949e', fontSize: '10px' }}>{drift.years?.[0]}–{drift.years?.[drift.years.length - 1]}</span>
      </div>
      <div style={{ color: '#8b949e', fontSize: '10px', lineHeight: 1.4 }}>
        Линейная траектория dense mesh по годам. Красные точки — отклонения от траектории, не доказательство операции или старения.
      </div>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" style={{ width: '100%', height: '58px', background: '#0d1117', borderRadius: '5px' }} aria-label="Residuals temporal drift">
        <polyline points={points} fill="none" stroke="#f0883e" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
        {residuals.map((value, index) => <circle key={index} cx={residuals.length === 1 ? 50 : (index / (residuals.length - 1)) * 100} cy={36 - (value / maxResidual) * 28} r={anomalyPositions.has(index) ? 2.2 : 1.4} fill={anomalyPositions.has(index) ? '#f85149' : '#f0883e'} />)}
      </svg>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '5px' }}>
        {Object.entries(drift.zone_velocity || {}).map(([zone, value]) => (
          <div key={zone} style={{ background: '#0d1117', borderRadius: '4px', padding: '5px' }}>
            <div style={{ color: '#8b949e', fontSize: '9px' }}>{labels[zone] || zone}</div>
            <div style={{ height: '4px', margin: '4px 0', background: '#21262d', borderRadius: '99px', overflow: 'hidden' }}><div style={{ width: `${Math.min(100, (value / maxVelocity) * 100)}%`, height: '100%', background: '#f0883e' }} /></div>
            <div style={{ color: '#e6edf3', fontSize: '10px', fontVariantNumeric: 'tabular-nums' }}>{value} / год</div>
          </div>
        ))}
      </div>
      <div style={{ color: '#6e7681', fontSize: '9px' }}>Скорость: {drift.velocity_l2_per_year} L2 / год · anomalies: {anomalyPositions.size}</div>
    </div>
  );
}
