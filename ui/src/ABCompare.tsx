import { useEffect, useRef, useState } from 'react'
import type { Frame, PairConnection, PhotoMetrics, ZoneMetric } from './types'
import { classifyPair, zoneLabel } from './timeline-data-contract'

/* V11: СТРАНИЦА СРАВНЕНИЯ A/B — полный редизайн (в 2 раза информативнее).
 *
 * Структура: шапка с режимами → [рейл A | сцена | рейл B] → футер с карточками.
 * - Режимы сцены: «Рядом» (side), «Наложение» (onion, с ползунком прозрачности),
 *   «Разделитель» (divider — перетаскиваемая граница A|B на одном полотне).
 * - Рейлы: полный набор метрик каждого кадра (поза, видимость, кожа, мимика).
 * - Футер: карточки дельт + легенда тепловой шкалы.
 * - Клавиатура: +/− зум, 0 сброс, s/o/d режимы, z зоны, Esc закрыть.
 *
 * Исправленные ранее ошибки:
 * - wheel-зум висел на React-корне (пассивный listener, preventDefault не
 *   работал) → нативный listener с { passive: false } на самой сцене;
 * - отсутствовала клавиатура → добавлена;
 * - битые картинки: face_crop → thumb → скрыть (каскад);
 * - нет режима «разделитель» и ползунка прозрачности → добавлены;
 * - зоны рисовались поверх без подписей/легенды → подписи + шкала в футере.
 */
const ZONE_ORDER = ['x_high_low', 'x_high_center', 'x_high_high', 'x_center_low', 'x_center_center', 'x_center_high', 'x_low_low', 'x_low_center', 'x_low_high']
const MODE_LABEL: Record<'side' | 'onion' | 'divider', string> = { side: 'Рядом (s)', onion: 'Наложение (o)', divider: 'Разделитель (d)' }
const v = (x: number | null | undefined, d = 2) => x == null ? '—' : x.toFixed(d)
const pct = (x: number | null | undefined) => x == null ? '—' : `${(x * 100).toFixed(0)}%`
const zColor = (z: number | null | undefined) => {
  if (z == null) return '#5a6573'
  if (z > 20) return '#ef4444'
  if (z > 10) return '#f97316'
  if (z > 5) return '#eab308'
  if (z > 3) return '#38bdf8'
  return '#22c55e'
}
const imgErr = (e: React.SyntheticEvent<HTMLImageElement>) => {
  const t = e.currentTarget
  if (t.src.includes('face_crop')) t.src = t.src.replace('face_crop', 'thumb')
  else t.style.display = 'none'
}

export function ABCompare({ pair, zones, photoMetrics, frames, onClose }: {
  pair: PairConnection; zones: ZoneMetric[]; photoMetrics?: Map<string, PhotoMetrics>; frames?: Frame[]; onClose: () => void
}) {
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [mode, setMode] = useState<'side' | 'onion' | 'divider'>('side')
  const [showZones, setShowZones] = useState(false)
  const [opacity, setOpacity] = useState(0.45)
  const [divider, setDivider] = useState(50)
  const stageRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<null | { kind: 'pan' | 'divider'; sx: number; sy: number; px: number; py: number }>(null)

  const frameA = frames?.find(f => f.id === pair.photoA)
  const frameB = frames?.find(f => f.id === pair.photoB)
  const mA = photoMetrics?.get(pair.photoA)
  const mB = photoMetrics?.get(pair.photoB)
  const pairZones = zones.filter(z => z.pairId === pair.pairId && z.rmse != null)
  const maxR = Math.max(0.001, ...pairZones.map(z => z.rmse!))
  const dominant = [...pairZones].sort((a, b) => b.rmse! - a.rmse!)[0]
  const expressionMismatch = pair.smileDetectedA !== pair.smileDetectedB || pair.jawOpenDetectedA !== pair.jawOpenDetectedB
  const dAlign = mA?.alignmentQuality != null && mB?.alignmentQuality != null ? mB.alignmentQuality - mA.alignmentQuality : null

  /* V11-fix: нативный wheel на сцене — не пассивный (React root вешал пассивно) */
  useEffect(() => {
    const el = stageRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      setZoom(z => Math.max(0.5, Math.min(6, z * (e.deltaY > 0 ? 0.9 : 1.1))))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === '+' || e.key === '=') setZoom(z => Math.min(6, z * 1.2))
      if (e.key === '-' || e.key === '_') setZoom(z => Math.max(0.5, z / 1.2))
      if (e.key === '0') { setZoom(1); setPan({ x: 0, y: 0 }) }
      if (e.key.toLowerCase() === 's') setMode('side')
      if (e.key.toLowerCase() === 'o') setMode('onion')
      if (e.key.toLowerCase() === 'd') setMode('divider')
      if (e.key.toLowerCase() === 'z') setShowZones(v => !v)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`

  const onStageDown = (e: React.PointerEvent) => {
    dragRef.current = { kind: 'pan', sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onStageMove = (e: React.PointerEvent) => {
    const d = dragRef.current
    if (!d || d.kind !== 'pan') return
    setPan({ x: d.px + (e.clientX - d.sx) / zoom, y: d.py + (e.clientY - d.sy) / zoom })
  }
  const onStageUp = () => { dragRef.current = null }
  const onDividerDown = (e: React.PointerEvent) => {
    e.stopPropagation()
    dragRef.current = { kind: 'divider', sx: e.clientX, sy: 0, px: 0, py: 0 }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onDividerMove = (e: React.PointerEvent) => {
    const d = dragRef.current
    if (!d || d.kind !== 'divider' || !stageRef.current) return
    const r = stageRef.current.getBoundingClientRect()
    setDivider(Math.max(2, Math.min(98, ((e.clientX - r.left) / r.width) * 100)))
  }

  return (
    <div className="cmp" role="dialog" aria-modal="true" aria-label="Сравнение A/B">
      <header className="cmp-header">
        <div className="cmp-title">
          <h2>Сравнение A/B</h2>
          <span>{pair.dateA} → {pair.dateB} · {pair.poseBin} · {pair.pairType} · {classifyPair(pair).label}</span>
        </div>
        <div className="cmp-controls">
          <span className="cmp-zoom">{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom(z => Math.min(6, z * 1.3))} aria-label="Увеличить">+</button>
          <button onClick={() => setZoom(z => Math.max(0.5, z / 1.3))} aria-label="Уменьшить">−</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }} title="Сброс (0)">⊞</button>
          <span className="cmp-sep" />
          {(Object.keys(MODE_LABEL) as Array<keyof typeof MODE_LABEL>).map(md => (
            <button key={md} className={`cmp-btn ${mode === md ? 'active' : ''}`} onClick={() => setMode(md)} title={MODE_LABEL[md]}>{MODE_LABEL[md]}</button>
          ))}
          <button className={`cmp-btn ${showZones ? 'active' : ''}`} onClick={() => setShowZones(v => !v)} title="Зоны (z)">Зоны</button>
          {mode === 'onion' && (
            <label className="cmp-op">A поверх B
              <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={e => setOpacity(Number(e.target.value))} aria-label="Прозрачность наложения" />
              <span>{Math.round(opacity * 100)}%</span>
            </label>
          )}
          <button onClick={onClose} aria-label="Закрыть">×</button>
        </div>
      </header>

      <div className="cmp-body">
        <Rail tag="A" date={pair.dateA} frame={frameA} m={mA} smile={pair.smileDetectedA} jaw={pair.jawOpenDetectedA} photoId={pair.photoA} />
        <div className={`cmp-stage ${dragRef.current?.kind === 'pan' ? 'drag' : ''}`} ref={stageRef}
          onPointerDown={onStageDown} onPointerMove={onStageMove} onPointerUp={onStageUp} onPointerCancel={onStageUp}>
          {mode === 'side' && <>
            <div className="cmp-half" style={{ left: 0, width: '50%' }}><img src={`/storage/stage1/${pair.photoA}/face_crop.jpg`} alt="" draggable={false} style={{ transform }} onError={imgErr} /></div>
            <div className="cmp-half" style={{ left: '50%', width: '50%' }}><img src={`/storage/stage1/${pair.photoB}/face_crop.jpg`} alt="" draggable={false} style={{ transform }} onError={imgErr} /></div>
            <div className="cmp-splitter" />
          </>}
          {mode === 'onion' && <>
            <div className="cmp-half" style={{ left: 0, width: '100%' }}><img src={`/storage/stage1/${pair.photoB}/face_crop.jpg`} alt="" draggable={false} style={{ transform }} onError={imgErr} /></div>
            <div className="cmp-half onion" style={{ left: 0, width: '100%' }}><img src={`/storage/stage1/${pair.photoA}/face_crop.jpg`} alt="" draggable={false} style={{ transform, opacity }} onError={imgErr} /></div>
            <div className="cmp-onion-label">A поверх B · {Math.round(opacity * 100)}%</div>
          </>}
          {mode === 'divider' && <>
            <div className="cmp-half" style={{ left: 0, width: `${divider}%` }}><img src={`/storage/stage1/${pair.photoA}/face_crop.jpg`} alt="" draggable={false} style={{ transform }} onError={imgErr} /></div>
            <div className="cmp-half" style={{ left: `${divider}%`, width: `${100 - divider}%` }}><img src={`/storage/stage1/${pair.photoB}/face_crop.jpg`} alt="" draggable={false} style={{ transform }} onError={imgErr} /></div>
            <div className="cmp-divider" style={{ left: `${divider}%` }} onPointerDown={onDividerDown} onPointerMove={onDividerMove} role="slider" aria-label="Граница разделителя" aria-valuenow={Math.round(divider)} aria-valuemin={2} aria-valuemax={98}><span>◂ ▸</span></div>
          </>}
          {showZones && (
            <div className="cmp-zones" aria-label="Зоны эффекта (3×3, raw rmse)">
              {ZONE_ORDER.map((zn, i) => {
                const z = pairZones.find(x => x.zone === zn)
                const measured = z != null
                const intensity = measured ? z.rmse! / maxR : 0
                return <div key={zn} className="cmp-zone" title={`${zoneLabel(zn)}${measured ? ` · rmse ${z.rmse!.toFixed(4)}` : ' · не измерено'}`}
                  style={{ left: `${(i % 3) * 33.333}%`, top: `${Math.floor(i / 3) * 33.333}%`, width: '33.333%', height: '33.333%', background: measured ? `rgba(222,146,85,${0.08 + intensity * 0.5})` : 'rgba(90,101,115,0.06)' }}>
                  {measured ? <span>{z.rmse!.toFixed(3)}</span> : <span className="na">—</span>}
                </div>
              })}
            </div>
          )}
        </div>
        <Rail tag="B" date={pair.dateB} frame={frameB} m={mB} smile={pair.smileDetectedB} jaw={pair.jawOpenDetectedB} photoId={pair.photoB} />
      </div>

      <footer className="cmp-footer">
        <div className="cmp-cards">
          <F k="Δ max z" value={v(pair.meshMaxRobustZ, 1)} color={zColor(pair.meshMaxRobustZ)} s={pair.meshCalibratedStatus || '—'} />
          <F k="FDR q" value={v(pair.mtQValue, 6)} s={pair.mtSignificantFdr10 ? 'FDR10 значимый' : 'не значим'} />
          <F k="Δ align" value={dAlign != null ? `${dAlign >= 0 ? '+' : ''}${dAlign.toFixed(3)}` : '—'} s="A → B" />
          <F k="Мимика" value={expressionMismatch ? '⚠ различается' : 'совпадает'} s={`улыбка ${pair.smileDetectedA ? '✓' : '—'}/${pair.smileDetectedB ? '✓' : '—'} · челюсть ${pair.jawOpenDetectedA ? '✓' : '—'}/${pair.jawOpenDetectedB ? '✓' : '—'}`} />
          <F k="Видимость" value={`${pct(frameA?.combinedVisibleFraction)} / ${pct(frameB?.combinedVisibleFraction)}`} s="A / B" />
          <F k="Резкость" value={`${v(mA?.laplacianVariance, 0)} / ${v(mB?.laplacianVariance, 0)}`} s="Laplacian A / B" />
          <F k="Кожа z" value={`${v(mA?.skinAuthenticityScore, 1)} / ${v(mB?.skinAuthenticityScore, 1)}`} s="аутентичность A / B" />
          <F k="Дом. зона" value={dominant ? zoneLabel(dominant.zone) : '—'} s={dominant ? `rmse ${dominant.rmse!.toFixed(4)}` : 'нет измерений'} />
        </div>
        <div className="cmp-legend" title="Тепловая шкала: 0–25% норма, 25–50% внимание, 50–75% выражено, 75%+ критично">
          <span>0</span><i /><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
        </div>
      </footer>
    </div>
  )
}

function Rail({ tag, date, frame, m, smile, jaw, photoId }: {
  tag: string; date: string; frame?: Frame; m?: PhotoMetrics; smile: boolean; jaw: boolean; photoId: string
}) {
  return (
    <aside className="cmp-rail" aria-label={`Кадр ${tag}`}>
      <span className="cmp-tag">{tag} · {date}</span>
      <img src={`/storage/stage1/${photoId}/thumb.jpg`} alt="" loading="lazy" onError={imgErr} />
      <div className="cmp-meta">
        <span>yaw/pitch <b>{frame ? `${frame.yaw.toFixed(1)}°/${frame.pitch.toFixed(1)}°` : '—'}</b></span>
        <span>roll <b>{frame ? `${frame.roll.toFixed(1)}°` : '—'}</b></span>
        <span>видимость <b>{frame ? pct(frame.combinedVisibleFraction) : '—'}</b></span>
        <span>align <b>{v(m?.alignmentQuality, 2)}</b></span>
        <span>резкость <b>{v(m?.laplacianVariance, 0)}</b></span>
        <span>шум <b>{v(m?.noiseResidualMean, 2)}</b></span>
        <span>кожа z <b>{v(m?.skinAuthenticityScore, 1)}</b></span>
        <span>кожа q <b>{v(m?.skinQualityScore, 2)}</b></span>
        <span>улыбка <b>{smile ? '✓' : '—'}</b></span>
        <span>челюсть <b>{jaw ? '✓' : '—'}</b></span>
      </div>
    </aside>
  )
}

function F({ k, value, s, color }: { k: string; value: string; s?: string; color?: string }) {
  return <div className="cmp-card"><span className="k">{k}</span><span className="v" style={color ? { color } : undefined}>{value}</span>{s && <span className="s">{s}</span>}</div>
}
