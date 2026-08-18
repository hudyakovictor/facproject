import { useCallback, useEffect, useMemo, useState } from 'react'
import { Timeline } from './Timeline'
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
import type { Frame, PairConnection, PhotoMetrics, PoseBin, ZoneMetric } from './types'
import { POSE_CONFIGS } from './types'
import './App.css'
import { validatePairs, validateZones, validateFrames, checkContractVersion, classifyPair, DATA_CONTRACT_VERSION } from './timeline-data-contract'

/* APP V9 — интеграционный каркас (фаза 1 плана до 95+).
 * Что и почему:
 * 1. ЕДИНЫЙ ИСТОЧНИК ДАННЫХ: 4 файла грузятся здесь один раз; разделы получают
 *    props. В V8-dev ZoneAtlas/Casework/Calibration делали повторные fetch —
 *    риск рассинхрона и лишний трафик.
 * 2. SECTION MANAGER: один activeSection вместо шести boolean — оверлеи не
 *    накладываются, Esc закрывает раздел, view= попадает в URL.
 * 3. DEEP-LINKS: выбранная пара передаётся в разделы; из popup — кнопки
 *    «В атласе»/«В очереди»; из ячеек матрицы — переход в таймлайн.
 * 4. РЕШЕНИЯ ПОДНЯТЫ В APP: Casework и Report читают один live-state
 *    (в V8-dev Report читал localStorage через useMemo([]) — устаревал).
 * 5. Аудит-log решений: {decision, ts, rationale?, contractVersion} —
 *    для расследования нужен журнал «когда и в какой версии данных».
 */
export type DecisionValue = 'accepted' | 'rejected' | 'more_data'
export interface DecisionEntry { decision: DecisionValue; ts: string; rationale?: string; contractVersion: string }
export type SectionKey = 'atlas' | 'calibration' | 'casework' | 'matrix' | 'report' | 'integrity' | 'abcompare' | 'persistence'

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

const LAYERS: [string, string, boolean][] = [
  ['pair', 'Геометрия пар', true],
  ['pair_families', '· baseline + rolling семейства', true],
  ['z_suite', '· пять robust-z на пару', false],
  ['zones', '· зоны эффекта (глиф 3×3)', false],
  ['support', 'Поддержка пар (видимость)', true],
  ['support_ext', '· вершины + якоря', false],
  ['applicability', 'Применимость (alignment)', true],
  ['expression', '· экспрессия (magnitude/jaw/corner)', false],
  ['quality', 'Качество (резкость/шум/кожа)', true],
  ['quality_ext', '· анизотропия + hard area', false],
  ['events', 'События и QC-иконки', true],
]
const SECTIONS: [SectionKey, string][] = [
    ['atlas', 'Зональный атлас'], ['casework', 'Проверка кандидатов'], ['matrix', 'Корроборация'],
    ['calibration', 'Калибровка'], ['report', 'Отчёт'], ['integrity', 'Целостность данных'],
    ['persistence', 'Persistence'],
  ]
const num = (v: string | null) => { const n = Number(v); return Number.isFinite(n) ? n : undefined }

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
  const [decisions, setDecisions] = useState<Record<string, DecisionEntry>>(() => {
    try { return JSON.parse(localStorage.getItem('deeputin_casework_v2') || '{}') } catch { return {} }
  })
  const [initialView] = useState(() => {
    const p = new URLSearchParams(location.hash.slice(1))
    return { slot: num(p.get('slot')), scroll: num(p.get('scroll')) }
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

  // Deep-link в таймлайн из любого раздела: pose + кадр, раздел закрывается.
  const navigateToTimeline = useCallback((p: PoseBin, frameId?: string) => {
    setActiveSection(null)
    setPose(p)
    setSelectedId(frameId ?? frames.find(f => f.poseBin === p)?.id ?? null)
  }, [frames])
  const openSection = useCallback((s: SectionKey | null) => { setActiveSection(s); setSectionsOpen(false) }, [])

  // URL: replaceState — история не засоряется (V8); +view раздела (V9).
  const viewRef = useCallback((slot: number, scroll: number) => {
    const p = new URLSearchParams()
    if (pose !== 'frontal') p.set('pose', pose)
    if (selectedId) p.set('id', selectedId)
    if (selectedPairId) p.set('pair', selectedPairId)
    if (collapsed.size) p.set('hide', [...collapsed].join(','))
    if (activeSection) p.set('view', activeSection)
    p.set('slot', String(Math.round(slot)))
    p.set('scroll', String(scroll))
    history.replaceState(null, '', `#${p.toString()}`)
  }, [pose, selectedId, selectedPairId, collapsed, activeSection])

  // Клавиатура: Esc закрывает СНАЧАЛА раздел, потом popup/detail (V8-dev разделы игнорировал).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'Escape') {
        if (activeSection) { setActiveSection(null); return }
        setPairPopup(null); setDetail(false); setSelectedPairId(null); return
      }
      if (activeSection) return
      if (e.key.toLowerCase() === 'c') { setCandOnly(v => !v); return }
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
  }, [pp, cands, candOnly, pf, selectedId, selectedPairId, activeSection])

  const popupNav = useMemo(() => {
    if (!pairPopup) return undefined
    const list = candOnly ? cands : pp
    const i = list.findIndex(p => p.pairId === pairPopup.pairId)
    if (i < 0) return undefined
    return {
      pos: i + 1, total: list.length,
      onPrev: () => { const n = list[(i - 1 + list.length) % list.length]; setPairPopup(n); setSelectedPairId(n.pairId) },
      onNext: () => { const n = list[(i + 1) % list.length]; setPairPopup(n); setSelectedPairId(n.pairId) },
    }
  }, [pairPopup, pp, cands, candOnly])

  if (loading) return <div className="state-screen">Загрузка…</div>
  if (error) return <div className="state-screen error">{error}</div>

  return <div className="forensic-shell">
    <header className="toolbar">
      <div className="brand">DEEPUTIN</div>
      <label className="pose-picker"><select value={pose} onChange={e => change(e.target.value as PoseBin)} aria-label="Выбор ракурса">{POSE_CONFIGS.map((p, i) => <option key={p.bin} value={p.bin}>{i + 1}. {p.label}</option>)}</select></label>
      <div className="filter-wrap">
        <button className="tab" onClick={() => { setFilterOpen(v => !v); setSectionsOpen(false) }} aria-expanded={filterOpen}>Данные ▾</button>
        {filterOpen && <div className="filter-drop" role="group" aria-label="Слои данных">
          {LAYERS.map(([k, label]) => <label key={k} className={label.startsWith('·') ? 'sub' : ''}><input type="checkbox" checked={!collapsed.has(k)} onChange={() => toggleCollapsed(k)} />{label.replace(/^· /, '')}</label>)}
        </div>}
      </div>
      {/* V9: разделы собраны в dropdown — toolbar не переполняется */}
      <div className="filter-wrap">
        <button className={`tab ${activeSection ? 'active' : ''}`} onClick={() => { setSectionsOpen(v => !v); setFilterOpen(false) }} aria-expanded={sectionsOpen}>Разделы ▾</button>
        {sectionsOpen && <div className="filter-drop" role="menu" aria-label="Разделы">
          {SECTIONS.map(([k, label]) => <button key={k} className="drop-item" role="menuitem" onClick={() => openSection(k)}>{label}</button>)}
        </div>}
      </div>
      <span className="ctx">{pf.length} кадров · {pp.length} пар · <strong className="cand-n">◆ {cands.length}</strong> (FDR {fdrCount})</span>
      {sparse && <span className="sparse-warn" title={`В этом ракурсе всего ${pp.length} пар на ${pf.length} кадров`}>мало пар — база слабая</span>}
      <button className={`tab ${candOnly ? 'active' : ''}`} onClick={() => setCandOnly(v => !v)} title="Клавиша C">◆ только кандидаты</button>
      <div className="toolbar-spacer" />
      <span className="safety">КАНДИДАТЫ · НЕ ВЕРДИКТ</span>
      <span className="keys">←/→ кадр · [/] пара · C кандидаты · Enter детали · Esc закрыть</span>
    </header>
    <main className="timeline-wrap">
      <Timeline frames={pf} pairs={pp} photoMetrics={metrics} zones={zones} selectedId={selectedId} selectedPairId={selectedPairId}
        onSelect={setSelectedId} onPairClick={setPairPopup} onPairSelect={setSelectedPairId} collapsed={collapsed}
        initialSlot={initialView.slot} initialScroll={initialView.scroll} onViewChange={viewRef} />
    </main>
    <FrameDetail frame={selected} metrics={selected ? metrics.get(selected.id) : undefined} visible={detail} onClose={() => setDetail(false)} />
    <PairPopup pair={pairPopup} visible={!!pairPopup} nav={popupNav} frames={frames} photoMetrics={metrics} zones={pairPopup ? zones.get(pairPopup.pairId) : undefined}
      onOpenSection={s => { setPairPopup(null); openSection(s) }}
      onClose={() => { setPairPopup(null); setSelectedPairId(null) }} />
    {/* V9: разделы — один активный; все получают данные через props (fetch нигде в разделах) */}
    {activeSection === 'atlas' && <ZoneAtlas pairs={pairs} zones={zones} selectedPairId={selectedPairId} onSelectPair={setSelectedPairId} onClose={() => openSection(null)} />}
    {activeSection === 'casework' && <Casework pairs={pairs} zones={zones} decisions={decisions} onDecision={setDecision} initialPairId={selectedPairId} onClose={() => openSection(null)} />}
    {activeSection === 'matrix' && <MatrixView pairs={pairs} frames={frames} onNavigate={navigateToTimeline} onClose={() => openSection(null)} />}
    {activeSection === 'calibration' && <Calibration pairs={pairs} zones={zones} onClose={() => openSection(null)} />}
    {activeSection === 'report' && <Report pairs={pairs} zones={zones} decisions={decisions} onClose={() => openSection(null)} />}
    {activeSection === 'integrity' && <DataIntegrity frames={frames} pairs={pairs} zones={zones} onNavigate={navigateToTimeline} onClose={() => openSection(null)} />}
    {activeSection === 'abcompare' && pairPopup && <ABCompare pair={pairPopup} zones={zones.get(pairPopup.pairId) ?? []} onClose={() => openSection(null)} />}
    <SessionJournal pairs={pairs} selectedPairId={selectedPairId} activeSection={activeSection} />
  </div>
}
