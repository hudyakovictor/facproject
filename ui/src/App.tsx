import { useCallback, useEffect, useMemo, useState } from 'react'
import { Timeline } from './Timeline'
import { TimelineMap } from './TimelineMap'
import { FrameDetail } from './FrameDetail'
import { PairPopup } from './PairOverlay'
import { ZoneAtlas } from './ZoneAtlas'
import { Calibration } from './Calibration'
import { Casework } from './Casework'
import { MatrixView } from './MatrixView'
import { Report } from './Report'
import { DataIntegrity } from './DataIntegrity'
import { SessionJournal } from './SessionJournal'
import { ABCompare } from './ABCompare'
import { PersistenceAnalysis } from './PersistenceAnalysis'
import { MorphPanel } from './MorphPanel'
import { KeyPointsLab } from './KeyPointsLab'
import { MetricProfiles } from './MetricProfiles'
import type { Frame, PairConnection, PhotoMetrics, PoseBin, TimelineAnnotation, ZoneMetric } from './types'
import { POSE_CONFIGS } from './types'
import './App.css'
import { validatePairs, validateZones, validateFrames, checkContractVersion, classifyPair, DATA_CONTRACT_VERSION } from './timeline-data-contract'

/* APP V10 — редизайн таймлайна (docs/TIMELINE_REDESIGN_VISION.md):
 * 1. Пресеты слоёв «Геометрия / Текстура / Контекст» (радио-режим вместо 14 чекбоксов).
 * 2. Стратегическая карта (L0) — TimelineMap вместо ленты по кнопке «Карта».
 * 3. Честная ось времени — переключатель «Время/Кадры» (axisMode).
 * 4. Режим «Обход кандидатов» — playhead по FDR-парам всех ракурсов, 1/2/3 решения.
 * 5. Заметки журналиста на датах (localStorage + флажки на линейке).
 * 6. Контекст-полосы ракурсов (contextPoses) — корроборация взглядом.
 * 7. Снимок вида — HTML-экспорт текущего состояния для рабочего блокнота.
 */
export type DecisionValue = 'accepted' | 'rejected' | 'more_data'
export interface DecisionEntry { decision: DecisionValue; ts: string; rationale?: string; contractVersion: string }
import type { SectionKey as SectionKeyMeta } from './section-meta'
/** Локальный ключ раздела: общие разделы + abcompare (полноэкранный оверлей) */
export type SectionKey = SectionKeyMeta | 'abcompare'

function csvLine(line: string) { const out: string[] = []; let v = '', q = false; for (let i = 0; i < line.length; i++) { const ch = line[i]; if (ch === '"') { if (q && line[i + 1] === '"') { v += '"'; i++ } else q = !q } else if (ch === ',' && !q) { out.push(v); v = '' } else v += ch } out.push(v); return out }
function parseCsv(raw: string): Frame[] {
  const ls = raw.trim().split(/\r?\n/).filter(Boolean), h = csvLine(ls[0] ?? '')
  const num = (v?: string) => { if (!v?.trim()) return null; const n = Number(v); return Number.isFinite(n) ? n : null }
  return ls.slice(1).map(line => {
    const c = csvLine(line), r: Record<string, string> = {}; h.forEach((k, i) => r[k] = c[i] ?? '')
    const n = (k: string) => num(r[k]) ?? 0, d = r.date ?? ''
    return { id: r.photo_id ?? '', date: d, sameDateSequence: n('same_date_sequence'), timestamp: Date.parse(`${d}T00:00:00Z`), year: Number(d.slice(0, 4)), poseBin: (r.pose_bin || 'frontal') as PoseBin, pitch: n('pitch'), yaw: n('yaw'), roll: n('roll'), sourceFilename: r.source_filename ?? '', sourceRelativePath: r.source_relative_path ?? '', dateProvenanceStatus: r.date_provenance_status || 'unknown', exifDate: r.exif_date ?? '', dateDeltaDays: num(r.date_delta_days), sourceClaimedDate: r.source_claimed_date ?? '', sourceClaimedDeltaDays: num(r.source_claimed_delta_days), dateConflictSources: r.date_conflict_sources ?? '', sourceProvenanceStatus: r.source_provenance_status || 'not_provided', perceptualDhash: r.perceptual_dhash ?? '', nearDuplicateOf: r.near_duplicate_of ?? '', geometryStatus: (r.geometry_status || 'unknown') as Frame['geometryStatus'], segmentationStatus: (r.segmentation_status || 'unknown') as Frame['segmentationStatus'], uvStatus: (r.uv_status || 'unknown') as Frame['uvStatus'], combinedVisibleFraction: n('combined_visible_fraction'), skinMaskCoverage: n('skin_mask_coverage'), uvObservedCoverage: n('uv_observed_coverage'), chronologyGlobal: n('chronology_index_global'), chronologyInPose: n('chronology_index_in_pose') } satisfies Frame
  }).sort((a, b) => a.timestamp - b.timestamp || a.sameDateSequence - b.sameDateSequence)
}

/* V10: дефолт — «сигнал + контекст»: пара/события/линейка/полосы/заметки.
   Остальное (качество, поддержка, применимость, z-suite, зоны) — по требованию. */
const LAYERS: [string, string, boolean][] = [
  ['pair', 'Геометрия пар', true],
  ['raw_geom', 'Геометрия raw + калибровка', true],
  ['pair_families', '· baseline + rolling семейства', true],
  ['z_suite', '· пять robust-z на пару', false],
  ['zones', '· зоны эффекта (глиф 3×3)', false],
  ['support', 'Поддержка пар (видимость)', false],
  ['support_ext', '· вершины + якоря', false],
  ['applicability', 'Применимость (alignment)', false],
  ['expression', '· экспрессия (magnitude/jaw/corner)', false],
  ['quality', 'Качество (резкость/шум/кожа)', false],
  ['quality_ext', '· анизотропия + hard area', false],
  ['events', 'События и QC-иконки', true],
  ['ruler_events', 'Линейка: возрасты и события', true],
  ['pose_lanes', 'Контекст-полосы ракурсов', true],
  ['annotations', 'Заметки на линейке', true],
]
/* V10: пресеты радио-режима слоя */
const PRESETS: Record<'geometry' | 'texture' | 'context', string[]> = {
  geometry: ['pair', 'raw_geom', 'pair_families', 'events', 'ruler_events', 'pose_lanes', 'annotations'],
  texture: ['quality', 'quality_ext', 'events', 'ruler_events', 'pose_lanes', 'annotations'],
  context: ['applicability', 'expression', 'support', 'support_ext', 'events', 'ruler_events', 'pose_lanes', 'annotations'],
}
const SECTIONS: [SectionKey, string][] = [
    ['atlas', 'Зональный атлас'], ['casework', 'Проверка кандидатов'], ['matrix', 'Корроборация'],
    ['keypoints', 'Ключевые точки'], ['calibration', 'Калибровка'], ['persistence', 'Persistence'],
    ['metrics', 'Метрики пар'], ['report', 'Отчёт'], ['integrity', 'Целостность данных'],
  ]
const num = (v: string | null) => { const n = Number(v); return Number.isFinite(n) ? n : undefined }
const esc = (s: unknown) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const CAND_KINDS = new Set(['candidate', 'persistent'])
const ANNOT_KEY = 'deeputin_annotations_v1'

export default function App() {
  const [frames, setFrames] = useState<Frame[]>([]), [pairs, setPairs] = useState<PairConnection[]>([]), [metrics, setMetrics] = useState(new Map<string, PhotoMetrics>())
  const [zones, setZones] = useState(new Map<string, ZoneMetric[]>())
  const [pose, setPose] = useState<PoseBin>('frontal'), [selectedId, setSelectedId] = useState<string | null>(null), [selectedPairId, setSelectedPairId] = useState<string | null>(null)
  const [detail, setDetail] = useState(false), [pairPopup, setPairPopup] = useState<PairConnection | null>(null)
  const [loading, setLoading] = useState(true), [error, setError] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState(() => new Set(LAYERS.filter(l => !l[2]).map(l => l[0])))
  const [filterOpen, setFilterOpen] = useState(false), [sectionsOpen, setSectionsOpen] = useState(false)
  const [candOnly, setCandOnly] = useState(false)
  const [activeSection, setActiveSection] = useState<SectionKey | null>(null)
  const [abPair, setAbPair] = useState<PairConnection | null>(null)
  /* V13: панель морфинга — большой горизонтальный попап поверх всего */
  const [morphPair, setMorphPair] = useState<PairConnection | null>(null)
  /* V10: режимы редизайна */
  const [initialView] = useState(() => {
    const p = new URLSearchParams(location.hash.slice(1))
    return { slot: num(p.get('slot')), scroll: num(p.get('scroll')) }
  })
  const [axisMode, setAxisMode] = useState<'calendar' | 'order'>(() => {
    const p = new URLSearchParams(location.hash.slice(1))
    return p.get('axis') === 'order' ? 'order' : 'calendar'
  })
  const [mapMode, setMapMode] = useState(false)
  const [walkIndex, setWalkIndex] = useState(-1)
  const [annotations, setAnnotations] = useState<TimelineAnnotation[]>(() => {
    try { const raw = localStorage.getItem(ANNOT_KEY); return raw ? JSON.parse(raw) : [] } catch { return [] }
  })
  const [decisions, setDecisions] = useState<Record<string, DecisionEntry>>(() => {
    try { return JSON.parse(localStorage.getItem('deeputin_casework_v2') || '{}') } catch { return {} }
  })
  const toggleCollapsed = (k: string) => setCollapsed(v => { const n = new Set(v); if (n.has(k)) n.delete(k); else n.add(k); return n })
  const setDecision = useCallback((pairId: string, decision: DecisionValue | null, rationale?: string) => {
    setDecisions(prev => {
      const next = { ...prev }
      if (decision == null) delete next[pairId]
      else next[pairId] = { decision, ts: new Date().toISOString(), rationale, contractVersion: DATA_CONTRACT_VERSION }
      localStorage.setItem('deeputin_casework_v2', JSON.stringify(next))
      return next
    })
  }, [])

  useEffect(() => { try { localStorage.setItem(ANNOT_KEY, JSON.stringify(annotations)) } catch { /* noop */ } }, [annotations])

  useEffect(() => {
    const p = new URLSearchParams(location.hash.slice(1))
    const pp0 = p.get('pose') as PoseBin | null; if (pp0 && POSE_CONFIGS.some(x => x.bin === pp0)) setPose(pp0)
    const id = p.get('id'); if (id) setSelectedId(id)
    const pr = p.get('pair'); if (pr) setSelectedPairId(pr)
    const hide = p.get('hide'); if (hide) setCollapsed(new Set(hide.split(',')))
    const view = p.get('view') as SectionKey | null; if (view && SECTIONS.some(s => s[0] === view)) setActiveSection(view)
    const get = (name: string) => fetch(`/data/${name}`).then(r => { if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`); return r })
    Promise.all([
      get('main_timeline.csv').then(r => r.text()),
      get('pair_metrics.json').then(r => r.json()),
      get('photo_metrics.json').then(r => r.json()),
      fetch('/data/zone_metrics.json').then(r => r.ok ? r.json() : []).catch(() => []),
    ]).then(([csv, pr2, mr, zr]) => {
      checkContractVersion(mr, 'photo_metrics'); checkContractVersion(pr2, 'pair_metrics')
      const f = validateFrames(parseCsv(csv)), m = new Map<string, PhotoMetrics>(), zm = new Map<string, ZoneMetric[]>()
      if (Array.isArray(mr)) mr.forEach((x: PhotoMetrics) => { if (x?.id) m.set(x.id, x) })
      for (const z of validateZones(zr)) { const a = zm.get(z.pairId) ?? []; a.push(z); zm.set(z.pairId, a) }
      checkContractVersion(zr, 'zone_metrics')
      setFrames(f); setPairs(validatePairs(pr2)); setMetrics(m); setZones(zm)
      if (!location.hash.includes('id=')) setSelectedId(f.find(x => x.poseBin === pose)?.id ?? null)
      setLoading(false)
    }).catch(e => { setError(`Загрузка данных не удалась: ${String(e)}`); setLoading(false) })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps — загрузка один раз при монтировании

  const pf = useMemo(() => frames.filter(f => f.poseBin === pose), [frames, pose])
  const ids = useMemo(() => new Set(pf.map(f => f.id)), [pf])
  const pp = useMemo(() => pairs.filter(p => p.poseBin === pose && ids.has(p.photoA) && ids.has(p.photoB)).sort((a, b) => a.dateB.localeCompare(b.dateB)), [pairs, pose, ids])
  const cands = useMemo(() => pp.filter(p => { const k = classifyPair(p).kind; return k === 'candidate' || k === 'persistent' }), [pp])
  const fdrCount = useMemo(() => pp.filter(p => p.mtSignificantFdr10).length, [pp])
  const sparse = pf.length > 0 && pp.length / pf.length < 0.10
  const selected = frames.find(f => f.id === selectedId) ?? null
  const change = useCallback((p: PoseBin) => { setPose(p); setSelectedPairId(null); setPairPopup(null); setSelectedId(frames.find(f => f.poseBin === p)?.id ?? null) }, [frames])

  /* V10: контекст-полосы остальных ракурсов + кандидаты в них */
  const allByPose = useMemo(() => {
    const m = new Map<PoseBin, Frame[]>()
    for (const f of frames) { const a = m.get(f.poseBin) ?? []; a.push(f); m.set(f.poseBin, a) }
    return m
  }, [frames])
  const contextPoses = useMemo(() => POSE_CONFIGS
    .filter(pc => pc.bin !== pose)
    .map(pc => ({ bin: pc.bin, label: pc.label, frames: allByPose.get(pc.bin) ?? [] }))
    .filter(x => x.frames.length > 0), [pose, allByPose])
  const contextCandidates = useMemo(() => {
    const m = new Map<string, Set<string>>()
    for (const p of pairs) {
      if (!CAND_KINDS.has(classifyPair(p).kind)) continue
      const set = m.get(p.poseBin) ?? new Set<string>()
      set.add(p.photoA); set.add(p.photoB)
      m.set(p.poseBin, set)
    }
    return m
  }, [pairs])

  /* V10: очередь обхода — все FDR-пары всех ракурсов по хронологии */
  const walkQueue = useMemo(() => pairs.filter(p => p.mtSignificantFdr10).sort((a, b) => a.dateB.localeCompare(b.dateB)), [pairs])
  const gotoWalk = useCallback((i: number) => {
    const q = walkQueue
    if (!q.length) return
    const idx = ((i % q.length) + q.length) % q.length
    const p = q[idx]
    setWalkIndex(idx); setMapMode(false); setActiveSection(null)
    setPose(p.poseBin as PoseBin)
    setSelectedPairId(p.pairId); setSelectedId(p.photoB); setPairPopup(p)
  }, [walkQueue])
  const exitWalk = useCallback(() => { setWalkIndex(-1); setPairPopup(null); setSelectedPairId(null) }, [])

  /* V10: заметки */
  const addAnnotation = useCallback((date: string, text: string) => {
    setAnnotations(prev => [...prev, { id: `a${Date.now()}${Math.floor(Math.random() * 1e4)}`, date, text, color: '#eac26b' }])
  }, [])
  const removeAnnotation = useCallback((a: TimelineAnnotation) => {
    setAnnotations(prev => prev.filter(x => x.id !== a.id))
  }, [])

  /* V10: снимок вида — HTML-экспорт текущего состояния */
  const snapshotView = useCallback(() => {
    const now = new Date().toISOString()
    const rows = pf.map(f => {
      const m = metrics.get(f.id)
      const pairZs = pp.filter(p => p.photoA === f.id || p.photoB === f.id).map(p => p.meshMaxRobustZ ?? null).filter((z): z is number => z != null)
      return `<tr><td>${esc(f.date)}</td><td>${esc(f.poseBin)}</td><td>${f.yaw.toFixed(1)}°/${f.pitch.toFixed(1)}°</td><td>${(f.combinedVisibleFraction * 100).toFixed(0)}%</td><td>${m?.skinAuthenticityScore?.toFixed(2) ?? '—'}</td><td>${pairZs.length ? Math.max(...pairZs).toFixed(1) : '—'}</td></tr>`
    }).join('')
    const pairRows = pp.map(p => `<tr><td>${esc(p.dateA)} → ${esc(p.dateB)}</td><td>${esc(p.pairType)}</td><td>${p.meshMaxRobustZ?.toFixed(1) ?? '—'}</td><td>${p.mtQValue?.toFixed(3) ?? '—'}</td><td>${p.mtSignificantFdr10 ? 'FDR10' : ''}</td><td>${esc(classifyPair(p).label)}</td></tr>`).join('')
    const annoRows = annotations.map(a => `<li>${esc(a.date)}: ${esc(a.text)}</li>`).join('')
    const html = `<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>DEEPUTIN — снимок вида</title><style>body{font:12px/1.5 sans-serif;color:#222;max-width:1100px;margin:20px auto;padding:20px}h1{font-size:18px;border-bottom:2px solid #333;padding-bottom:8px}table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border:1px solid #ccc;padding:3px 6px;font-size:11px}.wm{position:fixed;right:12px;top:12px;color:#b00;border:2px solid #b00;padding:6px 10px;font-weight:700;transform:rotate(3deg)}</style></head><body><div class="wm">КАНДИДАТЫ — НЕ ВЕРДИКТ</div><h1>DEEPUTIN — снимок вида</h1><p>Сгенерировано ${esc(now)} · ракурс ${esc(pose)} · ось ${axisMode} · кадров ${pf.length} · пар ${pp.length} · кандидатов ${cands.length} · FDR ${fdrCount} · контракт ${esc(DATA_CONTRACT_VERSION)}</p><h3>Заметки</h3>${annoRows || '<p>—</p>'}<h3>Кадры (${pf.length})</h3><table><thead><tr><th>Дата</th><th>Ракурс</th><th>Yaw/Pitch</th><th>Видимость</th><th>Кожа z</th><th>Max z пар</th></tr></thead><tbody>${rows}</tbody></table><h3>Пары (${pp.length})</h3><table><thead><tr><th>Пара</th><th>Тип</th><th>z</th><th>q</th><th>FDR</th><th>Статус</th></tr></thead><tbody>${pairRows}</tbody></table></body></html>`
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    a.download = `deeputin_view_${now.slice(0, 10)}.html`
    a.click()
  }, [pf, pp, metrics, cands, fdrCount, pose, axisMode, annotations])

  const applyPreset = (key: 'geometry' | 'texture' | 'context') => {
    setCollapsed(new Set(LAYERS.map(l => l[0]).filter(id => !PRESETS[key].includes(id))))
  }
  const presetActive = (key: 'geometry' | 'texture' | 'context') => PRESETS[key].every(id => !collapsed.has(id))

  const navigateToTimeline = useCallback((p: PoseBin, frameId?: string) => {
    setActiveSection(null)
    setPose(p)
    setSelectedId(frameId ?? frames.find(f => f.poseBin === p)?.id ?? null)
  }, [frames])
  const openSection = useCallback((s: SectionKey | null) => { setActiveSection(s); setSectionsOpen(false) }, [])

  const viewRef = useCallback((slot: number, scroll: number) => {
    const p = new URLSearchParams()
    if (pose !== 'frontal') p.set('pose', pose)
    if (selectedId) p.set('id', selectedId)
    if (selectedPairId) p.set('pair', selectedPairId)
    if (collapsed.size) p.set('hide', [...collapsed].join(','))
    if (activeSection) p.set('view', activeSection)
    if (axisMode !== 'calendar') p.set('axis', axisMode)
    p.set('slot', String(Math.round(slot)))
    p.set('scroll', String(scroll))
    history.replaceState(null, '', `#${p.toString()}`)
  }, [pose, selectedId, selectedPairId, collapsed, activeSection, axisMode])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return
      /* V10: режим обхода кандидатов перехватывает клавиши */
      if (walkIndex >= 0) {
        if (e.key === 'Escape') { exitWalk(); return }
        if (!walkQueue.length) return
        if (e.key === 'ArrowRight') { gotoWalk(walkIndex + 1); return }
        if (e.key === 'ArrowLeft') { gotoWalk(walkIndex - 1); return }
        if (e.key === '1') { setDecision(walkQueue[walkIndex].pairId, 'accepted'); return }
        if (e.key === '2') { setDecision(walkQueue[walkIndex].pairId, 'rejected'); return }
        if (e.key === '3') { setDecision(walkQueue[walkIndex].pairId, 'more_data'); return }
        return
      }
      if (e.key === 'Escape') {
        if (morphPair) { setMorphPair(null); return }
        if (activeSection) { setActiveSection(null); setAbPair(null); return }
        if (mapMode) { setMapMode(false); return }
        setPairPopup(null); setDetail(false); setSelectedPairId(null); return
      }
      if (activeSection) return
      if (e.key.toLowerCase() === 'c') { setCandOnly(v => !v); return }
      if (e.key === 'Enter' && (e.target as HTMLElement).tagName === 'BUTTON') return
      if (e.key === 'Enter') {
        const sp = pp.find(p => p.pairId === selectedPairId)
        if (sp) setPairPopup(sp); else if (selectedId) setDetail(true)
        return
      }
      if (e.key === '[' || e.key === ']') {
        const list = candOnly ? cands : pp
        if (!list.length) return
        const cur = list.findIndex(p => p.pairId === selectedPairId)
        const next = list[(cur + (e.key === ']' ? 1 : list.length - 1) + list.length) % list.length]
        setSelectedPairId(next.pairId); setSelectedId(next.photoB)
        return
      }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        if (!pf.length) return
        const cur = Math.max(0, pf.findIndex(f => f.id === selectedId))
        setSelectedId(pf[Math.max(0, Math.min(pf.length - 1, cur + (e.key === 'ArrowRight' ? 1 : -1)))].id)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pp, cands, candOnly, pf, selectedId, selectedPairId, activeSection, walkIndex, walkQueue, gotoWalk, exitWalk, setDecision, mapMode, morphPair])

  const popupNav = useMemo(() => {
    if (!pairPopup) return undefined
    const list = walkIndex >= 0 ? walkQueue : (candOnly ? cands : pp)
    const i = list.findIndex(p => p.pairId === pairPopup.pairId)
    if (i < 0) return undefined
    return {
      pos: i + 1, total: list.length,
      onPrev: () => {
        const n = list[(i - 1 + list.length) % list.length]
        if (walkIndex >= 0) gotoWalk(i - 1)
        else { setPairPopup(n); setSelectedPairId(n.pairId) }
      },
      onNext: () => {
        const n = list[(i + 1) % list.length]
        if (walkIndex >= 0) gotoWalk(i + 1)
        else { setPairPopup(n); setSelectedPairId(n.pairId) }
      },
    }
  }, [pairPopup, pp, cands, candOnly, walkIndex, walkQueue, gotoWalk])

  if (loading) return <div className="state-screen">Загрузка…</div>
  if (error) return <div className="state-screen error">{error}</div>

  return <div className="forensic-shell">
    <header className="toolbar">
      <div className="brand">DEEPUTIN</div>
      <label className="pose-picker"><select value={pose} onChange={e => change(e.target.value as PoseBin)} aria-label="Выбор ракурса">{POSE_CONFIGS.map((p, i) => <option key={p.bin} value={p.bin}>{i + 1}. {p.label}</option>)}</select></label>
      <button className={`tab ${axisMode === 'calendar' ? 'active' : ''}`} onClick={() => setAxisMode(v => v === 'calendar' ? 'order' : 'calendar')} title="Честная календарная ось (пробелы видны) или порядок кадров (равные интервалы)">Ось: {axisMode === 'calendar' ? 'время' : 'кадры'}</button>
      <button className={`tab ${mapMode ? 'active' : ''}`} onClick={() => { setMapMode(v => !v); setSectionsOpen(false); setFilterOpen(false) }} title="Стратегическая карта: весь архив × 9 ракурсов">Карта</button>
      <div className="filter-wrap">
        <button className="tab" onClick={() => { setFilterOpen(v => !v); setSectionsOpen(false) }} aria-expanded={filterOpen}>Данные ▾</button>
        {filterOpen && <div className="filter-drop" role="group" aria-label="Слои данных">
          <div className="preset-row" role="radiogroup" aria-label="Режим слоя">
            {(['geometry', 'texture', 'context'] as const).map(k => (
              <button key={k} className={`preset-btn ${presetActive(k) ? 'active' : ''}`} onClick={() => applyPreset(k)}>
                {k === 'geometry' ? 'Геометрия' : k === 'texture' ? 'Текстура' : 'Контекст'}
              </button>
            ))}
          </div>
          <div className="preset-sep" />
          {LAYERS.map(([k, label]) => <label key={k} className={label.startsWith('·') ? 'sub' : ''}><input type="checkbox" checked={!collapsed.has(k)} onChange={() => toggleCollapsed(k)} />{label.replace(/^· /, '')}</label>)}
        </div>}
      </div>
      <div className="filter-wrap">
        <button className={`tab ${activeSection ? 'active' : ''}`} onClick={() => { setSectionsOpen(v => !v); setFilterOpen(false) }} aria-expanded={sectionsOpen}>Разделы ▾</button>
        {sectionsOpen && <div className="filter-drop" role="menu" aria-label="Разделы">
          {SECTIONS.map(([k, label]) => <button key={k} className="drop-item" role="menuitem" onClick={() => openSection(k)}>{label}</button>)}
        </div>}
      </div>
      <span className="ctx">{pf.length} кадров · {pp.length} пар · <strong className="cand-n">◆ {cands.length}</strong> (FDR {fdrCount})</span>
      {sparse && <span className="sparse-warn" title={`В этом ракурсе всего ${pp.length} пар на ${pf.length} кадров`}>мало пар — база слабая</span>}
      {walkIndex >= 0 && (
        <span className="walk-chip" title="Режим обхода FDR-кандидатов: ←/→ — следующий, 1/2/3 — решение, Esc — выход">
          Обход {walkIndex + 1}/{walkQueue.length} · 1=к отчёту 2=артефакт 3=данные
          <button className="walk-exit" onClick={exitWalk} aria-label="Выйти из обхода">×</button>
        </span>
      )}
      <button className={`tab ${walkIndex >= 0 ? 'active' : ''}`} onClick={() => walkIndex >= 0 ? exitWalk() : gotoWalk(0)} title="Playhead по всем FDR-кандидатам всех ракурсов; решения клавишами 1/2/3">Обход{walkQueue.length ? ` ${walkQueue.length}` : ''}</button>
      <button className="tab" onClick={snapshotView} title="Экспорт снимка текущего вида (HTML, для рабочего блокнота)">Снимок</button>
      <button className={`tab ${candOnly ? 'active' : ''}`} onClick={() => setCandOnly(v => !v)} title="Клавиша C">◆ только кандидаты</button>
      <div className="toolbar-spacer" />
      <span className="safety">КАНДИДАТЫ · НЕ ВЕРДИКТ</span>
      <span className="keys">←/→ кадр · [/] пара · C · Enter · 1-3 обход · Esc</span>
    </header>
    <main className="timeline-wrap">
      {mapMode
        ? <TimelineMap frames={frames} pairs={pairs} activePose={pose}
            onPick={(bin, year) => { const fid = frames.find(f => f.poseBin === bin && f.year === year)?.id; setMapMode(false); navigateToTimeline(bin, fid) }} />
        : <Timeline frames={pf} pairs={pp} photoMetrics={metrics} zones={zones} selectedId={selectedId} selectedPairId={selectedPairId}
            onSelect={setSelectedId} onPairClick={setPairPopup} onPairSelect={setSelectedPairId} collapsed={collapsed}
            initialSlot={initialView.slot} initialScroll={initialView.scroll} onViewChange={viewRef}
            axisMode={axisMode}
            contextPoses={contextPoses} contextCandidates={contextCandidates}
            onContextPoseClick={(bin, frameId) => { setPose(bin); setSelectedId(frameId); setSelectedPairId(null) }}
            annotations={annotations} onAnnotationClick={(a) => { if (window.confirm(`Удалить заметку «${a.text}»?`)) removeAnnotation(a) }} />}
    </main>
    <FrameDetail frame={selected} metrics={selected ? metrics.get(selected.id) : undefined} visible={detail} onClose={() => setDetail(false)} />
    <PairPopup pair={pairPopup} visible={!!pairPopup} nav={popupNav} frames={frames} photoMetrics={metrics} zones={pairPopup ? zones.get(pairPopup.pairId) : undefined}
      onAnnotate={addAnnotation}
      onOpenSection={s => {
        if (s === 'morph') { setMorphPair(pairPopup); setPairPopup(null); setActiveSection(null); setSectionsOpen(false) }
        else if (s === 'abcompare') { setAbPair(pairPopup); setPairPopup(null); setActiveSection('abcompare'); setSectionsOpen(false) }
        else { setPairPopup(null); openSection(s) }
      }}
      onClose={() => { setPairPopup(null); setSelectedPairId(null) }} />
    {activeSection === 'atlas' && <ZoneAtlas pairs={pairs} zones={zones} selectedPairId={selectedPairId} onSelectPair={setSelectedPairId} onClose={() => openSection(null)} onNavigate={openSection} />}
    {activeSection === 'casework' && <Casework pairs={pairs} zones={zones} decisions={decisions} onDecision={setDecision} initialPairId={selectedPairId} onClose={() => openSection(null)}
      onNavigate={openSection} onCompare={p => { setAbPair(p); setActiveSection('abcompare') }} />}
    {activeSection === 'matrix' && <MatrixView pairs={pairs} frames={frames} onNavigate={navigateToTimeline} onClose={() => openSection(null)} onNavigateSection={openSection} />}
    {activeSection === 'keypoints' && <KeyPointsLab pairs={pairs} zones={zones} onClose={() => openSection(null)} onNavigate={openSection} />}
    {activeSection === 'calibration' && <Calibration pairs={pairs} zones={zones} onClose={() => openSection(null)} onNavigate={openSection} />}
    {activeSection === 'persistence' && <PersistenceAnalysis pairs={pairs} onClose={() => openSection(null)} onNavigate={openSection} />}
    {/* V13: панель морфинга — поверх всего, закрывается Esc */}
    {morphPair && <MorphPanel pair={morphPair} zones={zones.get(morphPair.pairId) ?? []} onClose={() => setMorphPair(null)} />}
    {activeSection === 'metrics' && <MetricProfiles pairs={pairs} zones={zones} onClose={() => openSection(null)} onNavigate={openSection} />}
    {activeSection === 'report' && <Report pairs={pairs} zones={zones} decisions={decisions} annotations={annotations} onClose={() => openSection(null)} onNavigate={openSection} />}
    {activeSection === 'integrity' && <DataIntegrity frames={frames} pairs={pairs} zones={zones} onNavigate={navigateToTimeline} onClose={() => openSection(null)} onNavigateSection={openSection} />}
    {activeSection === 'abcompare' && abPair && <ABCompare pair={abPair} zones={zones.get(abPair.pairId) ?? []} photoMetrics={metrics} frames={frames} onClose={() => { setAbPair(null); openSection(null) }} />}
    {activeSection === 'persistence' && <PersistenceAnalysis pairs={pairs} onClose={() => openSection(null)} />}
    <SessionJournal pairs={pairs} selectedPairId={selectedPairId} activeSection={activeSection} />
  </div>
}
