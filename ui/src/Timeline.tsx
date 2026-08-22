import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Frame, PairConnection, PhotoMetrics, ZoneMetric, PoseBin } from './types'
import { getPoseColor } from './types'
import { classifyPair, getFrameEvents, pickDisplayPair, dominantZone, zoneLabel } from './timeline-data-contract'
import './TimelineV2.css'

type Props = {
  frames: Frame[]
  pairs: PairConnection[]
  photoMetrics: Map<string, PhotoMetrics>
  zones: Map<string, ZoneMetric[]>
  selectedId: string | null
  selectedPairId: string | null
  onSelect: (id: string) => void
  onPairClick: (p: PairConnection) => void
  onPairSelect?: (id: string | null) => void
  collapsed?: Set<string>
  initialSlot?: number
  initialScroll?: number
  onViewChange?: (slot: number, scroll: number) => void
  axisMode?: 'calendar' | 'order'
  contextPoses?: Array<{ bin: PoseBin; label: string; frames: Frame[] }>
  contextCandidates?: Map<string, Set<string>>
  onContextPoseClick?: (bin: PoseBin, frameId: string) => void
  onAnnotationClick?: (a: any) => void
  annotations?: any[]
}

/* ── Видимый элемент ряда: каждый кадр сам по себе, стеков нет ── */
interface VisibleItem {
  frame: Frame
  i: number
}

/*
 * TIMELINE V8 — доводка до 95+. Что и почему изменено относительно V7-dev:
 *
 * ФАЗА 1. Целостность сетки
 *  - Стек same-day занимает ТОЛЬКО слот первого кадра даты. Раскрытие —
 *    плавающая панель-поверхность под фото-рядом, а не centerX(i+fi):
 *    в V7-dev раскрытые кадры наезжали на чужие слоты и рвали синхронизацию
 *    всех дорожек. Панель не меняет сетку вообще.
 *  - События и роли кадров внутри стека АГРЕГИРУЮТСЯ в маркер стека (+n),
 *    а не исчезают молча.
 *  - Повторный клик/Esc сворачивает стек.
 *  - Скрытые группы дорожек освобождают высоту: доли считаются динамически.
 *  - Readout перенесён вправо — в V7-dev он перекрывал подпись дорожки.
 *
 * ФАЗА 2. Зональный слой (zone_metrics.json, 567 измерений, ранее 0 отображений)
 *  - Opt-in слой «Зоны»: глиф 3×3 с доминантной зоной пары.
 *  - robustZ зон НЕ отображается: в текущем export он некалиброван
 *    (calibrationStatus=insufficient_calibration, медиана ~2.8e6). Показывать
 *    его как z было бы фабрикацией. Доминант выбирается по raw rmse.
 *
 * ФАЗА 3. Persistence
 *  - Цепочки подряд идущих candidate/persistent пар = интервальная заливка:
 *    устойчивый сдвиг отличим от одиночного скачка одним взглядом.
 *  - Закладки кластеров кандидатов на minimap (кликабельны).
 *
 * ФАЗА 5. A11y: hit-area ≥12px у маркеров, tabIndex на точках пар,
 *    focus-visible стили, нативные <title> у всех маркеров.
 *
 * ФАЗА 7. onViewChange (debounced) отдаёт slot/scroll в App для URL state
 *    через history.replaceState — без засорения истории браузера.
 */

/* V3/Этап 5: zoom limits по читаемости миниатюр.
   thumbW = slot − gap (gap = 0.12·slot при slot≥12.5), т.е. thumbW ≈ 0.88·slot.
   V3: минимальная ширина thumbnail 52px, максимальная 112px →
   slot ∈ [60, 128]. Вне диапазона wheel-зум не выходит (без overlap и скачков).
   Позднее MIN_SLOT понижен до 32 — глубже зум-out (левая колонка подписей
   удалена, поэтому сетка начинается сразу у края). */
const MIN_SLOT = 32
const MAX_SLOT = 128
const GUTTER = 40
const MINI_H = 30
const Z_MAX = 36
const Z_DOT_COLORS = ['#5e9fe8', '#4fb9c9', '#de9255', '#72bc8f', '#bf8eda'] // RMSE/Median/P95/PtPlane-RMSE/PtPlane-Median z
const log = Math.log1p
const un = (v: number | null | undefined) => (v == null || !Number.isFinite(v) ? null : v)
const CAND_KINDS = new Set(['candidate', 'persistent'])

export function Timeline({ frames, pairs, photoMetrics, zones, selectedId, selectedPairId, onSelect, onPairClick, onPairSelect, collapsed, initialSlot, initialScroll, onViewChange }: Props) {
  const viewport = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 1200, height: 700 })
  const [slot, setSlot] = useState(initialSlot ?? 86)
  const [scroll, setScroll] = useState(initialScroll ?? 0)
  const [dragging, setDragging] = useState(false)
  const [hoverFrame, setHoverFrame] = useState<Frame | null>(null)
  const [hoverPair, setHoverPair] = useState<PairConnection | null>(null)
  const [cursorI, setCursorI] = useState<number | null>(null)

  const cam = useRef({ slot, scroll })
  cam.current = { slot, scroll }
  const dragStart = useRef({ x: 0, scroll: 0 })
  const raf = useRef(0)
  const maxScrollRef = useRef(0)
  const viewTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    const el = viewport.current
    if (!el) return
    const ro = new ResizeObserver(() => setSize({ width: el.clientWidth, height: el.clientHeight }))
    ro.observe(el)
    setSize({ width: el.clientWidth, height: el.clientHeight })
    return () => ro.disconnect()
  }, [])

  // ── Единый масштаб: всё выводится из slot (пропорциональный zoom) ──
  const gap = Math.max(1.5, slot * 0.12)
  const thumbW = slot - gap
  const iconSize = Math.max(16, Math.min(26, slot * 0.3))
  const photoH = Math.max(16, Math.min(150, thumbW * 1.25))
  const centerX = useCallback((i: number) => GUTTER + i * slot + slot / 2, [slot])
  const contentW = Math.max(size.width + 1, GUTTER + frames.length * slot + 48)
  const maxScroll = Math.max(0, contentW - size.width)
  maxScrollRef.current = maxScroll

  const scheduleScroll = useCallback((v: number) => {
    const clamped = Math.max(0, Math.min(maxScrollRef.current, v))
    cancelAnimationFrame(raf.current)
    raf.current = requestAnimationFrame(() => setScroll(clamped))
  }, [])

  // ── V8: debounce отдачи вида в URL (300ms после последнего изменения) ──
  useEffect(() => {
    if (!onViewChange) return
    if (viewTimer.current) clearTimeout(viewTimer.current)
    viewTimer.current = setTimeout(() => onViewChange(slot, Math.round(scroll)), 300)
    return () => { if (viewTimer.current) clearTimeout(viewTimer.current) }
  }, [slot, scroll, onViewChange])

  useEffect(() => {
    const el = viewport.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const { slot: s, scroll: sc } = cam.current
      if (!e.shiftKey && Math.abs(e.deltaY) >= Math.abs(e.deltaX)) {
        const cursor = e.clientX - el.getBoundingClientRect().left
        const next = Math.max(MIN_SLOT, Math.min(MAX_SLOT, s * (e.deltaY > 0 ? 0.9 : 1.1)))
        if (next === s) return
        const logical = (sc + cursor - GUTTER) / s
        const nextScroll = logical * next + GUTTER - cursor
        cancelAnimationFrame(raf.current)
        raf.current = requestAnimationFrame(() => { setSlot(next); setScroll(Math.max(0, Math.min(maxScrollRef.current, nextScroll))) })
      } else {
        scheduleScroll(sc + (e.deltaX || e.deltaY))
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [scheduleScroll])

  // ── Auto-scroll только при смене выбора (иначе «дерется» с zoom) ──
  const lastSelected = useRef<string | null>(null)
  useEffect(() => {
    if (selectedId === lastSelected.current) return
    lastSelected.current = selectedId
    const i = frames.findIndex(f => f.id === selectedId)
    if (i < 0) return
    const px = centerX(i)
    const { scroll: sc } = cam.current
    if (px < sc + GUTTER) setScroll(Math.max(0, px - GUTTER - slot))
    else if (px > sc + size.width - slot) setScroll(Math.min(maxScrollRef.current, px - size.width + slot * 2))
  }, [selectedId, frames, centerX, size.width, slot])

  const index = useMemo(() => new Map(frames.map((f, i) => [f.id, i])), [frames])
  const byFrame = useMemo(() => {
    const map = new Map<string, PairConnection[]>()
    for (const p of pairs) for (const id of [p.photoA, p.photoB]) map.set(id, [...(map.get(id) ?? []), p])
    return map
  }, [pairs])
  const c = useMemo(() => collapsed ?? new Set<string>(), [collapsed])
  const showFamilies = !c.has('pair_families')
  const graphPairs = useMemo(
    () => pairs.filter(p => index.has(p.photoB) && (showFamilies || p.pairType === 'adjacent')),
    [pairs, index, showFamilies]
  )
  const selectedPair = useMemo(() => pairs.find(p => p.pairId === selectedPairId) ?? null, [pairs, selectedPairId])
  const endpoints = useMemo(() => new Set(selectedPair ? [selectedPair.photoA, selectedPair.photoB] : []), [selectedPair])

  const lastPair = useRef<string | null>(null)
  useEffect(() => {
    if (!selectedPair || selectedPair.pairId === lastPair.current) return
    lastPair.current = selectedPair.pairId
    const ia = index.get(selectedPair.photoA), ib = index.get(selectedPair.photoB)
    if (ia == null || ib == null) return
    const xA = centerX(ia), xB = centerX(ib)
    const { scroll: sc } = cam.current
    const vw = size.width
    const span = xB - xA
    if (span + GUTTER + 80 < vw) {
      const mid = (xA + xB) / 2
      if (xA < sc + GUTTER || xB > sc + vw - 40) setScroll(Math.max(0, Math.min(maxScrollRef.current, mid - vw / 2)))
    } else if (xB < sc + GUTTER || xB > sc + vw - 40) {
      setScroll(Math.max(0, Math.min(maxScrollRef.current, xB - vw + GUTTER + 80)))
    }
  }, [selectedPair, index, centerX, size.width])

  /* ── Видимые кадры: каждый фото всегда отдельной миниатюрой, никаких стеков.
        Фильтр по видимости защищает от рендера тысяч узлов при zom-out. ── */
  const visible = useMemo<VisibleItem[]>(() => {
    const inView = (i: number) => centerX(i) > scroll - slot * 2 && centerX(i) < scroll + size.width + slot * 2
    return frames.map((frame, i) => ({ frame, i })).filter(v => inView(v.i))
  }, [frames, centerX, scroll, size.width, slot])

  /* События кадра */
  const eventsOf = useCallback((v: VisibleItem) => {
    const ps = byFrame.get(v.frame.id) ?? []
    const ev = getFrameEvents(v.frame, ps)
    if (ps.some(p => p.smileDetectedA !== p.smileDetectedB || p.jawOpenDetectedA !== p.jawOpenDetectedB))
      ev.push({ kind: 'limited', label: 'Мимика A/B различается (confounder)', symbol: 'E' })
    return ev
  }, [byFrame])

  const roleOf = useCallback((v: VisibleItem) => {
    const ps = byFrame.get(v.frame.id) ?? []
    const a = ps.some(p => p.photoA === v.frame.id)
    const b = ps.some(p => p.photoB === v.frame.id)
    return a && b ? '⇄' : a ? 'A' : b ? 'B' : ''
  }, [byFrame])

  // ── V8: динамические доли дорожек — скрытая группа освобождает место ──
  const bands = useMemo(() => {
    const defs = [
      { key: 'pair', frac: 0.34 },
      { key: 'support', frac: 0.16 },
      { key: 'applicability', frac: 0.17 },
      { key: 'quality', frac: 0.33 },
    ].filter(b => {
      if (b.key === 'quality') return !c.has('quality') || !c.has('quality_ext')
      if (b.key === 'support') return !c.has('support') || !c.has('support_ext')
      if (b.key === 'applicability') return !c.has('applicability') || !c.has('expression')
      return !c.has(b.key)
    })
    const total = defs.reduce((s, b) => s + b.frac, 0) || 1
    let acc = 0
    return defs.map(b => { const top = acc; acc += b.frac / total; return { ...b, top, bottom: acc } })
  }, [c])
  const bandOf = (key: string) => bands.find(b => b.key === key)
  const bandLabels: Record<string, string> = {
    pair: 'z / пары',
    support: 'поддержка',
    applicability: 'QC',
    quality: 'кожа',
  }

  const roleH = Math.max(22, Math.min(38, iconSize + 12))
  const evH = roleH, qcH = roleH, rulerH = 40
  const availableGraphH = size.height - photoH - roleH - evH - qcH - rulerH - MINI_H
  // Аналитическая дорожка должна оставаться компактной: свободное место окна
  // не должно растягивать графики в высокий пустой плакат.
  const graphH = Math.min(280, Math.max(220, availableGraphH))
  const stackH = graphH + photoH + roleH + evH + qcH + rulerH
  const layoutH = Math.max(0, size.height - MINI_H)
  const layoutTop = Math.max(8, Math.floor((layoutH - stackH) / 2))
  const graphTop = layoutTop
  const photoTop = graphTop + graphH
  const roleTop = photoTop + photoH
  const evTop = roleTop + roleH
  const qcTop = evTop + evH
  const rulerTop = qcTop + qcH
  const bb = (key: string, padT: number, padB: number) => {
    const b = bandOf(key)
    return b ? { top: b.top * graphH + padT, bottom: b.bottom * graphH - padB } : null
  }

  const mapY = useCallback((v: number, min: number, max: number, top: number, bottom: number) =>
    bottom - Math.max(0, Math.min(1, (v - min) / Math.max(0.0001, max - min))) * (bottom - top), [])
  const geoB = bb('pair', 30, 10)
  const zY = useCallback((z: number) => geoB ? geoB.bottom - (log(Math.max(0, z)) / log(Z_MAX)) * (geoB.bottom - geoB.top) : 0, [geoB])

  const series = useMemo(() => {
    const app = bb('applicability', 26, 10), q = bb('quality', 26, 10)
    const line = (get: (f: Frame, m?: PhotoMetrics) => number | null, min: number, max: number, top: number, bottom: number) => {
      let d = '', pen = false
      for (let i = 0; i < frames.length; i++) {
        const f = frames[i]
        const v = get(f, photoMetrics.get(f.id))
        if (v == null) { pen = false; continue }
        d += (pen ? 'L' : 'M') + (GUTTER + i * slot + slot / 2).toFixed(1) + ' ' + mapY(v, min, max, top, bottom).toFixed(1)
        pen = true
      }
      return d
    }
    return {
      alignment: app ? line((_, m) => un(m?.alignmentQuality), 0, 1, app.top, app.bottom) : '',
      expression: app ? line((_, m) => un(m?.expressionMagnitude), 2.8, 10.2, app.top, app.bottom) : '',
      jawOpen: app ? line((_, m) => un(m?.jawOpenDegree), 0, 142, app.top, app.bottom) : '',
      cornerLift: app ? line((_, m) => un(m?.cornerLiftIoc), -0.07, 0.11, app.top, app.bottom) : '',
      sharpness: q ? line((_, m) => m?.laplacianVariance == null ? null : log(m.laplacianVariance), log(20), log(2000), q.top, q.bottom) : '',
      noise: q ? line((_, m) => un(m?.noiseResidualMean), 0.2, 3, q.top, q.bottom) : '',
      skinQuality: q ? line((_, m) => un(m?.skinQualityScore), 0.3, 1, q.top, q.bottom) : '',
      skinAuth: q ? line((_, m) => un(m?.skinAuthenticityScore), -1.5, 3.5, q.top, q.bottom) : '',
      anisotropy: q ? line((_, m) => un(m?.gradientAnisotropy), 1, 3.7, q.top, q.bottom) : '',
      hardArea: q ? line((_, m) => un(m?.hardAreaFraction), 0.2, 0.6, q.top, q.bottom) : '',
    }
  }, [frames, photoMetrics, slot, bands, graphH, mapY]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Марки пар (все семейства) + V8: зоны, FDR, z-suite ──
  const pairMarks = useMemo(() => {
    const sup = bb('support', 26, 10), app = bb('applicability', 26, 10)
    return graphPairs.map(p => {
      const ib = index.get(p.photoB)!
      const x = GUTTER + ib * slot + slot / 2
      const xA = index.has(p.photoA) ? GUTTER + index.get(p.photoA)! * slot + slot / 2 : null
      const z = un(p.meshMaxRobustZ)
      const y = z == null || !geoB ? (geoB?.bottom ?? 0) : zY(z)
      const vis = un(p.meshVisibleFraction)
      const barH = vis == null || !sup ? 0 : Math.max(1, vis * (sup.bottom - sup.top))
      const verts = un(p.meshCommonVertexCount)
      const anchor = un(p.meshAnchorFraction)
      const resid = un(p.meshAlignResidualAfterMedian)
      const zDots = [p.meshRmseRobustZ, p.meshMedianRobustZ, p.meshP95RobustZ, p.meshPtPlaneRmseRobustZ, p.meshPtPlaneMedianRobustZ].map(v => un(v))
      const dz = c.has('zones') ? null : dominantZone(zones.get(p.pairId)) // V8: доминантная зона (opt-in слой)
      return { p, x, xA, z, y, barH, verts, anchor, resid, zDots, dz, sup, app, cls: classifyPair(p), selected: p.pairId === selectedPairId }
    })
  }, [graphPairs, index, slot, geoB, bands, zY, selectedPairId, c, zones]) // eslint-disable-line react-hooks/exhaustive-deps

  /* ── V8 PERSISTENCE: цепочки подряд идущих кандидатов = интервальная заливка.
        Почему: устойчивый сдвиг (главный довод ТЗ) раньше не отличался от одиночного скачка. ── */
  const persistenceBands = useMemo(() => {
    if (!geoB) return []
    const cands = graphPairs
      .filter(p => p.pairType === 'adjacent' && CAND_KINDS.has(classifyPair(p).kind) && index.has(p.photoA) && index.has(p.photoB))
      .map(p => ({ a: index.get(p.photoA)!, b: index.get(p.photoB)! }))
      .sort((u, v) => u.b - v.b)
    const chains: { a: number; b: number }[] = []
    let cur: { a: number; b: number } | null = null
    for (const pr of cands) {
      if (cur && pr.a <= cur.b + 1) cur.b = Math.max(cur.b, pr.b)
      else { if (cur && cur.b > cur.a) chains.push(cur); cur = { a: pr.a, b: pr.b } }
    }
    if (cur && cur.b > cur.a) chains.push(cur)
    return chains.filter(ch => ch.b - ch.a >= 1).map(ch => ({ x1: centerX(ch.a), x2: centerX(ch.b) }))
  }, [graphPairs, index, centerX, geoB])

  // ── Minimap: плотность + кандидаты + V8 закладки кластеров + окно ──
  const minimap = useMemo(() => {
    const BINS = 220
    const bins = new Array<number>(BINS).fill(0)
    frames.forEach((_, i) => { bins[Math.min(BINS - 1, Math.floor(i / frames.length * BINS))]++ })
    const maxBin = Math.max(1, ...bins)
    const cands = pairs
      .filter(p => CAND_KINDS.has(classifyPair(p).kind) && index.has(p.photoB))
      .map(p => index.get(p.photoB)! / Math.max(1, frames.length - 1))
      .sort((a, b) => a - b)
    const clusters: number[] = []
    let acc: number[] = []
    for (const f of cands) {
      if (acc.length && f - acc[acc.length - 1] > 0.02) { clusters.push(acc.reduce((s, x) => s + x, 0) / acc.length); acc = [] }
      acc.push(f)
    }
    if (acc.length) clusters.push(acc.reduce((s, x) => s + x, 0) / acc.length)
    return { bins, maxBin, clusters }
  }, [frames, pairs, index])
  const jumpTo = useCallback((clientX: number, el: SVGSVGElement) => {
    const r = el.getBoundingClientRect()
    const frac = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    setScroll(Math.max(0, Math.min(maxScrollRef.current, frac * contentW - size.width / 2)))
  }, [contentW, size.width])

  // ── Crosshair: V8 — readout отражает ВКЛЮЧЁННЫЕ треки, не фиксированный набор ──
  const cursorInfo = useMemo(() => {
    if (cursorI == null || !frames[cursorI]) return null
    const f = frames[cursorI]
    const m = photoMetrics.get(f.id)
    const near = pairMarks.filter(pm => Math.abs(pm.x - centerX(cursorI)) < slot / 2).map(pm => pm.p)
    const rows: [string, string][] = []
    if (!c.has('applicability')) rows.push(['align', m?.alignmentQuality?.toFixed(3) ?? '—'])
    if (!c.has('expression')) rows.push(['рот', m?.jawOpenDegree != null ? `${m.jawOpenDegree.toFixed(1)}°` : '—'])
    if (!c.has('quality')) {
      rows.push(['кожа', m?.skinQualityScore?.toFixed(2) ?? '—'], ['аут', m?.skinAuthenticityScore?.toFixed(2) ?? '—'])
    }
    const nearPair = near[0]
    if (nearPair) {
      rows.push(['пара z', nearPair.meshMaxRobustZ?.toFixed(1) ?? '—'])
      if (!c.has('zones')) {
        const dz = dominantZone(zones.get(nearPair.pairId))
        if (dz) rows.push(['топ-зона', `${zoneLabel(dz.zone)} rmse ${dz.rmse?.toFixed(4) ?? '—'}`])
      }
    }
    return { f, rows }
  }, [cursorI, frames, photoMetrics, pairMarks, centerX, slot, c, zones])

  const choosePair = (p: PairConnection) => { onPairSelect?.(p.pairId); onPairClick(p) }

  return (
    <div ref={viewport} className={`tl8 ${dragging ? 'drag' : ''}`}
      onPointerDown={e => {
        if ((e.target as HTMLElement).closest('[data-hit]')) return
        e.currentTarget.setPointerCapture(e.pointerId)
        setDragging(true)
        dragStart.current = { x: e.clientX, scroll: cam.current.scroll }
      }}
      onPointerMove={e => { if (dragging) scheduleScroll(dragStart.current.scroll - (e.clientX - dragStart.current.x)) }}
      onPointerUp={() => setDragging(false)} onPointerCancel={() => setDragging(false)}>

      <div className="lane-labels" aria-hidden="true">
        {bands.map(b => <span key={b.key} className="lane-label" style={{ top: graphTop + (b.top + b.bottom) * graphH / 2 - 7 }}>{bandLabels[b.key]}</span>)}
      </div>

      <div className="tl8-canvas" style={{ width: contentW, height: size.height - MINI_H, transform: `translate3d(${-scroll}px,0,0)` }}>
        <section className="lane graph-lane" style={{ top: graphTop, height: graphH }} role="img" aria-label="Графики метрик таймлайна"
          onMouseMove={e => {
            const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
            const i = Math.round((e.clientX - r.left - GUTTER) / slot - 0.5)
            setCursorI(i >= 0 && i < frames.length ? i : null)
          }}
          onMouseLeave={() => setCursorI(null)}>
          <svg width={contentW} height={graphH}>
            {bands.slice(1).map(b => <line key={b.key} x1={0} y1={b.top * graphH} x2={contentW} y2={b.top * graphH} className="band-sep" />)}

            {/* V8: persistence-интервалы под маркерами пар */}
            {geoB && persistenceBands.map((b, k) => (
              <rect key={'pb' + k} x={b.x1} y={geoB.top - 14} width={Math.max(4, b.x2 - b.x1)} height={8} className="persist-band">
                <title>Устойчивая цепочка candidate-пар (persistence)</title>
              </rect>
            ))}

            {!c.has('applicability') && series.alignment && <path d={series.alignment} className="ml align" />}
            {!c.has('applicability') && pairMarks.map(({ p, x, resid, app }) => resid == null || !app ? null :
              <circle key={'ar' + p.pairId} cx={x} cy={mapY(resid, 0, 0.045, app.top, app.bottom)} r={2} className="dot-residual"><title>Residual выравнивания: {resid.toFixed(4)}</title></circle>)}
            {!c.has('expression') && <>
              <path d={series.jawOpen} className="ml jaw" />
            </>}

            {!c.has('quality') && <>
              <path d={series.skinQuality} className="ml skinq" />
              <path d={series.skinAuth} className="ml skinauth" />
            </>}
            {!c.has('quality_ext') && <>
              <path d={series.anisotropy} className="ml aniso" />
              <path d={series.hardArea} className="ml hard" />
            </>}

            {!c.has('support') && pairMarks.map(({ p, x, barH, sup }) => barH <= 0 || !sup ? null :
              <circle key={'v' + p.pairId} cx={x} cy={sup.bottom - barH} r={Math.max(2.5, Math.min(4.5, slot * 0.055))} className="support-dot">
                <title>Видимость mesh: {(barH / (sup.bottom - sup.top) * 100).toFixed(0)}%</title>
              </circle>)}
            {!c.has('support_ext') && pairMarks.map(({ p, x, verts, anchor, sup }) => !sup ? null : (
              <g key={'sx' + p.pairId}>
                {verts != null && <circle cx={x} cy={mapY(log(verts), log(14000), log(23000), sup.top, sup.bottom)} r={2.2} className="dot-verts"><title>Общие вершины: {verts}</title></circle>}
                {anchor != null && <path d={`M${x},${mapY(anchor, 0.25, 0.38, sup.top, sup.bottom) - 3} l3,3 l-3,3 l-3,-3 Z`} className="dot-anchor"><title>Anchor fraction: {anchor.toFixed(3)}</title></path>}
              </g>))}

            {!c.has('pair') && geoB && pairMarks.map(({ p, x, xA, y, z, cls, selected, zDots, dz }) => {
              const isBase = p.pairType === 'baseline', isRoll = p.pairType === 'rolling_anchor'
              return (
                <g key={p.pairId} data-hit tabIndex={0} role="button"
                  aria-label={`Пара ${p.dateA} → ${p.dateB}, ${cls.label}`}
                  className={`pop ${cls.kind} ${isBase ? 'base' : ''} ${isRoll ? 'roll' : ''} ${selected ? 'sel' : ''}`}
                  onMouseEnter={() => setHoverPair(p)} onMouseLeave={() => setHoverPair(null)}
                  onFocus={() => setHoverPair(p)} onBlur={() => setHoverPair(null)}
                  onClick={() => choosePair(p)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') choosePair(p) }}>
                  <title>{`${cls.label}: ${p.dateA} → ${p.dateB} | max z ${p.meshMaxRobustZ?.toFixed(1) ?? '—'}`}</title>
                  {isBase && xA != null && <line x1={xA} y1={geoB.bottom} x2={x} y2={geoB.bottom} className="base-link" />}
                  <circle cx={x} cy={y} r={10} className="metric-badge" />
                  <text x={x} y={y + 3.2} textAnchor="middle" className="metric-value">
                    {z == null ? '—' : z.toFixed(1)}
                  </text>
                  {/* V8: прозрачная hit-area ≥12px — кликабельно при любом zoom */}
                  <circle cx={x} cy={y} r={Math.max(12, slot * 0.4)} className="hitpad" />
                  {p.mtSignificantFdr10 && <circle cx={x} cy={y} r={13} className="fdr-ring" />}
                  {!c.has('z_suite') && zDots.map((zv, k) => zv == null ? null :
                    <circle key={k} cx={x} cy={zY(zv)} r={1.6} fill={Z_DOT_COLORS[k]} opacity={0.8} />)}
                  {/* V8: зональный глиф 3×3 (opt-in «Зоны») — доминант по raw rmse */}
                  {dz && (
                    <g transform={`translate(${x - 6},${geoB.bottom + 6})`}>
                      {[0, 1, 2].map(r => [0, 1, 2].map(cc => {
                        const zn = `x_${['low', 'center', 'high'][r]}_${['low', 'center', 'high'][cc]}`
                        return <rect key={zn} x={cc * 4.5} y={r * 4.5} width={4} height={4}
                          className={`zone-cell ${zn === dz.zone ? 'hot' : ''}`} />
                      }))}
                      <title>Доминантная зона: {zoneLabel(dz.zone)} (rmse {dz.rmse?.toFixed(4) ?? '—'})</title>
                    </g>
                  )}
                </g>
              )
            })}
            {cursorI != null && <line x1={centerX(cursorI)} y1={0} x2={centerX(cursorI)} y2={graphH} className="crosshair" />}
          </svg>
        </section>

        <section className="lane photo-lane" style={{ top: photoTop, height: photoH }}>
          {visible.map(v => (
            <button key={v.frame.id} data-hit
              className={`ph ${v.frame.id === selectedId ? 'sel' : ''} ${endpoints.has(v.frame.id) ? 'ep' : ''}`}
              style={{ left: centerX(v.i) - thumbW / 2, width: thumbW, height: photoH - 8, background: getPoseColor(v.frame.poseBin) }}
              onClick={() => onSelect(v.frame.id)}
              onMouseEnter={() => setHoverFrame(v.frame)} onMouseLeave={() => setHoverFrame(null)}
              aria-label={`Фото ${v.frame.date}`}>
              <img src={`/storage/stage1/${v.frame.id}/thumb.jpg`} alt="" loading="lazy" draggable={false}
                onError={e => { const t = e.target as HTMLImageElement; t.style.display = 'none'; t.parentElement?.classList.add('noimg') }} />
            </button>
          ))}
        </section>

        <section className="lane mini-lane" style={{ top: roleTop, height: roleH }}>
          {visible.map(v => {
            const role = roleOf(v)
            if (!role) return null
            return <span key={v.frame.id} className={`mini role ${endpoints.has(v.frame.id) ? 'ep' : ''}`}
              style={{ left: centerX(v.i) - iconSize / 2, width: iconSize, height: iconSize, fontSize: Math.max(7, iconSize * 0.42) }}>{role}</span>
          })}
        </section>

        <section className="lane mini-lane" style={{ top: evTop, height: evH }}>
          {!c.has('events') && visible.map(v => {
            const evPairs = (byFrame.get(v.frame.id) ?? []).filter(p => CAND_KINDS.has(classifyPair(p).kind))
            const p = evPairs.length ? pickDisplayPair(evPairs, 'evidence') : undefined
            if (!p) return null
            const cl = classifyPair(p)
            const extra = evPairs.length - 1
            return <button key={v.frame.id} data-hit className={`mini ev ${cl.kind}`}
              style={{ left: centerX(v.i) - iconSize / 2, width: iconSize, height: iconSize, fontSize: Math.max(7, iconSize * 0.5) }}
              onClick={() => choosePair(p)}
              title={`${cl.label}: ${p.dateA} → ${p.dateB} | z ${p.meshMaxRobustZ?.toFixed(1) ?? '—'}${extra > 0 ? ` · ещё ${extra} пар(ы)` : ''}`}
              aria-label={`${cl.label}, ${p.dateA} → ${p.dateB}`}>
              {cl.symbol}{extra > 0 && <sup className="cnt">+{extra}</sup>}
            </button>
          })}
        </section>

        <section className="lane mini-lane qc" style={{ top: qcTop, height: qcH }}>
          {!c.has('events') && visible.map(v => {
            const ev = eventsOf(v)
            if (!ev.length) return null
            const extra = ev.length - 1
            return <button key={v.frame.id} data-hit className={`mini ev ${ev[0].kind}`}
              style={{ left: centerX(v.i) - iconSize / 2, width: iconSize, height: iconSize, fontSize: Math.max(6, iconSize * 0.42) }}
              title={ev.map(e => e.label).join(' · ')}
              aria-label={ev.map(e => e.label).join(', ')}>
              {ev[0].symbol}{extra > 0 && <sup className="cnt">+{extra}</sup>}
            </button>
          })}
        </section>

        <section className="lane ruler" style={{ top: rulerTop, height: rulerH }}>
          <svg width={contentW} height={rulerH}>
            {slot >= 110 && frames.map((f, i) => f.date.slice(0, 7) !== frames[i - 1]?.date.slice(0, 7) ? <line key={f.id} x1={centerX(i)} y1={rulerH - 14} x2={centerX(i)} y2={rulerH - 2} className="tk mo" /> : null)}
            {frames.map((f, i) => f.year !== frames[i - 1]?.year ? (
              <g key={f.id}><line x1={centerX(i)} y1={rulerH - 24} x2={centerX(i)} y2={rulerH - 2} className="tk yr" />
                <text x={centerX(i) + 4} y={rulerH - 10} className="tk-label">{f.year}</text></g>
            ) : null)}
          </svg>
        </section>
      </div>

      <svg className="minimap" height={MINI_H} role="navigation" aria-label="Миникарта: плотность кадров, кластеры кандидатов, окно просмотра"
        onPointerDown={e => { jumpTo(e.clientX, e.currentTarget); e.currentTarget.setPointerCapture(e.pointerId) }}
        onPointerMove={e => { if (e.buttons === 1) jumpTo(e.clientX, e.currentTarget) }}>
        {minimap.bins.map((n, k) => n === 0 ? null :
          <rect key={k} x={`${k / minimap.bins.length * 100}%`} y={MINI_H - 4 - (n / minimap.maxBin) * (MINI_H - 12)} width={`${100 / minimap.bins.length}%`} height={(n / minimap.maxBin) * (MINI_H - 12)} className="mm-bin" />)}
        {minimap.clusters.map((cf, k) => (
          <path key={k} data-hit className="mm-book" d={`M0,0 l4,6 l-8,0 Z`} transform={`translate(0,0)`}
            style={{ transform: `translateX(${cf * 100}%)` }}
            onClick={e => { e.stopPropagation(); setScroll(Math.max(0, Math.min(maxScrollRef.current, cf * contentW - size.width / 2))) }}>
            <title>Кластер кандидатов — перейти</title>
          </path>))}
        <rect className="mm-view" x={`${scroll / contentW * 100}%`} y={1} width={`${Math.min(100, size.width / contentW * 100)}%`} height={MINI_H - 2} />
      </svg>

      {/* V8: readout справа (в V7-dev перекрывал band-label слева) */}
      {cursorInfo && <div className="readout" role="status">
        <strong>{cursorInfo.f.date}</strong>
        {cursorInfo.rows.map(([k, v]) => <span key={k}>{k} {v}</span>)}
      </div>}

      {hoverFrame && !cursorInfo && <div className="inspector">
        <strong>{hoverFrame.date}</strong>
        <span>yaw {hoverFrame.yaw.toFixed(1)}° · pitch {hoverFrame.pitch.toFixed(1)}° · roll {hoverFrame.roll.toFixed(1)}°</span>
        <span>видимость {(hoverFrame.combinedVisibleFraction * 100).toFixed(0)}% · alignment {photoMetrics.get(hoverFrame.id)?.alignmentQuality?.toFixed(2) ?? '—'}</span>
      </div>}
      {hoverPair && <div className="inspector pair">
        <strong>{classifyPair(hoverPair).label}</strong>
        <span>{hoverPair.dateA} → {hoverPair.dateB} · {hoverPair.pairType}</span>
        <span>z {hoverPair.meshMaxRobustZ?.toFixed(1) ?? '—'} · q {hoverPair.mtQValue?.toFixed(3) ?? '—'}{hoverPair.mtSignificantFdr10 ? ' · FDR10' : ''}</span>
      </div>}

      {/* V8: empty-state для ракурсов с малым числом кадров / пустой ракурс */}
      {frames.length === 0 && <div className="empty-state">
        Нет кадров для этого ракурса — выберите другой в списке поз или проверьте данные.
      </div>}
      {frames.length === 1 && <div className="empty-state">
        В этом ракурсе всего 1 кадр и {pairs.length} пар(ы) — одинокая точка не образует доказательной базы.
      </div>}
      {frames.length > 1 && frames.length <= 8 && <div className="empty-state">
        В этом ракурсе только {frames.length} кадра(ов) и {pairs.length} пар(ы) — доказательная база слабая. Выберите более плотный ракурс (например, анфас).
      </div>}
    </div>
  )
}
