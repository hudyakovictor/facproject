import React, { useRef, useCallback } from 'react';

// Вершины треугольника в viewBox 0..100 (проценты)
const A = { x: 50, y: 8 };
const B = { x: 8, y: 92 };
const C = { x: 92, y: 92 };

function barycentric(p, a, b, c) {
  const detT = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y);
  let wA = ((b.y - c.y) * (p.x - c.x) + (c.x - b.x) * (p.y - c.y)) / detT;
  let wB = ((c.y - a.y) * (p.x - c.x) + (a.x - c.x) * (p.y - c.y)) / detT;
  let wC = 1 - wA - wB;
  // Клэмп за пределами треугольника + перенормировка, чтобы точка "прилипала" к краю
  wA = Math.max(0, wA);
  wB = Math.max(0, wB);
  wC = Math.max(0, wC);
  const sum = wA + wB + wC || 1;
  return [wA / sum, wB / sum, wC / sum];
}

function pointFromBary(wA, wB, wC) {
  return {
    x: wA * A.x + wB * B.x + wC * C.x,
    y: wA * A.y + wB * B.y + wC * C.y,
  };
}

/**
 * Треугольный барицентрический слайдер для Multi-Face Blend (3 лица):
 * положение точки внутри треугольника ⇔ веса [wA, wB, wC], Σw = 1.
 * (M7 в docs/30_MORPHING_ANALYSES.md — "треугольный или тетраэдральный
 * слайдер-барицентр"; для 4 лиц используется упрощённый вариант — см.
 * MultiFaceBlend.jsx / линейные нормированные слайдеры.)
 */
export default function TriangleBarycentricPicker({ weights, onChange, labels = ['A', 'B', 'C'] }) {
  const svgRef = useRef(null);
  const point = pointFromBary(weights[0], weights[1], weights[2]);

  const updateFromEvent = useCallback((e) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    const x = ((clientX - rect.left) / rect.width) * 100;
    const y = ((clientY - rect.top) / rect.height) * 100;
    const [wA, wB, wC] = barycentric({ x, y }, A, B, C);
    onChange([wA, wB, wC]);
  }, [onChange]);

  const handlePointerDown = (e) => {
    updateFromEvent(e);
    const move = (ev) => updateFromEvent(ev);
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
      <svg
        ref={svgRef}
        viewBox="0 0 100 100"
        width="100%"
        style={{ maxWidth: '220px', cursor: 'crosshair', touchAction: 'none' }}
        onPointerDown={handlePointerDown}
      >
        <polygon
          points={`${A.x},${A.y} ${B.x},${B.y} ${C.x},${C.y}`}
          fill="rgba(88,166,255,0.08)"
          stroke="#30363d"
          strokeWidth="1"
        />
        {/* Изолинии 25/50/75% для ориентира */}
        {[0.25, 0.5, 0.75].map((f) => (
          <polygon
            key={f}
            points={[A, B, C].map((v) => {
              const cx = (A.x + B.x + C.x) / 3, cy = (A.y + B.y + C.y) / 3;
              return `${cx + (v.x - cx) * f},${cy + (v.y - cy) * f}`;
            }).join(' ')}
            fill="none"
            stroke="#21262d"
            strokeWidth="0.5"
          />
        ))}
        <circle cx={point.x} cy={point.y} r="3.2" fill="#00ffaa" stroke="#0d1117" strokeWidth="1" />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', maxWidth: '220px', fontSize: '10.5px', color: '#8b949e' }}>
        <span style={{ color: '#58a6ff' }}>{labels[0]}: {(weights[0] * 100).toFixed(0)}%</span>
        <span style={{ color: '#f778ba' }}>{labels[1]}: {(weights[1] * 100).toFixed(0)}%</span>
        <span style={{ color: '#d29922' }}>{labels[2]}: {(weights[2] * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}
