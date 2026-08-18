import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Frame, PairConnection, PhotoMetrics, PoseBin, TimelineAnnotation, ZoneMetric } from './types'
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
  /* V10: честная календарная ось (calendar) или порядок кадров (order) */
  axisMode?: 'calendar' | 'order'
  /* V10: контекст-полосы остальных ракурсов под фото-рядом */
  contextPoses?: { bin: PoseBin; label: string; frames: Frame[] }[]
  contextCandidates?: Map<string, Set<string>>
  onContextPoseClick?: (bin: PoseBin, frameId: string) => void
  /* V10: заметки журналиста на линейке */
  annotations?: TimelineAnnotation[]
  onAnnotationClick?: (a: TimelineAnnotation) => void
}

/* ── V8: единый тип элемента ряда ── */
interface VisibleItem {
  frame: Frame
  i: number
  stackCount?: number
  groupFrames?: Frame[]
  groupIndices?: number[]
  x: number      // центр на canvas (в координатах ленты, без scroll)
  w: number      // ширина
}

/*
 * TIMELINE V10 — редизайн по документу docs/TIMELINE_REDESIGN_VISION.md.
 *
 * ГЛАВНЫЕ ИЗМЕНЕНИЯ:
 * 1. ЧЕСТНАЯ ОСЬ ВРЕМЕНИ (axisMode='calendar', по умолчанию): X = календарь
 *    с минимальным зазором MIN_GAP px между соседями. Плотные периоды
 *    кластеризуются в один элемент фото-ряда, редкие — честно растягиваются
 *    (пробел данных виден как пробел). Переключатель «время/порядок» в App.
 * 2. КРИВАЯ СТАБИЛЬНОСТИ: скользящая медиана robust-z по adjacent-парам +
 *    коридор нормы (q50–q90) + треугольные маркеры одиночных скачков.
 *    Устойчивый сдвиг (persistence) теперь отличим от скачка одним взглядом.
 * 3. КОНТЕКСТ-ПОЛОСЫ РАКУРСОВ: под фото-рядом 8 тонких дорожек остальных
 *    ракурсов с точками-кадрами (календарно выровнены). Кросс-ракурсная
 *    корроборация — взглядом, без переключения селектора.
 * 4. ЛИНЕЙКА: вертикальные линии возрастов Путина и публичных событий.
 * 5. ЗАМЕТКИ: флажки журналиста на датах (localStorage, App).
 * 6. Кламп initialSlot/initialScroll из URL (аудит-фикс) и якорь зума по
 *    доле контента (работает для обоих режимов оси).
 */

const MIN_SLOT = 60
const MAX_SLOT = 128
const STACK_SLOT = 72
const GUTTER = 152
const MINI_H = 30
const Z_MAX = 36
const DAY = 86400000
const MIN_GAP = 2 // px между разными датами при календарной оси
const Z_DOT_COLORS = ['#5e9fe8', '#4fb9c9', '#de9255', '#72bc8f', '#bf8eda', '#eac26b']
const log = Math.log1p
const un = (v: number | null | undefined) => (v == null || !Number.isFinite(v) ? null : v)
const CAND_KINDS = new Set(['candidate', 'persistent'])
const median = (arr: number[]) => {
  if (!arr.length) return 0
  const s = [...arr].sort((a, b) => a - b)
  return s[Math.floor(s.length / 2)]
}
/* V10: короткие подписи для контекст-полос (русские, 3/4 б/с/г = ближ/сред/глуб) */
const SHORT_POSE: Record<string, string> = {
  left_light: 'Л 3/4·б', right_light: 'П 3/4·б',
  left_mid: 'Л 3/4·с', right_mid: 'П 3/4·с',
  left_deep: 'Л 3/4·г', right_deep: 'П 3/4·г',
  left_profile: 'Л профиль', right_profile: 'П профиль',
}

/* События и возрасты на линейке (V10). Возраст — от 1952-10-07. */
const ageDate = (age: number) => {
  const d = new Date(1952, 9, 7)
  d.setFullYear(d.getFullYear() + age)
  return d.toISOString().slice(0, 10)
}
const RULER_AGES = [50, 55, 60, 65, 70].map(age => ({ date: ageDate(age), label: `ВП ${age}` }))
const RULER_EVENTS = [
  { date: '2000-05-07', label: '2000 инауг.' },
  { date: '2008-05-07', label: '2008 инауг.' },
  { date: '2012-05-07', label: '2012 инауг.' },
  { date: '2020-07-01', label: '2020 поправки' },
  { date: '2022-02-24', label: '2022' },
]

export function Timeline({ frames, pairs, photoMetrics, zones, selectedId, selectedPairId, onSelect, onPairClick, onPairSelect, collapsed, initialSlot, initialScroll, onViewChange, axisMode = 'calendar', contextPoses, contextCandidates, onContextPoseClick, annotations, onAnnotationClick }: Props) {
  const viewport = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 1200, height: 700 })
  // Аудит-фикс: URL-значения клампим, иначе #slot=9999 ломает layout.
  const [slot, setSlot] = useState(() => Math.min(MAX_SLOT, Math.max(MIN_SLOT, initialSlot ?? 86)))
  const [scroll, setScroll] = useState(() => Math.max(0, initialScroll ?? 0))
  const [dragging, setDragging] = useState(false)
  const [hoverFrame, setHoverFrame] = useState<Frame | null>(null)
  const [hoverPair, setHoverPair] = useState<PairConnection | null>(null)
  const [cursorI, setCursorI] = useState<number | null>(null)
  const [expandedStack, setExpandedStack] = useState<string | null>(null)

  const cam = useRef({ slot, scroll })
  cam.current = { slot, scroll }
  const dragStart = useRef({ x: 0, scroll: 0 })
  const raf = useRef(0)
  const hoverRaf = useRef(0)
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

  const gap = Math.max(1.5, slot * 0.12)
  const thumbW = slot - gap
  const iconSize = Math.max(16, Math.min(26, slot * 0.3))
  const photoH = Math.max(16, Math.min(150, thumbW * 1.25))

  /* ── V10: LAYOUT. calendar: X = календарь с мин. зазором; order: X = индекс. ── */
  const layout = useMemo(() => {
    const n = frames.length
    const xs = new Array<number>(n)
    if (axisMode !== 'calendar' || n < 2) {
      for (let i = 0; i < n; i++) xs[i] = GUTTER + i * slot + slot / 2
      return { xs, contentW: GUTTER + n * slot + 48, pxPerDay: slot }
    }
    const gaps: number[] = []
    for (let i = 1; i < n; i++) {
      const d = (frames[i].timestamp - frames[i - 1].timestamp) / DAY
      if (Number.isFinite(d) && d > 0) gaps.push(d)
    }
    const med = median(gaps) || 1
    const pxPerDay = Math.max(0.2, slot / Math.max(0.1, med))
    let x = GUTTER
    for (let i = 0; i < n; i++) {
      const dPrev = i > 0 ? (frames[i].timestamp - frames[i - 1].timestamp) / DAY : med
      const seg = i > 0 ? Math.max(MIN_GAP, dPrev * pxPerDay) : Math.max(MIN_GAP, med * pxPerDay)
      xs[i] = x + seg / 2
      x += seg
    }
    return { xs, contentW: x + 48, pxPerDay }
  }, [frames, slot, axisMode])

  const contentW = Math.max(size.width + 1, layout.contentW)
  const centerX = useCallback((i: number) => layout.xs[i] ?? GUTTER, [layout])
  const maxScroll = Math.max(0, contentW - size.width)
  maxScrollRef.current = maxScroll

  const scheduleScroll = useCallback((v: number) => {
    const clamped = Math.max(0, Math.min(maxScrollRef.current, v))
    cancelAnimationFrame(raf.current)
    raf.current = requestAnimationFrame(() => setScroll(clamped))
  }, [])

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
        // V10: якорь по доле контента (работает и для календарной оси)
        const ratio = next / s
        const nextScroll = Math.max(0, Math.min(maxScrollRef.current, (sc + cursor) * ratio - cursor))
        cancelAnimationFrame(raf.current)
        raf.current = requestAnimationFrame(() => { setSlot(next); setScroll(nextScroll) })
      } else {
        scheduleScroll(sc + (e.deltaX || e.deltaY))
      }
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [scheduleScroll])

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

  /* ── V10: элементы фото-ряда. order: кадры (+same-day стеки при zoom-out);
        calendar: кластеры перекрывающихся кадров (плотные периоды) ── */
  const items = useMemo<VisibleItem[]>(() => {
    const inView = (x: number, w: number) => x > scroll - w * 2 && x < scroll + size.width + w * 2
    if (axisMode === 'order') {
      const out: VisibleItem[] = []
      let i = 0
      while (i < frames.length) {
        const f = frames[i]
        const x = layout.xs[i]
        const w = thumbW
        if (slot <= STACK_SLOT) {
          let j = i
          while (j + 1 < frames.length && frames[j + 1].date === f.date) j++
          if (j > i) {
            const gf = frames.slice(i, j + 1)
            out.push({ frame: f, i, stackCount: gf.length, groupFrames: gf, groupIndices: gf.map((_, k) => i + k), x, w })
            i = j + 1
            continue
          }
        }
        out.push({ frame: f, i, x, w })
        i++
      }
      return out.filter(v => inView(v.x, v.w))
    }
    // calendar: кластеры — только при реальном перекрытии кадров (gap < thumbW),
    // и с ограничением размаха (иначе плотный месяц превращается в мега-бар)
    const out: VisibleItem[] = []
    const n = frames.length
    const maxSpan = thumbW * 2.2
    let start = 0
    const flush = (end: number) => {
      const gf = frames.slice(start, end)
      const gi: number[] = []
      for (let k = start; k < end; k++) gi.push(k)
      const x0 = layout.xs[start]
      const x1 = layout.xs[end - 1]
      const x = (x0 + x1) / 2
      const w = Math.max(thumbW, x1 - x0 + Math.min(thumbW, 16))
      out.push({ frame: gf[0], i: start, stackCount: gf.length > 1 ? gf.length : undefined, groupFrames: gf, groupIndices: gi, x, w })
      start = end
    }
    for (let i = 1; i <= n; i++) {
      const overlap = i < n && (layout.xs[i] - layout.xs[i - 1]) < thumbW && (layout.xs[i] - layout.xs[start]) < maxSpan
      if (!overlap) flush(i)
    }
    return out.filter(v => inView(v.x, v.w))
  }, [frames, layout.xs, scroll, size.width, slot, thumbW, axisMode])

  /* ── V10: контекст-полосы ракурсов (та же календарная шкала) ── */
  const ctxLanes = useMemo(() => {
    if (!contextPoses?.length) return []
    return contextPoses.map(lp => {
      const n = lp.frames.length
      const xs = new Array<number>(n)
      if (axisMode !== 'calendar' || n < 2) {
        for (let i = 0; i < n; i++) xs[i] = GUTTER + i * slot + slot / 2
      } else {
        let x = GUTTER
        for (let i = 0; i < n; i++) {
          const d = i > 0 ? (lp.frames[i].timestamp - lp.frames[i - 1].timestamp) / DAY : 1
          const seg = i > 0 ? Math.max(MIN_GAP, d * layout.pxPerDay) : Math.max(MIN_GAP, layout.pxPerDay)
          xs[i] = x + seg / 2
          x += seg
        }
      }
      return { bin: lp.bin, label: lp.label, frames: lp.frames, xs }
    })
  }, [contextPoses, axisMode, slot, layout.pxPerDay])

  const eventsOf = useCallback((v: VisibleItem) => {
    const framesToScan = v.groupFrames ?? [v.frame]
    const out: ReturnType<typeof getFrameEvents> = []
    const seen = new Set<string>()
    for (const f of framesToScan) {
      const ps = byFrame.get(f.id) ?? []
      const ev = getFrameEvents(f, ps)
      if (ps.some(p => p.smileDetectedA !== p.smileDetectedB || p.jawOpenDetectedA !== p.jawOpenDetectedB))
        ev.push({ kind: 'limited', label: 'Мимика A/B различается (confounder)', symbol: 'E' })
      if (ps.some(p => [p.meshRmseStatus, p.meshMedianStatus, p.meshP95Status, p.meshPtPlaneRmseStatus, p.meshPtPlaneMedianStatus, p.meshPtPlaneP95Status].includes('mesh_elevated_but_uncertain')))
        ev.push({ kind: 'limited', label: 'Неуверенный статус метрики (elevated_but_uncertain)', symbol: 'S' })
      for (const e of ev) { const k = e.kind + e.symbol; if (!seen.has(k)) { seen.add(k); out.push(e) } }
    }
    return out
  }, [byFrame])

  const roleOf = useCallback((v: VisibleItem) => {
    const framesToScan = v.groupFrames ?? [v.frame]
    let a = false, b = false
    for (const f of framesToScan) {
      const ps = byFrame.get(f.id) ?? []
      if (ps.some(p => p.photoA === f.id)) a = true
      if (ps.some(p => p.photoB === f.id)) b = true
    }
    return a && b ? '⇄' : a ? 'A' : b ? 'B' : ''
  }, [byFrame])

  /* ── V10: контекст-полосы съедают высоту графика честно ── */
  const ctxH = (!c.has('pose_lanes') && ctxLanes.length) ? ctxLanes.length * 16 : 0
  const bands = useMemo(() => {
    const defs = [
      { key: 'pair', frac: 0.30 },
      { key: 'raw_geom', frac: 0.20 },
      { key: 'support', frac: 0.14 },
      { key: 'applicability', frac: 0.17 },
      { key: 'quality', frac: 0.33 },
    ].filter(b => {
      if (b.key === 'quality') return !c.has('quality') || !c.has('quality_ext')
      if (b.key === 'support') return !c.has('support') || !c.has('support_ext')
      if (b.key === 'applicability') return !c.has('applicability') || !c.has('expression')
      if (b.key === 'raw_geom') return !c.has('raw_geom')
      return !c.has(b.key)
    })
    const total = defs.reduce((s, b) => s + b.frac, 0) || 1
    let acc = 0
    return defs.map(b => { const top = acc; acc += b.frac / total; return { ...b, top, bottom: acc } })
  }, [c])
  const bandOf = (key: string) => bands.find(b => b.key === key)

  const roleH = Math.max(22, Math.min(38, iconSize + 12))
  const evH = roleH, qcH = roleH, rulerH = 40
  const graphH = Math.max(200, size.height - photoH - ctxH - roleH - evH - qcH - rulerH - MINI_H)
  const photoTop = graphH
  const ctxTop = photoTop + photoH + 2
  const roleTop = photoTop + photoH + ctxH
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
        d += (pen ? 'L' : 'M') + (layout.xs[i]).toFixed(1) + ' ' + mapY(v, min, max, top, bottom).toFixed(1)
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
  }, [frames, photoMetrics, slot, bands, graphH, mapY, layout.xs]) // eslint-disable-line react-hooks/exhaustive-deps

  /* ── V10: КРИВАЯ СТАБИЛЬНОСТИ (rolling median z) + коридор нормы + скачки ── */
  const stab = useMemo(() => {
    if (!geoB) return null
    const pts = graphPairs
      .filter(p => p.pairType === 'adjacent' && p.meshMaxRobustZ != null && index.has(p.photoB))
      .map(p => ({ x: layout.xs[index.get(p.photoB)!], z: p.meshMaxRobustZ! }))
      .sort((a, b) => a.x - b.x)
    if (pts.length < 3) return null
    const win = Math.max(2, Math.min(6, Math.round(pts.length / 50)))
    let d = ''
    for (let k = 0; k < pts.length; k++) {
      const lo = Math.max(0, k - win), hi = Math.min(pts.length, k + win + 1)
      const med = median(pts.slice(lo, hi).map(p => p.z))
      d += (k ? 'L' : 'M') + pts[k].x.toFixed(1) + ' ' + zY(med).toFixed(1)
    }
    const sorted = pts.map(p => p.z).sort((a, b) => a - b)
    const q = (f: number) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * f))]
    const jumps = graphPairs
      .filter(p => p.pairType === 'adjacent' && p.meshMaxRobustZ != null && index.has(p.photoB) && classifyPair(p).kind === 'candidate')
      .map(p => ({ x: layout.xs[index.get(p.photoB)!], y: Math.max(geoB.top + 8, zY(p.meshMaxRobustZ!) - 2) }))
    return { d, q50: q(0.5), q90: q(0.9), jumps }
  }, [graphPairs, index, layout.xs, zY, geoB])

  const pairMarks = useMemo(() => {
    const sup = bb('support', 26, 10), app = bb('applicability', 26, 10)
    return graphPairs.map(p => {
      const ib = index.get(p.photoB)!
      const x = layout.xs[ib]
      const xA = index.has(p.photoA) ? layout.xs[index.get(p.photoA)!] : null
      const z = un(p.meshMaxRobustZ)
      const y = z == null || !geoB ? (geoB?.bottom ?? 0) : zY(z)
      const vis = un(p.meshVisibleFraction)
      const barH = vis == null || !sup ? 0 : Math.max(1, vis * (sup.bottom - sup.top))
      const verts = un(p.meshCommonVertexCount)
      const anchor = un(p.meshAnchorFraction)
      const resid = un(p.meshAlignResidualAfterMedian)
      const zDots = [p.meshRmseRobustZ, p.meshMedianRobustZ, p.meshP95RobustZ, p.meshPtPlaneRmseRobustZ, p.meshPtPlaneMedianRobustZ, p.meshPtPlaneP95RobustZ].map(v => un(v))
      const dz = c.has('zones') ? null : dominantZone(zones.get(p.pairId))
      return { p, x, xA, z, y, barH, verts, anchor, resid, zDots, dz, sup, app, cls: classifyPair(p), selected: p.pairId === selectedPairId }
    })
  }, [graphPairs, index, layout.xs, geoB, bands, zY, selectedPairId, c, zones]) // eslint-disable-line react-hooks/exhaustive-deps

  /* ── V14: RAW-геометрия пар: 6 сырых метрик + калибровочный коридор RMSE + статус-точки ── */
  const rawSeries = useMemo(() => {
    const b = bb('raw_geom', 26, 10)
    if (!b) return null
    const rMin = Math.log(0.0015), rMax = Math.log(0.08)
    const yOf = (v: number) => mapY(Math.log(v), rMin, rMax, b.top, b.bottom)
    const mkPath = (get: (p: PairConnection) => number | null) => {
      let d = '', pen = false
      for (const p of graphPairs) {
        const ib = index.get(p.photoB)
        if (ib == null) continue
        const v = get(p)
        if (v == null || v <= 0) { pen = false; continue }
        d += (pen ? 'L' : 'M') + layout.xs[ib].toFixed(1) + ' ' + yOf(v).toFixed(1)
        pen = true
      }
      return d
    }
    const metrics: [string, (p: PairConnection) => number | null, string][] = [
      ['rmse', p => p.meshRmse, 'ml raw rmse'],
      ['median', p => p.meshMedian, 'ml raw median'],
      ['p95', p => p.meshP95, 'ml raw p95'],
      ['ptr', p => p.meshPtPlaneRmse, 'ml raw ptr'],
      ['ptm', p => p.meshPtPlaneMedian, 'ml raw ptm'],
      ['ptp', p => p.meshPtPlaneP95, 'ml raw ptp'],
    ]
    const lines = metrics.map(([id, get, cls]) => ({ id, d: mkPath(get), cls }))
    // калибровочный коридор RMSE: замкнутый полигон между cal median и cal p95
    const calPts = (get: (p: PairConnection) => number | null) => {
      const pts: { x: number; y: number }[] = []
      for (const p of graphPairs) {
        const ib = index.get(p.photoB)
        if (ib == null) continue
        const v = get(p)
        if (v == null || v <= 0) continue
        pts.push({ x: layout.xs[ib], y: yOf(v) })
      }
      return pts
    }
    const loPts = calPts(p => p.meshRmseCalMedian)
    const upPts = calPts(p => p.meshRmseCalP95)
    let corridor = ''
    if (loPts.length && upPts.length) {
      corridor = 'M' + upPts.map(p => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' L')
        + ' L' + [...loPts].reverse().map(p => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' L') + ' Z'
    }
    const pathOf = (pts: { x: number; y: number }[]) => pts.length ? 'M' + pts.map(p => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' L') : ''
    // статус-точки: цвет по meshRmseStatus
    const statusDots: { x: number; y: number; st: string }[] = []
    for (const p of graphPairs) {
      const ib = index.get(p.photoB)
      if (ib == null || p.meshRmse == null) continue
      statusDots.push({ x: layout.xs[ib], y: yOf(p.meshRmse), st: p.meshRmseStatus || 'none' })
    }
    return { lines, up: pathOf(upPts), lo: pathOf(loPts), corridor, statusDots, yOf }
  }, [graphPairs, index, layout.xs, bb, mapY]) // eslint-disable-line react-hooks/exhaustive-deps

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

  const nearestIdx = useCallback((x: number) => {
    const xs = layout.xs
    if (!xs.length) return -1
    let lo = 0, hi = xs.length - 1
    while (lo < hi) { const m = (lo + hi) >> 1; if (xs[m] < x) lo = m + 1; else hi = m }
    if (lo > 0 && Math.abs(xs[lo - 1] - x) < Math.abs(xs[lo] - x)) return lo - 1
    return lo
  }, [layout.xs])

  const cursorInfo = useMemo(() => {
    if (cursorI == null || !frames[cursorI]) return null
    const f = frames[cursorI]
    const m = photoMetrics.get(f.id)
    const near = pairMarks.filter(pm => Math.abs(pm.x - centerX(cursorI)) < slot / 2).map(pm => pm.p)
    const rows: [string, string][] = []
    if (!c.has('applicability')) rows.push(['align', m?.alignmentQuality?.toFixed(3) ?? '—'])
    if (!c.has('expression')) rows.push(['экспр', m?.expressionMagnitude?.toFixed(2) ?? '—'])
    if (!c.has('quality')) {
      rows.push(['резк', m?.laplacianVariance?.toFixed(0) ?? '—'], ['шум', m?.noiseResidualMean?.toFixed(2) ?? '—'], ['кожа', m?.skinQualityScore?.toFixed(2) ?? '—'], ['аут', m?.skinAuthenticityScore?.toFixed(2) ?? '—'])
    }
    if (!c.has('quality_ext')) rows.push(['аниз', m?.gradientAnisotropy?.toFixed(2) ?? '—'])
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

  /* ── V10: X для даты (события линейки, заметки) ── */
  const xForDate = useCallback((iso: string) => {
    if (!frames.length) return GUTTER + 8
    const t = Date.parse(`${iso}T00:00:00Z`)
    if (!Number.isFinite(t)) return GUTTER + 8
    if (t <= frames[0].timestamp) return Math.max(GUTTER + 6, centerX(0) - 10)
    if (t >= frames[frames.length - 1].timestamp) return Math.min(contentW - 30, centerX(frames.length - 1) + 10)
    let lo = 0, hi = frames.length - 1
    while (lo < hi) { const m = (lo + hi) >> 1; if (frames[m].timestamp < t) lo = m + 1; else hi = m }
    return centerX(lo)
  }, [frames, centerX, contentW])

  const choosePair = (p: PairConnection) => { onPairSelect?.(p.pairId); onPairClick(p) }
  const expandedGroup = useMemo(() => items.find(v => v.stackCount && v.frame.id === expandedStack) ?? null, [items, expandedStack])

  return (
    <div ref={viewport} className={`tl8 ${dragging ? 'drag' : ''}`}
      onPointerDown={e => {
        if ((e.target as HTMLElement).closest('[data-hit]')) return
        e.currentTarget.setPointerCapture(e.pointerId)
        setDragging(true)
        setExpandedStack(null)
        dragStart.current = { x: e.clientX, scroll: cam.current.scroll }
      }}
      onPointerMove={e => { if (dragging) scheduleScroll(dragStart.current.scroll - (e.clientX - dragStart.current.x)) }}
      onPointerUp={() => setDragging(false)} onPointerCancel={() => setDragging(false)}>

      <div className="tl8-canvas" style={{ width: contentW, height: size.height - MINI_H, transform: `translate3d(${-scroll}px,0,0)` }}>
        <section className="lane graph-lane" style={{ height: graphH }} role="img" aria-label="Графики метрик таймлайна"
          onMouseMove={e => {
            const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
            const x = e.clientX - r.left + scroll
            const i = nearestIdx(x)
            if (hoverRaf.current) return
            hoverRaf.current = requestAnimationFrame(() => { hoverRaf.current = 0; setCursorI(i >= 0 && i < frames.length ? i : null) })
          }}
          onMouseLeave={() => { if (hoverRaf.current) cancelAnimationFrame(hoverRaf.current); hoverRaf.current = 0; setCursorI(null) }}>
          <svg width={contentW} height={graphH}>
            {bands.slice(1).map(b => <line key={b.key} x1={0} y1={b.top * graphH} x2={contentW} y2={b.top * graphH} className="band-sep" />)}
            {geoB && !c.has('pair') && [3, 5, 10, 20].map(v => (
              <g key={v}><line x1={GUTTER} y1={zY(v)} x2={contentW} y2={zY(v)} className="ref" /><text x={GUTTER - 8} y={zY(v) + 3} className="axis-label">z={v}</text></g>
            ))}

            {/* V10: коридор нормы + кривая стабильности + скачки */}
            {geoB && stab && (
              <g>
                <rect className="stab-band" x={GUTTER} y={zY(stab.q90)} width={Math.max(0, contentW - GUTTER)} height={Math.max(0, geoB.bottom - zY(stab.q90))}>
                  <title>Коридор нормы: q50–q90 robust-z этого ракурса (q90={stab.q90.toFixed(1)})</title>
                </rect>
                <path d={stab.d} className="ml stab" />
                {stab.jumps.map(j => (
                  <path key={j.x} className="jump-mark" d={`M${j.x - 3},${j.y - 1} L${j.x + 3},${j.y - 1} L${j.x},${j.y - 7} Z`}>
                    <title>Одиночный скачок (candidate, без persistence)</title>
                  </path>
                ))}
              </g>
            )}

            {geoB && persistenceBands.map((b, k) => (
              <rect key={'pb' + k} x={b.x1} y={geoB.top - 14} width={Math.max(4, b.x2 - b.x1)} height={8} className="persist-band">
                <title>Устойчивая цепочка candidate-пар (persistence)</title>
              </rect>
            ))}

            {/* V14: RAW-геометрия: коридор калибровки + линии + статус-точки */}
            {!c.has('raw_geom') && rawSeries && (
              <g>
                {rawSeries.corridor && <path d={rawSeries.corridor} className="cal-corridor" />}
                {rawSeries.up && <path d={rawSeries.up} className="cal-ref up" />}
                {rawSeries.lo && <path d={rawSeries.lo} className="cal-ref lo" />}
                {rawSeries.lines.map(l => <path key={l.id} d={l.d} className={l.cls} />)}
                {rawSeries.statusDots.map((d, k) => (
                  <circle key={'st' + k} cx={d.x} cy={d.y} r={2.2} className={`status-dot ${d.st}`}>
                    <title>Статус RMSE: {d.st === 'none' ? 'без калибровочного статуса' : d.st}</title>
                  </circle>
                ))}
              </g>
            )}
            {!c.has('applicability') && series.alignment && <path d={series.alignment} className="ml align" />}
            {!c.has('applicability') && pairMarks.map(({ p, x, resid, app }) => resid == null || !app ? null :
              <circle key={'ar' + p.pairId} cx={x} cy={mapY(resid, 0, 0.045, app.top, app.bottom)} r={2} className="dot-residual"><title>Residual выравнивания: {resid.toFixed(4)}</title></circle>)}
            {!c.has('expression') && <>
              <path d={series.expression} className="ml expr" />
              <path d={series.jawOpen} className="ml jaw" />
              <path d={series.cornerLift} className="ml corner" />
            </>}

            {!c.has('quality') && <>
              <path d={series.sharpness} className="ml sharp" />
              <path d={series.noise} className="ml noise" />
              <path d={series.skinQuality} className="ml skinq" />
              <path d={series.skinAuth} className="ml skinauth" />
            </>}
            {!c.has('quality_ext') && <>
              <path d={series.anisotropy} className="ml aniso" />
              <path d={series.hardArea} className="ml hard" />
            </>}

            {!c.has('support') && pairMarks.map(({ p, x, barH, sup }) => barH <= 0 || !sup ? null :
              <rect key={'v' + p.pairId} x={x - Math.max(1, slot * 0.14)} y={sup.bottom - barH} width={Math.max(2, slot * 0.28)} height={barH} className="support-bar" />)}
            {!c.has('support_ext') && pairMarks.map(({ p, x, verts, anchor, sup }) => !sup ? null : (
              <g key={'sx' + p.pairId}>
                {verts != null && <circle cx={x} cy={mapY(log(verts), log(14000), log(23000), sup.top, sup.bottom)} r={2.2} className="dot-verts"><title>Общие вершины: {verts}</title></circle>}
                {anchor != null && <path d={`M${x},${mapY(anchor, 0.25, 0.38, sup.top, sup.bottom) - 3} l3,3 l-3,3 l-3,-3 Z`} className="dot-anchor"><title>Anchor fraction: {anchor.toFixed(3)}</title></path>}
              </g>))}

            {!c.has('pair') && geoB && pairMarks.map(({ p, x, xA, y, cls, selected, zDots, dz }) => {
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
                  <line x1={x} y1={geoB.bottom} x2={x} y2={y} />
                  {isRoll
                    ? <rect x={x - 3} y={y - 3} width={selected ? 10 : 6} height={selected ? 10 : 6} className="sq" />
                    : <circle cx={x} cy={y} r={selected ? 6 : 3.5} className={isBase ? 'hollow' : ''} />}
                  <circle cx={x} cy={y} r={Math.max(12, slot * 0.4)} className="hitpad" />
                  {p.mtSignificantFdr10 && <circle cx={x} cy={y} r={selected ? 9 : 6.5} className="fdr-ring" />}
                  {!c.has('z_suite') && zDots.map((zv, k) => zv == null ? null :
                    <circle key={k} cx={x} cy={zY(zv)} r={1.6} fill={Z_DOT_COLORS[k]} opacity={0.8} />)}
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

          {bandOf('pair') && !c.has('pair') && <div className="band-label" style={{ top: bandOf('pair')!.top * graphH + 10 }}><strong>ГЕОМЕТРИЯ ПАР</strong><span>кривая — медиана z (окно 2–6) · заливка — коридор нормы q50–q90 · сплошной adjacent · пунктир baseline · квадрат rolling · кольцо FDR10 · ▲ одиночный скачок · полоса сверху persistence</span></div>}
          {bandOf('raw_geom') && !c.has('raw_geom') && <div className="band-label" style={{ top: bandOf('raw_geom')!.top * graphH + 10 }}><strong>ГЕОМЕТРИЯ RAW</strong><span><i className="chip raw-rmse" />RMSE · <i className="chip raw-median" />Median · <i className="chip raw-p95" />P95 · <i className="chip raw-ptr" />PtPlane-RMSE · <i className="chip raw-ptm" />PtPlane-Median · <i className="chip raw-ptp" />PtPlane-P95 · заливка — калибровочный коридор RMSE (median–p95) · точки — статус RMSE: <i className="chip raw-ok" />шум <i className="chip raw-elev" />повышен <i className="chip raw-unc" />неуверенно</span></div>}
          {bandOf('support') && (!c.has('support') || !c.has('support_ext')) && <div className="band-label" style={{ top: bandOf('support')!.top * graphH + 10 }}><strong>ПОДДЕРЖКА ПАР</strong><span><i className="chip svis" />видимость{!c.has('support_ext') && <> · <i className="chip svert" />вершины · <i className="chip sanch" />якоря</>}</span></div>}
          {bandOf('applicability') && (!c.has('applicability') || !c.has('expression')) && <div className="band-label" style={{ top: bandOf('applicability')!.top * graphH + 10 }}><strong>ПРИМЕНИМОСТЬ</strong><span><i className="chip align" />alignment · <i className="chip res" />residual{!c.has('expression') && <> · <i className="chip expr" />экспрессия <i className="chip jawc" />челюсть <i className="chip cornerc" />уголки</>}</span></div>}
          {bandOf('quality') && (!c.has('quality') || !c.has('quality_ext')) && <div className="band-label" style={{ top: bandOf('quality')!.top * graphH + 10 }}><strong>КАЧЕСТВО</strong><span><i className="chip sharp" />резкость <i className="chip noise" />шум <i className="chip skinq" />кожа <i className="chip skinauth" />аутентичность{!c.has('quality_ext') && <> · <i className="chip aniso" />анизотропия <i className="chip hard" />hard area</>}</span></div>}
          {!c.has('z_suite') && geoB && <div className="band-label hint" style={{ top: geoB.bottom - 34 }}><span>Шесть robust-z на пару — подпись: RMSE/Median/P95/PtPlane-RMSE/PtPlane-Median/PtPlane-P95</span></div>}
        </section>

        {/* V10: фото-ряд — кластеры (calendar) или кадры/стеки (order) */}
        <section className="lane photo-lane" style={{ top: photoTop, height: photoH }}>
          {items.map(v => (
            <button key={v.frame.id} data-hit
              className={`ph ${v.frame.id === selectedId ? 'sel' : ''} ${v.stackCount ? 'cl' : ''} ${(v.groupFrames ?? [v.frame]).some(f => endpoints.has(f.id)) ? 'ep' : ''}`}
              style={{ left: v.x - v.w / 2, width: v.w, height: photoH - 8, background: getPoseColor(v.frame.poseBin) }}
              onClick={() => v.stackCount ? setExpandedStack(expandedStack === v.frame.id ? null : v.frame.id) : onSelect(v.frame.id)}
              onMouseEnter={() => setHoverFrame(v.frame)} onMouseLeave={() => setHoverFrame(null)}
              aria-label={`Фото ${v.frame.date}${v.stackCount ? `, кластер из ${v.stackCount} кадров — Enter раскрывает` : ''}`}>
              <img src={`/storage/stage1/${v.frame.id}/thumb.jpg`} alt="" loading="lazy" draggable={false}
                onError={e => { const t = e.target as HTMLImageElement; t.style.display = 'none'; t.parentElement?.classList.add('noimg') }} />
              {v.stackCount && <span className="stack-cnt">{v.stackCount}</span>}
            </button>
          ))}
        </section>

        {/* V10: контекст-полосы остальных ракурсов (корроборация взглядом) */}
        {!c.has('pose_lanes') && ctxLanes.length > 0 && (
          <section className="lane ctx-lanes" style={{ top: ctxTop, height: ctxH }}>
            {ctxLanes.map((lp, laneIdx) => (
              <div key={lp.bin} className="ctx-lane" style={{ top: laneIdx * 16, height: 14 }}>
                <span className="ctx-label" style={{ color: getPoseColor(lp.bin) }}>{SHORT_POSE[lp.bin] ?? lp.label}</span>
                {lp.xs.map((x, k) => {
                  const fid = lp.frames[k].id
                  const cand = contextCandidates?.get(lp.bin)?.has(fid)
                  return <button key={fid} data-hit className={`ctx-dot ${cand ? 'cand' : ''} ${fid === selectedId ? 'sel' : ''}`}
                    style={{ left: x - 3 }}
                    onClick={() => onContextPoseClick?.(lp.bin, fid)}
                    title={`${lp.frames[k].date} · ${lp.label}${cand ? ' · ◆ кандидат' : ''}`}
                    aria-label={`${lp.frames[k].date} · ${lp.label}`} />
                })}
              </div>
            ))}
          </section>
        )}

        {/* V10: раскрытый кластер/стек — плавающая панель (координаты canvas) */}
        {expandedGroup?.groupFrames && (
          <div className="stack-fan" style={{ left: Math.max(8, expandedGroup.x - (expandedGroup.groupFrames.length * (thumbW + 8)) / 2), top: photoTop + photoH + 2 }}>
            {expandedGroup.groupFrames.map(f => (
              <button key={f.id} data-hit className={`ph ${f.id === selectedId ? 'sel' : ''}`} style={{ width: thumbW, height: photoH - 8, position: 'relative', background: getPoseColor(f.poseBin) }}
                onClick={() => { onSelect(f.id); setExpandedStack(null) }} aria-label={`Кадр ${f.date} из кластера`}>
                <img src={`/storage/stage1/${f.id}/thumb.jpg`} alt="" loading="lazy" draggable={false}
                  onError={e => { const t = e.target as HTMLImageElement; t.style.display = 'none'; t.parentElement?.classList.add('noimg') }} />
              </button>
            ))}
            <button className="stack-close" data-hit onClick={() => setExpandedStack(null)} aria-label="Свернуть кластер">×</button>
          </div>
        )}

        <section className="lane mini-lane" style={{ top: roleTop, height: roleH }}>
          <span className="mini-label">РОЛЬ</span>
          {items.map(v => {
            const role = roleOf(v)
            if (!role) return null
            return <span key={v.frame.id} className={`mini role ${(v.groupFrames ?? [v.frame]).some(f => endpoints.has(f.id)) ? 'ep' : ''}`}
              style={{ left: v.x - iconSize / 2, width: iconSize, height: iconSize, fontSize: Math.max(7, iconSize * 0.42) }}>{role}</span>
          })}
        </section>

        <section className="lane mini-lane" style={{ top: evTop, height: evH }}>
          <span className="mini-label">СОБЫТИЯ</span>
          {!c.has('events') && items.map(v => {
            const framesToScan = v.groupFrames ?? [v.frame]
            const evPairs = framesToScan.flatMap(f => byFrame.get(f.id) ?? []).filter(p => CAND_KINDS.has(classifyPair(p).kind))
            const p = evPairs.length ? pickDisplayPair(evPairs, 'evidence') : undefined
            if (!p) return null
            const cl = classifyPair(p)
            const extra = evPairs.length - 1
            return <button key={v.frame.id} data-hit className={`mini ev ${cl.kind}`}
              style={{ left: v.x - iconSize / 2, width: iconSize, height: iconSize, fontSize: Math.max(7, iconSize * 0.5) }}
              onClick={() => choosePair(p)}
              title={`${cl.label}: ${p.dateA} → ${p.dateB} | z ${p.meshMaxRobustZ?.toFixed(1) ?? '—'}${extra > 0 ? ` · ещё ${extra} пар(ы)` : ''}`}
              aria-label={`${cl.label}, ${p.dateA} → ${p.dateB}`}>
              {cl.symbol}{extra > 0 && <sup className="cnt">+{extra}</sup>}
            </button>
          })}
        </section>

        <section className="lane mini-lane qc" style={{ top: qcTop, height: qcH }}>
          <span className="mini-label">QC</span>
          {!c.has('events') && items.map(v => {
            const ev = eventsOf(v)
            if (!ev.length) return null
            const extra = ev.length - 1
            return <button key={v.frame.id} data-hit className={`mini ev ${ev[0].kind}`}
              style={{ left: v.x - iconSize / 2, width: iconSize, height: iconSize, fontSize: Math.max(6, iconSize * 0.42) }}
              title={ev.map(e => e.label).join(' · ')}
              aria-label={ev.map(e => e.label).join(', ')}>
              {ev[0].symbol}{extra > 0 && <sup className="cnt">+{extra}</sup>}
            </button>
          })}
        </section>

        {/* V10: линейка — годы + возрасты + события + заметки */}
        <section className="lane ruler" style={{ top: rulerTop, height: rulerH }}>
          <svg width={contentW} height={rulerH}>
            {slot >= 110 && frames.map((f, i) => f.date.slice(0, 7) !== frames[i - 1]?.date.slice(0, 7) ? <line key={f.id} x1={centerX(i)} y1={rulerH - 14} x2={centerX(i)} y2={rulerH - 2} className="tk mo" /> : null)}
            {frames.map((f, i) => f.year !== frames[i - 1]?.year ? (
              <g key={f.id}><line x1={centerX(i)} y1={rulerH - 24} x2={centerX(i)} y2={rulerH - 2} className="tk yr" />
                <text x={centerX(i) + 4} y={rulerH - 10} className="tk-label">{f.year}</text></g>
            ) : null)}
            {!c.has('ruler_events') && RULER_EVENTS.map(ev => (
              <g key={ev.label}>
                <line x1={xForDate(ev.date)} y1={2} x2={xForDate(ev.date)} y2={rulerH - 2} className="ruler-event" />
                <text x={xForDate(ev.date) + 3} y={10} className="ruler-event-label">{ev.label}</text>
              </g>
            ))}
            {!c.has('ruler_events') && RULER_AGES.map(ag => (
              <g key={ag.label}>
                <line x1={xForDate(ag.date)} y1={2} x2={xForDate(ag.date)} y2={rulerH - 2} className="ruler-age" />
                <text x={xForDate(ag.date) + 3} y={21} className="ruler-age-label">{ag.label}</text>
              </g>
            ))}
          </svg>
          {!c.has('annotations') && (annotations ?? []).map(a => (
            <button key={a.id} data-hit className="anno-flag" style={{ left: xForDate(a.date) - 5, background: a.color }}
              onClick={() => onAnnotationClick?.(a)}
              title={`Заметка (${a.date}): ${a.text} — клик для удаления`}
              aria-label={`Заметка ${a.date}: ${a.text}`} />
          ))}
        </section>
      </div>

      <svg className="minimap" height={MINI_H} role="navigation" aria-label="Миникарта: плотность кадров, кластеры кандидатов, окно просмотра"
        onPointerDown={e => { jumpTo(e.clientX, e.currentTarget); e.currentTarget.setPointerCapture(e.pointerId) }}
        onPointerMove={e => { if (e.buttons === 1) jumpTo(e.clientX, e.currentTarget) }}>
        {minimap.bins.map((n, k) => n === 0 ? null :
          <rect key={k} x={`${k / minimap.bins.length * 100}%`} y={MINI_H - 4 - (n / minimap.maxBin) * (MINI_H - 12)} width={`${100 / minimap.bins.length}%`} height={(n / minimap.maxBin) * (MINI_H - 12)} className="mm-bin" />)}
        {minimap.clusters.map((cf, k) => (
          <rect key={k} data-hit className="mm-book" x={`${cf * 100}%`} y={MINI_H - 13} width={8} height={11} rx={2}
            onClick={e => { e.stopPropagation(); setScroll(Math.max(0, Math.min(maxScrollRef.current, cf * contentW - size.width / 2))) }}>
            <title>Кластер кандидатов — перейти</title>
          </rect>))}
        <rect className="mm-view" x={`${scroll / contentW * 100}%`} y={1} width={`${Math.min(100, size.width / contentW * 100)}%`} height={MINI_H - 2} />
      </svg>

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
