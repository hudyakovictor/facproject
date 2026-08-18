import { useEffect, useMemo, useState } from 'react'
import type { PairConnection, PoseBin, ZoneMetric } from './types'
import { classifyPair, zoneLabel } from './timeline-data-contract'
import { SectionShell, MiniBars } from './SectionShell'
import type { SectionKey } from './section-meta'
import type { DecisionEntry, DecisionValue } from './App'

/* V12: ПРОВЕРКА КАНДИДАТОВ 2.0.
 * Что нового против V9:
 * 1. Двухколоночная вёрстка: список-очередь слева (с иконками решений),
 *    карточка кандидата справа — контекст очереди виден всегда.
 * 2. Фильтры: ракурс, статус решения (все/нерешённые/принятые/отклонённые/
 *    нужны данные), период.
 * 3. Прогресс-бар решений + мини-гистограмма решений по годам.
 * 4. Клампинг индекса при фильтрации (в V9 индекс уходил за границы списка).
 * 5. Кнопки: в атлас, сравнить A/B, экспорт журнала.
 * Лексика: «Принять к отчёту / Отклонить как артефакт / Нужны данные» — вердикт-слова запрещены. */
function score(p: PairConnection): number {
  const cls = classifyPair(p).kind
  return (cls === 'persistent' ? 400 : cls === 'candidate' ? 300 : 0)
    + (p.mtSignificantFdr10 ? 100 : 0)
    + (p.meshVisibleFraction ?? 0) * 50
    + Math.min(50, p.meshMaxRobustZ ?? 0)
}
const POSES: (PoseBin | 'all')[] = ['all', 'frontal', 'left_light', 'right_light', 'left_mid', 'right_mid', 'left_deep', 'right_deep', 'left_profile', 'right_profile']
type DecFilter = 'all' | 'undecided' | 'accepted' | 'rejected' | 'more_data'

export function Casework({ pairs, zones, decisions, onDecision, initialPairId, onClose, onNavigate, onCompare }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>
  decisions: Record<string, DecisionEntry>; onDecision: (pairId: string, d: DecisionValue | null, rationale?: string) => void
  initialPairId: string | null; onClose: () => void; onNavigate?: (k: SectionKey) => void; onCompare?: (p: PairConnection) => void
}) {
  const [pose, setPose] = useState<'all' | PoseBin>('all')
  const [decFilter, setDecFilter] = useState<DecFilter>('all')
  const [fromY, setFromY] = useState(1998)
  const [toY, setToY] = useState(2027)

  const base = useMemo(() => pairs.filter(p => p.mtSignificantFdr10), [pairs])
  const queue = useMemo(() => base.filter(p => {
    if (pose !== 'all' && p.poseBin !== pose) return false
    const y = Number(p.dateB.slice(0, 4))
    if (y < fromY || y > toY) return false
    const d = decisions[p.pairId]?.decision
    if (decFilter === 'undecided' && d) return false
    if (decFilter !== 'all' && decFilter !== 'undecided' && d !== decFilter) return false
    return true
  }).sort((a, b) => score(b) - score(a)), [base, pose, decFilter, fromY, toY, decisions])

  const [index, setIndex] = useState(() => {
    const i = queue.findIndex(p => p.pairId === initialPairId)
    return i >= 0 ? i : 0
  })
  /* V12-fix: при фильтрации индекс не должен выходить за границы */
  useEffect(() => { setIndex(i => Math.max(0, Math.min(queue.length - 1, i))) }, [queue.length])
  const current = queue[index] ?? null
  const pairZones = useMemo(() => (current ? zones.get(current.pairId) ?? [] : []).filter(z => z.status === 'measured' && z.rmse != null), [zones, current])
  const topZones = useMemo(() => [...pairZones].sort((a, b) => (b.rmse ?? 0) - (a.rmse ?? 0)).slice(0, 5), [pairZones])

  const stats = useMemo(() => {
    const byYear = new Map<number, { done: number; total: number }>()
    for (const p of base) {
      const y = Number(p.dateB.slice(0, 4))
      const c = byYear.get(y) ?? { done: 0, total: 0 }
      c.total++
      if (decisions[p.pairId]?.decision) c.done++
      byYear.set(y, c)
    }
    const years = [...byYear.keys()].sort((a, b) => a - b)
    const counts = { total: base.length, done: Object.values(decisions).filter(d => d.decision).length,
      accepted: Object.values(decisions).filter(d => d.decision === 'accepted').length,
      rejected: Object.values(decisions).filter(d => d.decision === 'rejected').length,
      more: Object.values(decisions).filter(d => d.decision === 'more_data').length }
    return { byYear, years, counts }
  }, [base, decisions])

  const exportLog = () => {
    const log = { exportedAt: new Date().toISOString(), queueSize: base.length, decisions }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify(log, null, 2)], { type: 'application/json' }))
    a.download = 'deeputin_casework_log.json'
    a.click()
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'ArrowLeft') setIndex(i => Math.max(0, i - 1))
      if (e.key === 'ArrowRight') setIndex(i => Math.min(queue.length - 1, i + 1))
      if (!current) return
      if (e.key === '1') onDecision(current.pairId, 'accepted')
      if (e.key === '2') onDecision(current.pairId, 'rejected')
      if (e.key === '3') onDecision(current.pairId, 'more_data')
      if (e.key === '0') onDecision(current.pairId, null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [queue.length, current, onDecision])

  const pctDone = stats.counts.total ? Math.round(stats.counts.done / stats.counts.total * 100) : 0

  return (
    <SectionShell title="Проверка кандидатов" current="casework" onNavigate={onNavigate} onClose={onClose}
      scope={`все ракурсы · ${base.length} FDR-кандидатов · в фильтре ${queue.length}`}
      help={<>Очередь = все пары, прошедшие <b>FDR10</b> (q ≤ 0.10), всех ракурсов. Сортировка: статус → FDR → видимость → z. Клавиши: <b>←/→</b> — навигация, <b>1</b> — принять к отчёту, <b>2</b> — отклонить как артефакт, <b>3</b> — нужны данные, <b>0</b> — сброс. Кандидат — не вердикт.</>}
      filters={<div className="sec-filters-row">
        <select value={pose} onChange={e => setPose(e.target.value as PoseBin | 'all')} aria-label="Ракурс">
          {POSES.map(ps => <option key={ps} value={ps}>{ps === 'all' ? 'Все ракурсы' : ps}</option>)}
        </select>
        <select value={decFilter} onChange={e => setDecFilter(e.target.value as DecFilter)} aria-label="Статус решения">
          <option value="all">Все статусы</option>
          <option value="undecided">Нерешённые</option>
          <option value="accepted">К отчёту</option>
          <option value="rejected">Отклонённые</option>
          <option value="more_data">Нужны данные</option>
        </select>
        <label>с <input type="number" min={1998} max={2027} value={fromY} onChange={e => setFromY(Number(e.target.value))} aria-label="Год с" /></label>
        <label>по <input type="number" min={1998} max={2027} value={toY} onChange={e => setToY(Number(e.target.value))} aria-label="Год по" /></label>
      </div>}
      footer={<div className="cw-foot">
        <div className="cw-progress" role="progressbar" aria-valuenow={pctDone} aria-valuemin={0} aria-valuemax={100}>
          <span>Решено {stats.counts.done}/{stats.counts.total} ({pctDone}%)</span>
          <div className="cw-progress-bar"><div style={{ width: `${pctDone}%` }} /></div>
        </div>
        <span className="cw-counts">к отчёту {stats.counts.accepted} · артефакт {stats.counts.rejected} · нужны данные {stats.counts.more}</span>
        <button onClick={exportLog}>Экспорт журнала</button>
      </div>}>
      <div className="cw2">
        <div className="cw2-left">
          <div className="sec-card cw2-stats">
            <h4>Решения по годам <small>(заполненность — доля решённых)</small></h4>
            <MiniBars data={stats.years.map(y => ({ label: String(y).slice(2), value: stats.byYear.get(y)?.total ?? 0 }))} />
          </div>
          <div className="sec-card cw2-list-wrap">
            <h4>Очередь ({queue.length})</h4>
            <div className="cw2-list">
              {queue.map((p, i) => {
                const d = decisions[p.pairId]?.decision
                return <button key={p.pairId} data-hit className={`cw2-item ${i === index ? 'active' : ''}`} onClick={() => setIndex(i)}>
                  <span className="cw2-idx">{i + 1}</span>
                  <span className="cw2-d">{p.dateA}→{p.dateB}</span>
                  <span className="cw2-p">{p.poseBin}</span>
                  <span className="cw2-z">z {p.meshMaxRobustZ?.toFixed(1) ?? '—'}</span>
                  <span className={`cw2-dec ${d ?? 'none'}`}>{d === 'accepted' ? '✓' : d === 'rejected' ? '✗' : d === 'more_data' ? '?' : ''}</span>
                </button>
              })}
              {queue.length === 0 && <p className="sec-note">Нет кандидатов под фильтрами.</p>}
            </div>
          </div>
        </div>

        <div className="cw2-right">
          {!current && <div className="sec-card"><p className="sec-note">Выберите кандидата.</p></div>}
          {current && (() => {
            const cls = classifyPair(current)
            const dec = decisions[current.pairId]?.decision ?? null
            const exprMismatch = current.smileDetectedA !== current.smileDetectedB || current.jawOpenDetectedA !== current.jawOpenDetectedB
            return <div className="sec-card cw2-card">
              <div className="cw2-statusline"><strong>{cls.label}</strong><span>{current.pairType} · {current.poseBin} · {index + 1}/{queue.length}</span></div>
              <div className="cw2-ab">
                {(['A', 'B'] as const).map(side => {
                  const photo = side === 'A' ? current.photoA : current.photoB
                  const date = side === 'A' ? current.dateA : current.dateB
                  const smile = side === 'A' ? current.smileDetectedA : current.smileDetectedB
                  const jaw = side === 'A' ? current.jawOpenDetectedA : current.jawOpenDetectedB
                  const align = side === 'A' ? current.alignmentQualityA : current.alignmentQualityB
                  return <div key={side} className="cw2-side">
                    <strong>{side} · {date}</strong>
                    <img src={`/storage/stage1/${photo}/thumb.jpg`} alt={`Кадр ${side} (${date})`}
                      onError={e => { const t = e.currentTarget; if (t.src.includes('thumb') && t.src.includes('face_crop')) t.src = t.src.replace('face_crop', 'thumb'); else t.style.visibility = 'hidden' }} />
                    <span className="cw2-meta">align {align?.toFixed(2) ?? '—'} · улыбка {smile ? '✓' : '—'} · челюсть {jaw ? '✓' : '—'}</span>
                  </div>
                })}
              </div>
              <div className="cw2-deltas">
                <span>z max <b>{current.meshMaxRobustZ?.toFixed(2) ?? '—'}</b></span>
                <span>q <b>{current.mtQValue?.toFixed(6) ?? '—'}</b></span>
                <span>видимость <b>{current.meshVisibleFraction != null ? Math.round(current.meshVisibleFraction * 100) + '%' : '—'}</b></span>
                <span>мимика <b>{exprMismatch ? '⚠ различается' : 'совпадает'}</b></span>
                <span>калибровка <b>{current.meshCalibratedStatus || '—'}</b></span>
              </div>
              <div className="cw2-zones">
                <h4>Топ-зоны (raw rmse)</h4>
                {topZones.length === 0 && <p className="sec-note">Зональных измерений нет (зоны есть у 63 из 305 пар).</p>}
                {topZones.map(z => (
                  <div key={z.zone} className="cw2-zone-row"><span>{zoneLabel(z.zone)}</span><span>RMSE {z.rmse?.toFixed(4)}</span><span>P95 {z.p95?.toFixed(4) ?? '—'}</span><span>n={z.pointCount ?? '—'}</span></div>
                ))}
              </div>
              <div className="cw2-actions" role="group" aria-label="Решение по кандидату">
                <button className={`cw2-btn ${dec === 'accepted' ? 'active ok' : ''}`} onClick={() => onDecision(current.pairId, 'accepted')}>✓ К отчёту (1)</button>
                <button className={`cw2-btn ${dec === 'rejected' ? 'active no' : ''}`} onClick={() => onDecision(current.pairId, 'rejected')}>✗ Артефакт (2)</button>
                <button className={`cw2-btn ${dec === 'more_data' ? 'active more' : ''}`} onClick={() => onDecision(current.pairId, 'more_data')}>? Данные (3)</button>
                <button className="cw2-btn" onClick={() => onDecision(current.pairId, null)}>Сброс (0)</button>
                {onNavigate && <button className="cw2-btn" onClick={() => onNavigate('atlas')}>В атлас</button>}
                {onCompare && <button className="cw2-btn" onClick={() => onCompare(current)}>Сравнить A/B</button>}
              </div>
            </div>
          })()}
        </div>
      </div>
    </SectionShell>
  )
}
