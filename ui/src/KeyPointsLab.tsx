import { useEffect, useMemo, useRef, useState } from 'react'
import type { PairConnection, PoseBin, ZoneMetric } from './types'
import { zoneLabel } from './timeline-data-contract'
import { SectionShell, Chip } from './SectionShell'
import type { SectionKey } from './section-meta'

/* V14: КЛЮЧЕВЫЕ ТОЧКИ (KeyPointsLab).
 *
 * Полноценная панель анализа смещения ключевых точек по парам:
 * - Векторы смещения 9 зон (signedX/Y/Z из zone_metrics) на карте зон.
 * - АНИМАЦИЯ ПО ХРОНОЛОГИИ: playhead по годам 1999–2026; в каждом году —
 *   агрегат пар ракурса (макс. магнитуда по зонам, направление — среднее).
 * - Режимы: «Смещения» (лицо+векторы), «Временной ряд» (9 зон × годы),
 *   «Комбинации» (scatter любых 2 метрик: магнитуда/rmse/dx/dy/dz/z).
 * - ПОРОГИ: шум (ниже = погрешность, приглушено) и аномалия (выше =
 *   аномальное смещение, пульсация) — настраиваются процентилями +
 *   абсолютными значениями; гистограмма магнитуд с маркерами порогов.
 * - Замер комбинаций метрик (ТЗ: «извлекая полностью все точки, можно
 *   замерять разные комбинации метрик»).
 *
 * Данные: zone_metrics (63 пары × 9 зон, signed — 470 измерений). robustZ зон
 * некалиброван — цвет по магнитуде/rmse, z только как опция с пометкой.
 */
const ZONE_ORDER = ['x_high_low', 'x_high_center', 'x_high_high', 'x_center_low', 'x_center_center', 'x_center_high', 'x_low_low', 'x_low_center', 'x_low_high']
const ZONE_POS: Record<string, { col: number; row: number }> = {}
ZONE_ORDER.forEach((zn, i) => { ZONE_POS[zn] = { col: i % 3, row: Math.floor(i / 3) } })
const POSES: (PoseBin | 'all')[] = ['all', 'frontal', 'left_light', 'right_light', 'left_mid', 'right_mid', 'left_deep', 'right_deep', 'left_profile', 'right_profile']
type Mode = 'vectors' | 'timeseries' | 'scatter'
const MAG_METRICS = [
  { id: 'mag', label: 'Магнитуда смещения' },
  { id: 'rmse', label: 'RMSE зоны' },
  { id: 'dx', label: '|ΔX|' },
  { id: 'dy', label: '|ΔY|' },
  { id: 'dz', label: '|ΔZ|' },
  { id: 'z', label: 'robustZ (некалибр.)' },
] as const
type MetricId = typeof MAG_METRICS[number]['id']

interface PointRec { pairId: string; year: number; pose: string; zone: string; rmse: number | null; dx: number; dy: number; dz: number; mag: number; z: number | null; status: string }
interface ZoneAgg { mag: number; dx: number; dy: number; dz: number; n: number; pairs: Set<string>; rmseMax: number }
const valueOf = (p: PointRec, m: MetricId): number | null => {
  switch (m) {
    case 'mag': return p.mag
    case 'rmse': return p.rmse
    case 'dx': return Math.abs(p.dx)
    case 'dy': return Math.abs(p.dy)
    case 'dz': return Math.abs(p.dz)
    case 'z': return p.z
  }
}

export function KeyPointsLab({ pairs, zones, onClose, onNavigate }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>
  onClose: () => void; onNavigate?: (k: SectionKey) => void
}) {
  const [pose, setPose] = useState<'all' | PoseBin>('all')
  const [fromY, setFromY] = useState(1999)
  const [toY, setToY] = useState(2026)
  const [fdrOnly, setFdrOnly] = useState(false)
  const [mode, setMode] = useState<Mode>('vectors')
  const [playYear, setPlayYear] = useState<number | null>(null)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [noisePct, setNoisePct] = useState(50)
  const [anomPct, setAnomPct] = useState(90)
  const [vecScale, setVecScale] = useState(1.6)
  const [showLabels, setShowLabels] = useState(true)
  const [showGrid, setShowGrid] = useState(true)
  const [showVectors, setShowVectors] = useState(true)
  const [colorBy, setColorBy] = useState<'mag' | 'rmse'>('mag')
  const [xMetric, setXMetric] = useState<MetricId>('mag')
  const [yMetric, setYMetric] = useState<MetricId>('rmse')
  const [focusedPair, setFocusedPair] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  /* Точки: из zone_metrics, по фильтрам */
  const points = useMemo<PointRec[]>(() => {
    const pairSet = new Set(pairs.filter(p => {
      if (pose !== 'all' && p.poseBin !== pose) return false
      const y = Number(p.dateB.slice(0, 4))
      if (y < fromY || y > toY) return false
      if (fdrOnly && !p.mtSignificantFdr10) return false
      return true
    }).map(p => p.pairId))
    const out: PointRec[] = []
    for (const [pid, list] of zones) {
      if (!pairSet.has(pid)) continue
      const pair = pairs.find(p => p.pairId === pid)
      const year = pair ? Number(pair.dateB.slice(0, 4)) : 0
      for (const z of list) {
        if (z.status !== 'measured') continue
        const dx = z.signedX ?? 0, dy = z.signedY ?? 0, dz = z.signedZ ?? 0
        out.push({
          pairId: pid, year, pose: z.poseBin || pair?.poseBin || '', zone: z.zone,
          rmse: z.rmse, dx, dy, dz, mag: Math.sqrt(dx * dx + dy * dy + dz * dz),
          z: z.robustZ, status: z.status,
        })
      }
    }
    return out
  }, [zones, pairs, pose, fromY, toY, fdrOnly])

  const years = useMemo(() => {
    const s = new Set(points.map(p => p.year))
    return [...s].sort((a, b) => a - b)
  }, [points])
  const yearRange = useMemo(() => years.length ? years : [1999], [years])

  /* Распределение магнитуд для порогов */
  const dist = useMemo(() => {
    const mags = points.map(p => p.mag).sort((a, b) => a - b)
    const q = (f: number) => mags.length ? mags[Math.min(mags.length - 1, Math.floor(mags.length * f))] : 0
    const noiseVal = q(noisePct / 100)
    const anomVal = q(anomPct / 100)
    return { mags, noiseVal, anomVal, max: mags.length ? mags[mags.length - 1] : 1 }
  }, [points, noisePct, anomPct])

  const aggregate = (source: PointRec[]) => {
    const m = new Map<number, Map<string, ZoneAgg>>()
    for (const p of source) {
      const zonesMap = m.get(p.year) ?? new Map()
      const cur = zonesMap.get(p.zone) ?? { mag: 0, dx: 0, dy: 0, dz: 0, n: 0, pairs: new Set<string>(), rmseMax: 0 }
      cur.n++
      cur.pairs.add(p.pairId)
      if (p.mag > cur.mag) cur.mag = p.mag
      cur.dx += p.dx; cur.dy += p.dy; cur.dz += p.dz
      if ((p.rmse ?? 0) > cur.rmseMax) cur.rmseMax = p.rmse ?? 0
      zonesMap.set(p.zone, cur)
      m.set(p.year, zonesMap)
    }
    return m
  }

  /* Агрегат по году: для каждой зоны — макс магнитуда и средний вектор.
     Отдельно строим общий агрегат, чтобы «Год: все» был данными, а не пустым состоянием. */
  const yearAgg = useMemo(() => aggregate(points), [points])
  const allAgg = useMemo(() => {
    const out = new Map<string, ZoneAgg>()
    for (const p of points) {
      const cur = out.get(p.zone) ?? { mag: 0, dx: 0, dy: 0, dz: 0, n: 0, pairs: new Set<string>(), rmseMax: 0 }
      cur.n++
      cur.pairs.add(p.pairId)
      if (p.mag > cur.mag) cur.mag = p.mag
      cur.dx += p.dx; cur.dy += p.dy; cur.dz += p.dz
      if ((p.rmse ?? 0) > cur.rmseMax) cur.rmseMax = p.rmse ?? 0
      out.set(p.zone, cur)
    }
    return out
  }, [points])

  /* Playhead-анимация по годам */
  useEffect(() => {
    if (!playing) { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null } return }
    timerRef.current = setInterval(() => {
      setPlayYear(prev => {
        const list = yearRange
        if (!list.length) return prev
        const i = list.indexOf(prev ?? list[0])
        const next = list[(i + 1) % list.length]
        if (next === list[list.length - 1] && i === list.length - 1) setPlaying(false)
        return next
      })
    }, 900 / speed)
    return () => { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null } }
  }, [playing, speed, yearRange]) // eslint-disable-line react-hooks/exhaustive-deps

  const activeYear = playYear ?? null
  const agg = activeYear != null ? yearAgg.get(activeYear) : allAgg
  const yearPairs = useMemo(() => {
    const set = new Set<string>()
    for (const p of points) if (activeYear == null || p.year === activeYear) set.add(p.pairId)
    return pairs.filter(p => set.has(p.pairId))
  }, [points, pairs, activeYear])

  const anomCount = useMemo(() => {
    if (!agg) return 0
    let n = 0
    for (const cur of agg.values()) if (cur.mag > dist.anomVal) n++
    return n
  }, [activeYear, agg, dist.anomVal])

  /* Гистограмма магнитуд */
  const hist = useMemo(() => {
    const BINS = 40
    const bins = new Array(BINS).fill(0)
    for (const m of dist.mags) bins[Math.min(BINS - 1, Math.floor((m / Math.max(1e-6, dist.max)) * BINS))]++
    return bins
  }, [dist])

  /* Временные ряды по зонам: медианная магнитуда за год */
  const ts = useMemo(() => {
    const byZone = new Map<string, Map<number, number[]>>()
    for (const p of points) {
      const zm = byZone.get(p.zone) ?? new Map()
      const arr = zm.get(p.year) ?? []
      arr.push(p.mag)
      zm.set(p.year, arr)
      byZone.set(p.zone, zm)
    }
    const series = ZONE_ORDER.map(zn => {
      const zm = byZone.get(zn)
      const data = yearRange.map(y => {
        const arr = zm?.get(y)
        if (!arr?.length) return null
        const s = [...arr].sort((a, b) => a - b)
        return s[Math.floor(s.length / 2)]
      })
      return { zone: zn, data }
    })
    const maxV = Math.max(1e-6, ...series.flatMap(s => s.data).filter((v): v is number => v != null))
    return { series, maxV }
  }, [points, yearRange]) // eslint-disable-line react-hooks/exhaustive-deps

  /* Scatter: точки (zone-pair) по выбранным метрикам */
  const scatter = useMemo(() => {
    const pts = points.map(p => ({ x: valueOf(p, xMetric), y: valueOf(p, yMetric), rec: p }))
      .filter((p): p is { x: number; y: number; rec: PointRec } => p.x != null && p.y != null)
    const maxX = Math.max(1e-6, ...pts.map(p => p.x))
    const maxY = Math.max(1e-6, ...pts.map(p => p.y))
    return { pts, maxX, maxY }
  }, [points, xMetric, yMetric])

  const focusPair = focusedPair ? pairs.find(p => p.pairId === focusedPair) : null
  const focusPoints = focusedPair ? points.filter(p => p.pairId === focusedPair) : []

  return (
    <SectionShell title="Ключевые точки" current="keypoints" onNavigate={onNavigate} onClose={onClose}
      scope={`${points.length} измерений зон · ${new Set(points.map(p => p.pairId)).size} пар · годы ${yearRange[0]}–${yearRange[yearRange.length - 1]}`}
      help={<>Смещение ключевых точек = векторы <b>signedX/Y/Z</b> из zone_metrics (470 измерений, 63 пары × 9 зон). <b>Порог шума</b> — ниже считается погрешностью (приглушено), <b>порог аномалии</b> — выше считается аномальным смещением (пульсация). Пороги задаются процентилями распределения магнитуд. <b>Анимация</b>: playhead по годам, агрегат пар года. robustZ зон некалиброван — основной цвет по магнитуде/rmse.</>}
      filters={<div className="sec-filters-row">
        <select value={pose} onChange={e => setPose(e.target.value as PoseBin | 'all')} aria-label="Ракурс">
          {POSES.map(ps => <option key={ps} value={ps}>{ps === 'all' ? 'Все ракурсы' : ps}</option>)}
        </select>
        <label>с <input type="number" min={1999} max={2026} value={fromY} onChange={e => setFromY(Number(e.target.value))} aria-label="Год с" /></label>
        <label>по <input type="number" min={1999} max={2026} value={toY} onChange={e => setToY(Number(e.target.value))} aria-label="Год по" /></label>
        <Chip active={fdrOnly} onClick={() => setFdrOnly(v => !v)} title="Только FDR-пары">◆ FDR10</Chip>
        <Chip active={mode === 'vectors'} onClick={() => setMode('vectors')} title="Смещения на схеме лица">Смещения</Chip>
        <Chip active={mode === 'timeseries'} onClick={() => setMode('timeseries')} title="Магнитуда по зонам и годам">Временной ряд</Chip>
        <Chip active={mode === 'scatter'} onClick={() => setMode('scatter')} title="Комбинации метрик: любые 2 оси">Комбинации</Chip>
      </div>}
      footer={<div className="kp-foot">
        <span className="kp-legend">
          <i className="kp-sw" />шум (≤{noisePct}%) · <i className="kp-an" />аномалия (&gt;{anomPct}%) · <i className="kp-vec" />вектор (×{vecScale.toFixed(1)}) · {points.length} точек
        </span>
        <span className="kp-keys">Пробел — играть/пауза · ←/→ — год · Esc — закрыть</span>
      </div>}>
      <div className="kp2">
        <div className="sec-card kp-stage-card">
          <div className="kp-stage-head">
            <h3>{mode === 'vectors' ? 'Смещения ключевых точек' : mode === 'timeseries' ? 'Временные ряды по зонам' : 'Комбинации метрик'}</h3>
            <div className="kp-play">
              <button className="kp-btn" onClick={() => setPlayYear(activeYear == null ? yearRange[0] : null)} title="Сброс года">Год: {activeYear ?? 'все'}</button>
              <button className={`kp-btn ${playing ? 'active' : ''}`} onClick={() => setPlaying(v => !v)} title="Пробел">{playing ? '⏸' : '▶'}</button>
              <button className="kp-btn" onClick={() => setPlayYear(prev => { const i = yearRange.indexOf(prev ?? yearRange[0]); return yearRange[Math.max(0, i - 1)] })}>←</button>
              <button className="kp-btn" onClick={() => setPlayYear(prev => { const i = yearRange.indexOf(prev ?? yearRange[0]); return yearRange[Math.min(yearRange.length - 1, i + 1)] })}>→</button>
              <input type="range" min={yearRange[0]} max={yearRange[yearRange.length - 1]} value={activeYear ?? yearRange[0]}
                onChange={e => setPlayYear(Number(e.target.value))} className="kp-year" aria-label="Год" />
              {activeYear != null && <span className="kp-year-info">{activeYear} · {yearPairs.length} пар · <b className={anomCount > 0 ? 'kp-an-txt' : ''}>{anomCount} аномальных зон</b></span>}
            </div>
          </div>

          {mode === 'vectors' && (
            <div className="kp-vectors">
              <svg viewBox="0 0 720 520" className="kp-face" role="img" aria-label="Карта фактически измеренных зон с векторами смещения">
                {showGrid && [1, 2].map(i => <line key={'v' + i} x1={i * 240} y1={24} x2={i * 240} y2={496} className="kp-grid" />)}
                {showGrid && [1, 2].map(i => <line key={'h' + i} x1={0} y1={i * 157.3} x2={720} y2={i * 157.3} className="kp-grid" />)}
                {ZONE_ORDER.map(zn => {
                  const pos = ZONE_POS[zn]
                  const cellX = pos.col * 240, cellY = pos.row * 157.3
                  const cx = cellX + 120, cy = cellY + 78.5
                  const cur = agg?.get(zn)
                  const mag = cur?.mag ?? 0
                  const hasData = !!cur?.n
                  const avgDx = cur?.n ? cur.dx / cur.n : 0
                  const avgDy = cur?.n ? cur.dy / cur.n : 0
                  const avgDz = cur?.n ? cur.dz / cur.n : 0
                  const isAnom = mag > dist.anomVal
                  const isNoise = mag <= dist.noiseVal
                  const col = colorBy === 'rmse' ? (cur?.rmseMax ?? 0) : mag
                  const colMax = colorBy === 'rmse' ? Math.max(dist.anomVal, 1e-6) : dist.anomVal
                  const intensity = Math.min(1, col / Math.max(1e-6, colMax))
                  const color = isAnom ? '#ef4444' : isNoise ? '#3a4452' : `rgba(${Math.round(120 + intensity * 90)},${Math.round(140 + intensity * 60)},${Math.round(230 - intensity * 90)},0.9)`
                  const len = hasData && (isAnom || !isNoise) ? Math.min(54, mag * 520 * vecScale) : 0
                  const ang = Math.atan2(avgDy, avgDx)
                  const ex = cx + Math.cos(ang) * len
                  const ey = cy + Math.sin(ang) * len
                  return (
                    <g key={zn} className={isAnom ? 'kp-anom-g' : ''}>
                      <rect x={cellX + 10} y={cellY + 10} width={220} height={137.3} rx={12} className={`kp-zone-card ${hasData ? '' : 'empty'}`} />
                      {hasData && showVectors && !isNoise && (
                        <g>
                          <line x1={cx} y1={cy} x2={ex} y2={ey} stroke={color} strokeWidth={2.4} markerEnd="url(#kpArrow)" />
                        </g>
                      )}
                      {hasData ? <circle cx={cx} cy={cy} r={isAnom ? 9 : 7} fill={color} stroke={isAnom ? '#fff' : '#0f1115'} strokeWidth={1.6}
                        className={isAnom ? 'kp-anom-pt' : ''}>
                        <title>{`${zoneLabel(zn)}: mag ${mag.toFixed(4)} · rmse ${cur?.rmseMax.toFixed(4) ?? '—'} · n=${cur?.n ?? 0} пар${isAnom ? ' · АНОМАЛЬНОЕ СМЕЩЕНИЕ' : isNoise ? ' · в пределах шума' : ''}`}</title>
                      </circle> : <text x={cx - 5} y={cy + 5} className="kp-zone-empty">—</text>}
                      {hasData ? <>
                        {showLabels && <text x={cellX + 24} y={cellY + 34} className="kp-zone-name">{zoneLabel(zn)}</text>}
                        <text x={cellX + 24} y={cellY + 112} className="kp-zone-value">mag {mag.toFixed(4)} · n {cur?.n}</text>
                        <text x={cellX + 24} y={cellY + 130} className="kp-zone-detail">Δ {avgDx.toFixed(3)} / {avgDy.toFixed(3)} / {avgDz.toFixed(3)}</text>
                      </> : <>
                        {showLabels && <text x={cellX + 24} y={cellY + 34} className="kp-zone-name">{zoneLabel(zn)}</text>}
                        <text x={cellX + 24} y={cellY + 112} className="kp-zone-detail">нет измерения</text>
                      </>}
                    </g>
                  )
                })}
                <defs><marker id="kpArrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="#9bc6f4" /></marker></defs>
              </svg>
              <div className="kp-side">
                <h4>Гистограмма магнитуд</h4>
                <div className="kp-hist">
                  {hist.map((n, i) => <div key={i} className="kp-bar" style={{ height: `${(n / Math.max(1, ...hist)) * 100}%` }}
                    title={`${((i / 40) * dist.max).toFixed(4)}–${(((i + 1) / 40) * dist.max).toFixed(4)}: ${n}`} />)}
                  <div className="kp-thresh" style={{ left: `${(dist.noiseVal / dist.max) * 100}%` }} title={`Порог шума: ${dist.noiseVal.toFixed(4)} (p${noisePct})`} />
                  <div className="kp-thresh an" style={{ left: `${(dist.anomVal / dist.max) * 100}%` }} title={`Порог аномалии: ${dist.anomVal.toFixed(4)} (p${anomPct})`} />
                </div>
                <h4>{activeYear != null ? `Пары ${activeYear}` : 'Пары диапазона'} ({yearPairs.length})</h4>
                <div className="kp-pairs">
                  {yearPairs.map(p => (
                    <button key={p.pairId} data-hit className={`kp-pair ${focusedPair === p.pairId ? 'active' : ''}`} onClick={() => setFocusedPair(focusedPair === p.pairId ? null : p.pairId)}>
                      <span>{p.dateA} → {p.dateB}</span><span>{p.poseBin}</span><span className="kp-z">z {p.meshMaxRobustZ?.toFixed(1) ?? '—'}</span>
                    </button>
                  ))}
                  {yearPairs.length === 0 && <p className="sec-note">Нет пар в этом году (фильтры).</p>}
                </div>
              </div>
            </div>
          )}

          {mode === 'timeseries' && (
            <div className="kp-ts">
              <svg viewBox="0 0 900 340" className="kp-ts-svg" role="img" aria-label="Магнитуда смещения по зонам и годам">
                {yearRange.map((y, i) => (
                  <g key={y}>
                    <line x1={30 + i * (860 / Math.max(1, yearRange.length - 1))} y1={8} x2={30 + i * (860 / Math.max(1, yearRange.length - 1))} y2={300} className="kp-ts-grid" />
                    <text x={30 + i * (860 / Math.max(1, yearRange.length - 1)) + 2} y={316} className="kp-ts-year">{y}</text>
                  </g>
                ))}
                <line x1={30} y1={300 - (dist.noiseVal / ts.maxV) * 290} x2={890} y2={300 - (dist.noiseVal / ts.maxV) * 290} stroke="#3a4452" strokeWidth={1} strokeDasharray="4 4" />
                <line x1={30} y1={300 - (dist.anomVal / ts.maxV) * 290} x2={890} y2={300 - (dist.anomVal / ts.maxV) * 290} stroke="#ef4444" strokeWidth={1.2} strokeDasharray="6 4" />
                <text x={894} y={300 - (dist.anomVal / ts.maxV) * 290 + 3} className="kp-ts-th">аном.</text>
                <text x={894} y={300 - (dist.noiseVal / ts.maxV) * 290 + 3} className="kp-ts-th dim">шум</text>
                {ts.series.map((s, si) => {
                  const color = ['#5e9fe8', '#4fb9c9', '#de9255', '#72bc8f', '#bf8eda', '#eac26b', '#df84a8', '#9aa4b2', '#f87171'][si]
                  let d = ''
                  s.data.forEach((v, i) => {
                    if (v == null) return
                    const x = 30 + i * (860 / Math.max(1, yearRange.length - 1))
                    const y = 300 - (v / ts.maxV) * 290
                    d += (d ? 'L' : 'M') + x + ' ' + y
                  })
                  return (
                    <g key={s.zone}>
                      <path d={d} fill="none" stroke={color} strokeWidth={1.6} opacity={0.9} />
                      {s.data.map((v, i) => v == null ? null : (
                        <circle key={i} cx={30 + i * (860 / Math.max(1, yearRange.length - 1))} cy={300 - (v / ts.maxV) * 290} r={2.4} fill={color}>
                          <title>{`${zoneLabel(s.zone)} ${yearRange[i]}: ${v.toFixed(4)}`}</title>
                        </circle>
                      ))}
                    </g>
                  )
                })}
                {activeYear != null && (() => {
                  const i = yearRange.indexOf(activeYear)
                  const x = 30 + i * (860 / Math.max(1, yearRange.length - 1))
                  return <line x1={x} y1={8} x2={x} y2={300} stroke="#f4f6f8" strokeWidth={1.4} opacity={0.7} />
                })()}
              </svg>
              <div className="kp-ts-legend">
                {ts.series.map((s, si) => (
                  <span key={s.zone} className="kp-ts-chip"><i style={{ background: ['#5e9fe8', '#4fb9c9', '#de9255', '#72bc8f', '#bf8eda', '#eac26b', '#df84a8', '#9aa4b2', '#f87171'][si] }} />{zoneLabel(s.zone)}</span>
                ))}
              </div>
            </div>
          )}

          {mode === 'scatter' && (
            <div className="kp-scatter">
              <div className="kp-axes">
                <label>X
                  <select value={xMetric} onChange={e => setXMetric(e.target.value as MetricId)} aria-label="Ось X">
                    {MAG_METRICS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                  </select>
                </label>
                <label>Y
                  <select value={yMetric} onChange={e => setYMetric(e.target.value as MetricId)} aria-label="Ось Y">
                    {MAG_METRICS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                  </select>
                </label>
                <span className="kp-scatter-note">Точка = зона-пара. Клик — детали. {scatter.pts.length} точек</span>
              </div>
              <svg viewBox="0 0 760 480" className="kp-scatter-svg" role="img" aria-label="Scatter комбинаций метрик">
                {[0.2, 0.4, 0.6, 0.8].map(f => (
                  <g key={f}>
                    <line x1={60 + f * 660} y1={20} x2={60 + f * 660} y2={440} className="kp-sc-grid" />
                    <line x1={60} y1={20 + f * 420} x2={720} y2={20 + f * 420} className="kp-sc-grid" />
                  </g>
                ))}
                {scatter.pts.map((p, i) => {
                  const x = 60 + (p.x / scatter.maxX) * 660
                  const y = 440 - (p.y / scatter.maxY) * 420
                  const anom = p.rec.mag > dist.anomVal
                  return <circle key={i} cx={x} cy={y} r={anom ? 4.5 : 3} fill={anom ? '#ef4444' : '#5e9fe8'} opacity={0.75} className={anom ? 'kp-sc-anom' : ''}>
                    <title>{`${zoneLabel(p.rec.zone)} · ${p.rec.pose} ${p.rec.year} · ${MAG_METRICS.find(m => m.id === xMetric)?.label}: ${p.x.toFixed(4)} · ${MAG_METRICS.find(m => m.id === yMetric)?.label}: ${p.y.toFixed(4)} · mag ${p.rec.mag.toFixed(4)}${anom ? ' · АНОМАЛИЯ' : ''}`}</title>
                  </circle>
                })}
                <text x={62} y={460} className="kp-sc-axis">{MAG_METRICS.find(m => m.id === xMetric)?.label}</text>
                <text x={14} y={24} className="kp-sc-axis">{MAG_METRICS.find(m => m.id === yMetric)?.label}</text>
              </svg>
              {focusPair && (
                <div className="kp-focus">
                  <strong>{focusPair.dateA} → {focusPair.dateB} · {focusPair.poseBin}</strong>
                  {focusPoints.map(p => (
                    <span key={p.zone} className={`kp-focus-pt ${p.mag > dist.anomVal ? 'an' : p.mag <= dist.noiseVal ? 'noise' : ''}`}>
                      {zoneLabel(p.zone)} mag {p.mag.toFixed(4)}{p.mag > dist.anomVal ? ' ⚠' : ''}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <aside className="kp-settings" aria-label="Настройки ключевых точек">
          <h4>Пороги</h4>
          <div className="kp-sec">
            <label>Порог шума (процентиль)<input type="range" min={5} max={80} value={noisePct} onChange={e => { const v = Number(e.target.value); setNoisePct(v); if (v >= anomPct) setAnomPct(Math.min(99, v + 10)) }} /><b>{noisePct}% → {dist.noiseVal.toFixed(4)}</b></label>
            <label>Порог аномалии (процентиль)<input type="range" min={50} max={99} value={anomPct} onChange={e => { const v = Number(e.target.value); setAnomPct(v); if (v <= noisePct) setNoisePct(Math.max(5, v - 10)) }} /><b>{anomPct}% → {dist.anomVal.toFixed(4)}</b></label>
            <p className="kp-note">Ниже порога шума — <b>погрешность</b> (приглушено). Выше порога аномалии — <b>аномальное смещение</b> (красное, пульсация). Между — внимание.</p>
          </div>
          <details className="sec-disclosure kp-settings-more">
            <summary>Настройки отображения и анимации</summary>
            <h4>Векторы</h4>
            <div className="kp-sec">
              <label>Масштаб векторов<input type="range" min={0.4} max={4} step={0.1} value={vecScale} onChange={e => setVecScale(Number(e.target.value))} /><b>{vecScale.toFixed(1)}×</b></label>
              <label>Цвет по
                <select value={colorBy} onChange={e => setColorBy(e.target.value as 'mag' | 'rmse')}>
                  <option value="mag">магнитуде</option><option value="rmse">RMSE зоны</option>
                </select>
              </label>
              <label><input type="checkbox" checked={showVectors} onChange={e => setShowVectors(e.target.checked)} />Стрелки векторов</label>
              <label><input type="checkbox" checked={showLabels} onChange={e => setShowLabels(e.target.checked)} />Подписи зон</label>
              <label><input type="checkbox" checked={showGrid} onChange={e => setShowGrid(e.target.checked)} />Сетка 3×3</label>
            </div>
            <h4>Анимация</h4>
            <div className="kp-sec">
              <label>Скорость<input type="range" min={0.5} max={3} step={0.1} value={speed} onChange={e => setSpeed(Number(e.target.value))} /><b>{speed.toFixed(1)}×</b></label>
              <p className="kp-note">Пробел — играть/пауза. Анимация идёт по годам хронологии; в каждом году — агрегат пар.</p>
            </div>
          </details>
          <details className="sec-disclosure kp-settings-more">
            <summary>Как читать данные</summary>
            <div className="kp-sec">
              <p className="kp-note">signedX/Y/Z — вектор смещения зоны между фото пары. «Комбинации» показывает взаимосвязь двух метрик. robustZ зон некалиброван и помечен как технический.</p>
            </div>
          </details>
        </aside>
      </div>
    </SectionShell>
  )
}
