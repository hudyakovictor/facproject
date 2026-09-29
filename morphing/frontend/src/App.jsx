import React, { useState } from 'react';
import PairMorph from './components/PairMorph';
import MultiFaceBlend from './components/MultiFaceBlend';
import TimelineMorph from './components/TimelineMorph';

const TABS = [
  { id: 'pair', label: '👤↔👤 Пара (A↔B)' },
  { id: 'multi', label: '🧬 Multi-Face Blend' },
  { id: 'timeline', label: '🎬 Timeline A→B→C→D' },
];

export default function App() {
  const [tab, setTab] = useState('pair');

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      width: '100vw',
      height: '100vh',
      background: '#0b0c10',
      color: '#e6edf3',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex',
        gap: '4px',
        padding: '6px 10px',
        background: '#0d1117',
        borderBottom: '1px solid #30363d',
        flexShrink: 0,
      }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 16px',
              background: tab === t.id ? '#21262d' : 'transparent',
              border: 'none',
              borderBottom: tab === t.id ? '2px solid #00ffaa' : '2px solid transparent',
              color: tab === t.id ? '#e6edf3' : '#8b949e',
              fontSize: '13px',
              fontWeight: tab === t.id ? 'bold' : 'normal',
              cursor: 'pointer',
              borderRadius: '6px 6px 0 0',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        {tab === 'pair' && <PairMorph />}
        {tab === 'multi' && <MultiFaceBlend />}
        {tab === 'timeline' && <TimelineMorph />}
      </div>
    </div>
  );
}
