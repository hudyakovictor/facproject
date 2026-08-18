import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { PairConnection, ZoneMetric } from './types'
import { classifyPair, zoneLabel } from './timeline-data-contract'

/* V13: ПАНЕЛЬ МОРФИНГА A→B — большой горизонтальный попап.
 *
 * Возможности:
 * - Интерактивный морфинг между фото пары (слайдер + авто-петля A→B→A).
 * - 3D-морфинг: если Stage 1 отдаёт mesh.json — интерполяция вершин с
 *   вращением; иначе честный 2D-режим (данные Stage 1 вне песочницы).
 * - Тепловая карта: зонная (3×3 raw rmse) + пиксельная (разностная карта
 *   изображений) с настраиваемыми порогами (0–25–50–75 по ТЗ), схемой,
 *   гаммой и размытием.
 * - Ключевые точки: центры зон, размер/цвет по rmse; точки с аномальным
 *   смещением (rmse > порога) подсвечиваются кольцами с пульсацией.
 * - Многослойные фильтры отображения: фото/морфинг/зоны/сетка/точки/
 *   разностная карта/подписи.
 * - Легенда тепловой шкалы с текущими порогами.
 */
const ZONE_ORDER = ['x_high_low', 'x_high_center', 'x_high_high', 'x_center_low', 'x_center_center', 'x_center_high', 'x_low_low', 'x_low_center', 'x_low_high']
const ZONE_POS: Record<string, { x: number; y: number }> = {}
ZONE_ORDER.forEach((zn, i) => { const row = Math.floor(i / 3), col = i % 3; ZONE_POS[zn] = { x: ((col + 0.5) / 3) * 100, y: ((row + 0.5) / 3) * 100 } })

interface MorphSettings {
  s1: number; s2: number; s3: number      // пороги тепловой карты, % (0–100)
  gamma: number                            // гамма-коррекция интенсивности
  blur: number                             // размытие зонной карты, px
  scheme: 'thermal' | 'gray' | 'inverse'   // цветовая схема
  anomalyPct: number                       // доля max rmse → аномальная точка
  pointSize: number                        // базовый радиус точек, px
  speed: number                            // скорость авто-морфинга
  showHeat: boolean; showZones: boolean; showGrid: boolean
  showPoints: boolean; showAnomalies: boolean; showDiff: boolean; showLabels: boolean
  auto: boolean; loop: boolean
}
const DEFAULTS: MorphSettings = {
  s1: 25, s2: 50, s3: 75, gamma: 1, blur: 0, scheme: 'thermal',
  anomalyPct: 0.6, pointSize: 12, speed: 1.2,
  showHeat: true, showZones: true, showGrid: false, showPoints: true,
  showAnomalies: true, showDiff: false, showLabels: false,
  auto: false, loop: true,
}
const SETTINGS_KEY = 'deeputin_morph_settings_v1'

function lerpHex(a: string, b: string, k: number): string {
  const pa = parseInt(a.slice(1), 16), pb = parseInt(b.slice(1), 16)
  const r = Math.round(((pa >> 16) & 255) + (((pb >> 16) & 255) - ((pa >> 16) & 255)) * k)
  const g = Math.round(((pa >> 8) & 255) + (((pb >> 8) & 255) - ((pa >> 8) & 255)) * k)
  const bl = Math.round((pa & 255) + ((pb & 255) - (pa & 255)) * k)
  return `rgb(${r},${g},${bl})`
}
function heatColor(p: number, s: MorphSettings): string {
  const pct = Math.max(0, Math.min(100, p))
  const g = Math.max(0.1, s.gamma)
  const curve = (v: number) => Math.pow(v / 100, 1 / g) * 100
  const p1 = curve(s.s1), p2 = curve(s.s2), p3 = curve(s.s3), pc = curve(pct)
  const stops: [number, string][] = [[0, '#1d4ed8'], [p1, '#22d3ee'], [p2, '#22c55e'], [p3, '#ef4444'], [100, '#7f1d1d']]
  let color = '#7f1d1d'
  for (let i = 0; i < stops.length - 1; i++) {
    const [x0, c0] = stops[i], [x1, c1] = stops[i + 1]
    if (pc >= x0 && pc <= x1) { color = lerpHex(c0, c1, x1 === x0 ? 1 : (pc - x0) / (x1 - x0)); break }
    if (pc <= x0) { color = c0; break }
  }
  if (s.scheme === 'gray') {
    const gv = Math.round((pc / 100) * 255)
    return `rgb(${gv},${gv},${gv})`
  }
  if (s.scheme === 'inverse') {
    const inv = (c: string) => { const n = parseInt(c.slice(1), 16); return `rgb(${255 - ((n >> 16) & 255)},${255 - ((n >> 8) & 255)},${255 - (n & 255)})` }
    return inv(color)
  }
  return color
}
function drawContain(ctx: CanvasRenderingContext2D, img: HTMLImageElement, W: number, H: number) {
  const scale = Math.min(W / img.naturalWidth, H / img.naturalHeight)
  const w = img.naturalWidth * scale, h = img.naturalHeight * scale
  ctx.drawImage(img, (W - w) / 2, (H - h) / 2, w, h)
}

export function MorphPanel({ pair, zones, onClose }: {
  pair: PairConnection; zones: ZoneMetric[]; onClose: () => void
}) {
  const [t, setT] = useState(0.5)
  const [settings, setSettings] = useState<MorphSettings>(() => {
    try { const raw = localStorage.getItem(SETTINGS_KEY); return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS } catch { return DEFAULTS }
  })
  const [imgs, setImgs] = useState<{ a?: HTMLImageElement; b?: HTMLImageElement; aOk: boolean; bOk: boolean }>({ aOk: false, bOk: false })
  const [diff, setDiff] = useState<HTMLCanvasElement | null>(null)
  const [mesh, setMesh] = useState<{ a: number[][]; b: number[][] } | null>(null)
  const [meshStatus, setMeshStatus] = useState<'idle' | 'checking' | 'ok' | 'missing'>('idle')
  const [angle, setAngle] = useState(0)
  const sceneRef = useRef<HTMLCanvasElement>(null)
  const canvas3dRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef(0)

  useEffect(() => { try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)) } catch { /* noop */ } }, [settings])

  /* Загрузка изображений пары */
  useEffect(() => {
    let alive = true
    const load = (src: string) => new Promise<HTMLImageElement | null>((res) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => res(img)
      img.onerror = () => res(null)
      img.src = src
    })
    Promise.all([load(`/storage/stage1/${pair.photoA}/face_crop.jpg`), load(`/storage/stage1/${pair.photoB}/face_crop.jpg`)]).then(([a, b]) => {
      if (!alive) return
      setImgs({ a: a ?? undefined, b: b ?? undefined, aOk: !!a, bOk: !!b })
    })
    return () => { alive = false }
  }, [pair])

  /* Разностная (пиксельная) карта — реальные различия изображений */
  useEffect(() => {
    if (!imgs.a || !imgs.b) { setDiff(null); return }
    const S = 360
    const cv = document.createElement('canvas')
    cv.width = S; cv.height = S
    const ctx = cv.getContext('2d')
    if (!ctx) return
    ctx.drawImage(imgs.a, 0, 0, S, S)
    const da = ctx.getImageData(0, 0, S, S)
    ctx.clearRect(0, 0, S, S)
    ctx.drawImage(imgs.b, 0, 0, S, S)
    const db = ctx.getImageData(0, 0, S, S)
    const out = ctx.createImageData(S, S)
    let max = 1
    for (let i = 0; i < da.data.length; i += 4) {
      const d = Math.abs(da.data[i] - db.data[i]) + Math.abs(da.data[i + 1] - db.data[i + 1]) + Math.abs(da.data[i + 2] - db.data[i + 2])
      if (d > max) max = d
    }
    for (let i = 0; i < da.data.length; i += 4) {
      const d = Math.abs(da.data[i] - db.data[i]) + Math.abs(da.data[i + 1] - db.data[i + 1]) + Math.abs(da.data[i + 2] - db.data[i + 2])
      const n = d / max
      const col = heatColor(n * 100, settings)
      const m = col.match(/\d+/g)
      out.data[i] = m ? Number(m[0]) : 0
      out.data[i + 1] = m ? Number(m[1]) : 0
      out.data[i + 2] = m ? Number(m[2]) : 0
      out.data[i + 3] = 255
    }
    ctx.putImageData(out, 0, 0)
    setDiff(cv)
  }, [imgs, settings]) // eslint-disable-line react-hooks/exhaustive-deps

  /* Отрисовка сцены (2D-морфинг + diff) */
  useEffect(() => {
    const cv = sceneRef.current
    if (!cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const W = cv.width, H = cv.height
    ctx.clearRect(0, 0, W, H)
    if (imgs.a && imgs.b) {
      ctx.globalAlpha = 1 - t
      drawContain(ctx, imgs.a, W, H)
      ctx.globalAlpha = t
      drawContain(ctx, imgs.b, W, H)
      ctx.globalAlpha = 1
    } else {
      ctx.fillStyle = '#101318'
      ctx.fillRect(0, 0, W, H)
      ctx.fillStyle = '#3a4452'
      ctx.font = '12px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(imgs.aOk || imgs.bOk ? 'Одно из изображений недоступно — морфинг неполный' : 'Изображения Stage 1 недоступны в этом окружении — зонная карта активна', W / 2, H / 2)
      ctx.font = '10px monospace'
      ctx.fillStyle = '#5a6573'
      ctx.fillText('При наличии /Volumes/SDCARD/storage/stage1 морфинг заработает автоматически', W / 2, H / 2 + 18)
    }
    if (settings.showDiff && diff) {
      ctx.globalAlpha = 0.65
      ctx.drawImage(diff, 0, 0, W, H)
      ctx.globalAlpha = 1
    }
  }, [t, imgs, diff, settings.showDiff])

  /* 3D-рендер (если mesh доступен): интерполяция вершин + вращение */
  useEffect(() => {
    const cv = canvas3dRef.current
    if (!cv || meshStatus !== 'ok' || !mesh) return
    const ctx = cv.getContext('2d')
    if (!ctx) return
    const W = cv.width, H = cv.height
    ctx.clearRect(0, 0, W, H)
    const n = Math.min(mesh.a.length, mesh.b.length)
    const step = Math.max(1, Math.floor(n / 9000))
    const rad = (angle * Math.PI) / 180
    const cos = Math.cos(rad), sin = Math.sin(rad)
    // нормализация к общему центру/масштабу
    const ax = mesh.a, bx = mesh.b
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity, minZ = Infinity, maxZ = -Infinity
    for (let i = 0; i < n; i += step) {
      const v = ax[i]
      if (!v || v.length < 3) continue
      const vx = v[0] + (bx[i][0] - v[0]) * t
      const vy = v[1] + (bx[i][1] - v[1]) * t
      const vz = v[2] + (bx[i][2] - v[2]) * t
      const xr = vx * cos - vz * sin
      const zr = vx * sin + vz * cos
      if (xr < minX) minX = xr; if (xr > maxX) maxX = xr
      if (vy < minY) minY = vy; if (vy > maxY) maxY = vy
      if (zr < minZ) minZ = zr; if (zr > maxZ) maxZ = zr
    }
    const sx = (W - 40) / Math.max(1e-6, maxX - minX)
    const sy = (H - 40) / Math.max(1e-6, maxY - minY)
    const sc = Math.min(sx, sy)
    ctx.fillStyle = '#101318'
    ctx.fillRect(0, 0, W, H)
    for (let i = 0; i < n; i += step) {
      const va = ax[i], vb = bx[i]
      if (!va || !vb || va.length < 3) continue
      const vx = va[0] + (vb[0] - va[0]) * t
      const vy = va[1] + (vb[1] - va[1]) * t
      const vz = va[2] + (vb[2] - va[2]) * t
      const xr = vx * cos - vz * sin
      const zr = vx * sin + vz * cos
      const px = (W - (maxX + minX) * sc) / 2 + xr * sc
      const py = (H - (maxY + minY) * sc) / 2 + vy * sc
      const depth = (zr - minZ) / Math.max(1e-6, maxZ - minZ)
      ctx.fillStyle = `rgba(${Math.round(80 + depth * 120)},${Math.round(120 + depth * 90)},${Math.round(200 - depth * 60)},0.85)`
      ctx.fillRect(px, py, 1.6, 1.6)
    }
  }, [mesh, meshStatus, t, angle])

  /* Авто-морфинг */
  useEffect(() => {
    if (!settings.auto) return
    let last = performance.now()
    const tick = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000)
      last = now
      setT(prev => {
        let next = prev + dt * settings.speed * 0.5
        if (next > 1) next = settings.loop ? 0 : 1
        if (next < 0) next = settings.loop ? 1 : 0
        return next
      })
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [settings.auto, settings.speed, settings.loop])

  /* Клавиатура */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowLeft') setT(v => Math.max(0, v - 0.05))
      if (e.key === 'ArrowRight') setT(v => Math.min(1, v + 0.05))
      if (e.key === ' ') { e.preventDefault(); setSettings(s => ({ ...s, auto: !s.auto })) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const set = useCallback((patch: Partial<MorphSettings>) => setSettings(s => ({ ...s, ...patch })), [])

  const zonesMeasured = useMemo(() => zones.filter(z => z.status === 'measured' && z.rmse != null), [zones])
  const maxRmse = Math.max(0.0001, ...zonesMeasured.map(z => z.rmse!))
  const topZones = useMemo(() => [...zonesMeasured].sort((a, b) => b.rmse! - a.rmse!).slice(0, 5), [zonesMeasured])

  const try3d = async () => {
    setMeshStatus('checking')
    const load = async (id: string): Promise<number[][] | null> => {
      try {
        const r = await fetch(`/storage/stage1/${id}/mesh.json`)
        if (!r.ok) return null
        const j = await r.json()
        const verts = j.vertices ?? j.mesh?.vertices ?? null
        return verts && Array.isArray(verts) && verts.length > 0 ? verts : null
      } catch { return null }
    }
    const [a, b] = await Promise.all([load(pair.photoA), load(pair.photoB)])
    if (a && b) { setMesh({ a, b }); setMeshStatus('ok') }
    else { setMeshStatus('missing'); setMesh(null) }
  }
  const reset = () => { setSettings(DEFAULTS); setT(0.5); setAngle(0) }

  return (
    <div className="morph" role="dialog" aria-modal="true" aria-label="Морфинг пары A/B">
      <header className="morph-header">
        <div className="morph-title">
          <h2>Морфинг A → B</h2>
          <span>{pair.dateA} → {pair.dateB} · {pair.poseBin} · {classifyPair(pair).label} · z {pair.meshMaxRobustZ?.toFixed(1) ?? '—'}</span>
        </div>
        <div className="morph-controls">
          <button className={`m-btn ${settings.auto ? 'active' : ''}`} onClick={() => set({ auto: !settings.auto })} title="Авто-морфинг (пробел)">{settings.auto ? '⏸ Пауза' : '▶ Авто'}</button>
          <button className="m-btn" onClick={reset} title="Сбросить настройки и позицию">Сброс</button>
          <button className="m-btn" onClick={try3d} title="Загрузить 3D-модели (mesh.json из Stage 1)">3D</button>
          {meshStatus === 'ok' && <label className="m-op">угол <input type="range" min={-60} max={60} value={angle} onChange={e => setAngle(Number(e.target.value))} aria-label="Угол вращения 3D" /></label>}
          {meshStatus === 'checking' && <span className="m-status">проверка 3D…</span>}
          {meshStatus === 'missing' && <span className="m-status">3D-данные не найдены — работает 2D-морфинг</span>}
          <button onClick={onClose} aria-label="Закрыть (Esc)">×</button>
        </div>
      </header>

      <div className="morph-body">
        <div className="morph-stage-wrap">
          <div className="morph-stage">
            <canvas ref={sceneRef} width={900} height={560} className="morph-canvas" />
            {meshStatus === 'ok' && <canvas ref={canvas3dRef} width={900} height={560} className="morph-canvas3d" />}
            {settings.showZones && (
              <div className="morph-zones" aria-label="Зонная тепловая карта 3×3">
                {ZONE_ORDER.map(zn => {
                  const z = zones.find(x => x.zone === zn)
                  const measured = z?.status === 'measured' && z.rmse != null
                  const intensity = measured ? (z!.rmse! / maxRmse) * 100 : 0
                  const pos = ZONE_POS[zn]
                  const bg = measured && settings.showHeat ? heatColor(intensity, settings) : 'transparent'
                  return (
                    <div key={zn} className="morph-zone" style={{ left: `${pos.x}%`, top: `${pos.y}%`, transform: 'translate(-50%,-50%)', background: bg, borderColor: measured ? undefined : '#2a3340' }}
                      title={`${zoneLabel(zn)}: ${measured ? 'rmse ' + z!.rmse!.toFixed(4) + ' · ' + Math.round(intensity) + '% шкалы' : 'не измерено'}`}>
                      {settings.showLabels && <span className="morph-zone-label">{zoneLabel(zn)}</span>}
                    </div>
                  )
                })}
              </div>
            )}
            {settings.showGrid && (
              <div className="morph-grid" aria-hidden="true">
                {[0, 1, 2].map(r => [0, 1, 2].map(c => <div key={`${r}${c}`} className="morph-grid-cell" style={{ left: `${c * 33.333}%`, top: `${r * 33.333}%` }} />))}
              </div>
            )}
            {settings.showPoints && zonesMeasured.map(z => {
              const pos = ZONE_POS[z.zone]
              const intensity = (z.rmse! / maxRmse) * 100
              const anomaly = intensity >= settings.s1 * (1 + settings.anomalyPct) || intensity >= settings.s2
              const r = Math.max(4, settings.pointSize * (0.4 + (z.rmse! / maxRmse) * 0.8))
              return (
                <div key={z.zone + 'p'} className={`morph-point ${anomaly && settings.showAnomalies ? 'anomaly' : ''}`}
                  style={{ left: `${pos.x}%`, top: `${pos.y}%`, width: r, height: r, marginLeft: -r / 2, marginTop: -r / 2, background: heatColor(intensity, settings), borderColor: anomaly ? '#fff' : '#5a6573' }}
                  title={`${zoneLabel(z.zone)}: rmse ${z.rmse!.toFixed(4)}${anomaly ? ' · ⚠ аномальное смещение' : ''}`} />
              )
            })}
            {meshStatus === 'ok' && (
              <div className="morph-3d-note">3D-морфинг: интерполяция вершин {t * 100 | 0}% · угол {angle}° · точки = вершины меша</div>
            )}
          </div>
          <div className="morph-slider-row">
            <span className="m-side">{pair.dateA}</span>
            <input type="range" min={0} max={100} value={Math.round(t * 100)} onChange={e => setT(Number(e.target.value) / 100)}
              className="morph-slider" aria-label="Морфинг A→B" style={{ background: `linear-gradient(90deg, #1d4ed8, #22d3ee ${settings.s1}%, #22c55e ${settings.s2}%, #ef4444 ${settings.s3}%, #7f1d1d)` }} />
            <span className="m-side">{pair.dateB}</span>
            <span className="m-pct">{Math.round(t * 100)}%</span>
          </div>
          <div className="morph-legend">
            <span className="m-legend-item" style={{ background: '#1d4ed8' }}>0</span>
            <span className="m-legend-item" style={{ background: '#22d3ee' }}>{settings.s1}%</span>
            <span className="m-legend-item" style={{ background: '#22c55e' }}>{settings.s2}%</span>
            <span className="m-legend-item" style={{ background: '#ef4444' }}>{settings.s3}%</span>
            <span className="m-legend-item" style={{ background: '#7f1d1d' }}>100%</span>
            <span className="m-legend-txt">норма · внимание · выражено · критично — пороги настраиваются справа</span>
          </div>
        </div>

        <aside className="morph-panel" aria-label="Настройки морфинга">
          <h4>Тепловая карта</h4>
          <div className="m-sec">
            <label>Порог синий→голубой <input type="range" min={0} max={99} value={settings.s1} onChange={e => set({ s1: Number(e.target.value) })} /><b>{settings.s1}%</b></label>
            <label>Порог голубой→зелёный <input type="range" min={1} max={100} value={settings.s2} onChange={e => set({ s2: Math.max(settings.s1 + 1, Number(e.target.value)) })} /><b>{settings.s2}%</b></label>
            <label>Порог зелёный→красный <input type="range" min={1} max={100} value={settings.s3} onChange={e => set({ s3: Math.max(settings.s2 + 1, Number(e.target.value)) })} /><b>{settings.s3}%</b></label>
            <label>Гамма (кривая) <input type="range" min={0.3} max={3} step={0.1} value={settings.gamma} onChange={e => set({ gamma: Number(e.target.value) })} /><b>{settings.gamma.toFixed(1)}</b></label>
            <label>Размытие <input type="range" min={0} max={8} value={settings.blur} onChange={e => set({ blur: Number(e.target.value) })} /><b>{settings.blur}px</b></label>
            <label>Схема
              <select value={settings.scheme} onChange={e => set({ scheme: e.target.value as MorphSettings['scheme'] })}>
                <option value="thermal">Термальная</option>
                <option value="gray">Серый градиент</option>
                <option value="inverse">Инверсия</option>
              </select>
            </label>
          </div>

          <h4>Слои</h4>
          <div className="m-sec m-layers">
            <label><input type="checkbox" checked={settings.showHeat} onChange={e => set({ showHeat: e.target.checked })} />Тепловая карта зон</label>
            <label><input type="checkbox" checked={settings.showZones} onChange={e => set({ showZones: e.target.checked })} />Зоны 3×3</label>
            <label><input type="checkbox" checked={settings.showGrid} onChange={e => set({ showGrid: e.target.checked })} />Сетка</label>
            <label><input type="checkbox" checked={settings.showPoints} onChange={e => set({ showPoints: e.target.checked })} />Ключевые точки</label>
            <label><input type="checkbox" checked={settings.showAnomalies} onChange={e => set({ showAnomalies: e.target.checked })} />Подсветка аномалий</label>
            <label><input type="checkbox" checked={settings.showDiff} onChange={e => set({ showDiff: e.target.checked })} />Разностная карта (пиксели)</label>
            <label><input type="checkbox" checked={settings.showLabels} onChange={e => set({ showLabels: e.target.checked })} />Подписи зон</label>
          </div>

          <h4>Ключевые точки</h4>
          <div className="m-sec">
            <label>Порог аномалии <input type="range" min={0.1} max={1} step={0.05} value={settings.anomalyPct} onChange={e => set({ anomalyPct: Number(e.target.value) })} /><b>{Math.round(settings.anomalyPct * 100)}%</b></label>
            <label>Размер точек <input type="range" min={6} max={26} value={settings.pointSize} onChange={e => set({ pointSize: Number(e.target.value) })} /><b>{settings.pointSize}px</b></label>
            <p className="m-note">Точки — центры зон; радиус и цвет по rmse. Точка с интенсивностью ≥ порога зелёного — <b>аномальное смещение</b> (белое кольцо + пульсация).</p>
          </div>

          <h4>Авто-морфинг</h4>
          <div className="m-sec">
            <label>Скорость <input type="range" min={0.2} max={3} step={0.1} value={settings.speed} onChange={e => set({ speed: Number(e.target.value) })} /><b>{settings.speed.toFixed(1)}×</b></label>
            <label><input type="checkbox" checked={settings.loop} onChange={e => set({ loop: e.target.checked })} />Петля A→B→A</label>
          </div>

          <h4>Пары</h4>
          <div className="m-sec m-metrics">
            <span>Δ max z <b style={{ color: '#eac26b' }}>{pair.meshMaxRobustZ?.toFixed(1) ?? '—'}</b></span>
            <span>FDR q <b>{pair.mtQValue?.toFixed(4) ?? '—'}</b>{pair.mtSignificantFdr10 && ' · FDR10'}</span>
            <span>Видимость <b>{pair.meshVisibleFraction != null ? Math.round(pair.meshVisibleFraction * 100) + '%' : '—'}</b></span>
            <span>Мимика <b>{pair.smileDetectedA !== pair.smileDetectedB ? '⚠ различается' : 'совпадает'}</b></span>
          </div>

          <h4>Топ-зоны по rmse</h4>
          <div className="m-sec m-topzones">
            {topZones.length === 0 && <p className="m-note">Зональных измерений нет.</p>}
            {topZones.map(z => (
              <div key={z.zone} className="m-zone-row">
                <span className="m-zone-dot" style={{ background: heatColor((z.rmse! / maxRmse) * 100, settings) }} />
                <span>{zoneLabel(z.zone)}</span>
                <b>{z.rmse!.toFixed(4)}</b>
              </div>
            ))}
          </div>
        </aside>
      </div>

      <footer className="morph-foot">
        <span>←/→ — шаг морфинга · Пробел — авто · Esc — закрыть · Клик по сцене — перетаскивание недоступно (статика) — данные: raw rmse, не z</span>
      </footer>
    </div>
  )
}
