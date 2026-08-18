import { useRef, useState } from 'react'
import type { PairConnection, ZoneMetric } from './types'

const ZONE_ORDER = ['x_high_low', 'x_high_center', 'x_high_high', 'x_center_low', 'x_center_center', 'x_center_high', 'x_low_low', 'x_low_center', 'x_low_high']

export function ABCompare({ pair, zones, onClose }: { pair: PairConnection; zones: ZoneMetric[]; onClose: () => void }) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [onion, setOnion] = useState(false)
  const [showZones, setShowZones] = useState(false)
  const dragStart = useRef({ x: 0, y: 0, px: 0, py: 0 })
  const dragging = useRef(false)

  const pairZones = zones.filter((z): z is ZoneMetric & { rmse: number } => z.pairId === pair.pairId && z.rmse != null)
  const maxR = Math.max(...pairZones.map(z => z.rmse), 0.001)
  const dominant = [...pairZones].sort((a, b) => b.rmse - a.rmse)[0]

  return (
    <div className="abc">
      <header className="abc-header">
        <h2>Сравнение A/B</h2>
        <div className="abc-controls">
          <span className="abc-zoom">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom(z => Math.min(5, z * 1.3))}>+</button>
          <button onClick={() => setZoom(z => Math.max(0.5, z / 1.3))}>−</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }}>⊞</button>
          <button className={`abc-btn ${onion ? 'active' : ''}`} onClick={() => setOnion(v => !v)}>Наложение</button>
          <button className={`abc-btn ${showZones ? 'active' : ''}`} onClick={() => setShowZones(v => !v)}>Зоны {dominant ? `(${dominant.zone})` : ''}</button>
          <span className="abc-info">{pair.dateA} → {pair.dateB} · {pair.poseBin}</span>
          <button onClick={onClose}>×</button>
        </div>
      </header>
      <div className="abc-body">
        <div className="abc-side">
          <div className="abc-label">A · {pair.dateA}</div>
          <div className="abc-img-wrap"
            onPointerDown={e => { dragging.current = true; dragStart.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }; (e.target as HTMLElement).setPointerCapture(e.pointerId) }}
            onPointerMove={e => { if (dragging.current) setPan({ x: dragStart.current.px + (e.clientX - dragStart.current.x) / zoom, y: dragStart.current.py + (e.clientY - dragStart.current.y) / zoom }) }}
            onPointerUp={() => { dragging.current = false }}
            onWheel={e => { e.preventDefault(); const delta = e.deltaY > 0 ? 0.9 : 1.1; setZoom(z => Math.max(0.5, Math.min(5, z * delta))) }}>
            <img src={`/storage/stage1/${pair.photoA}/face_crop.jpg`} alt=""
              style={{ transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`, cursor: dragging.current ? 'grabbing' : 'grab' }}
              onError={e => { (e.target as HTMLImageElement).src = `/storage/stage1/${pair.photoA}/thumb.jpg` }} />
          </div>
          <div className="abc-meta">
            align {pair.alignmentQualityA?.toFixed(2) ?? '—'} · улыбка {pair.smileDetectedA ? '✓' : '—'}
          </div>
        </div>

        <div className="abc-side">
          <div className="abc-label">B · {pair.dateB}</div>
          <div className="abc-img-wrap" style={{ position: 'relative' }}
            onPointerDown={e => { dragging.current = true; dragStart.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }; (e.target as HTMLElement).setPointerCapture(e.pointerId) }}
            onPointerMove={e => { if (dragging.current) setPan({ x: dragStart.current.px + (e.clientX - dragStart.current.x) / zoom, y: dragStart.current.py + (e.clientY - dragStart.current.y) / zoom }) }}
            onPointerUp={() => { dragging.current = false }}
            onWheel={e => { e.preventDefault(); const delta = e.deltaY > 0 ? 0.9 : 1.1; setZoom(z => Math.max(0.5, Math.min(5, z * delta))) }}>
            <img src={`/storage/stage1/${pair.photoB}/face_crop.jpg`} alt=""
              style={{ transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`, cursor: dragging.current ? 'grabbing' : 'grab' }}
              onError={e => { (e.target as HTMLImageElement).src = `/storage/stage1/${pair.photoB}/thumb.jpg` }} />
            {showZones && pairZones.map(z => {
              const pos = ZONE_ORDER.indexOf(z.zone)
              if (pos < 0) return null
              const row = Math.floor(pos / 3), col = pos % 3
              const intensity = z.rmse / maxR
              return <div key={z.zone} className="abc-zone"
                style={{
                  position: 'absolute', left: `${col * 33.3}%`, top: `${row * 33.3}%`,
                  width: '33.3%', height: '33.3%',
                  background: `rgba(222, 146, 85, ${intensity * 0.4})`,
                  border: '1px solid rgba(222, 146, 85, 0.5)',
                  display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
                  fontSize: 8, color: '#fff', padding: 2, pointerEvents: 'none',
                }}>
                {z.rmse.toFixed(3)}
              </div>
            })}
            {onion && <img src={`/storage/stage1/${pair.photoA}/face_crop.jpg`} alt=""
              style={{
                position: 'absolute', inset: 0, width: '100%', height: '100%',
                objectFit: 'contain', opacity: 0.4, pointerEvents: 'none',
                transform: `translate(${pan.x}px,${pan.y}px) scale(${zoom})`,
              }}
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />}
          </div>
          <div className="abc-meta">
            align {pair.alignmentQualityB?.toFixed(2) ?? '—'} · улыбка {pair.smileDetectedB ? '✓' : '—'}
          </div>
        </div>
      </div>
      <div className="abc-footer">
        Δ z = {(pair.meshMaxRobustZ ?? 0).toFixed(2)} · Δ align = {((pair.alignmentQualityA ?? 0) - (pair.alignmentQualityB ?? 0)).toFixed(3)}
        {dominant && ` · Доминантная зона: ${dominant.zone} (RMSE ${dominant.rmse.toFixed(4)})`}
      </div>
    </div>
  )
}