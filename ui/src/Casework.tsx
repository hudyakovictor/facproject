import { useEffect, useMemo, useState } from 'react'
import type { PairConnection, ZoneMetric } from './types'
import { classifyPair, zoneLabel } from './timeline-data-contract'
import type { DecisionEntry, DecisionValue } from './App'

/* Casework V9 — очередь проверки кандидатов (фаза 3 плана). Исправления:
 * 1. ГЛОБАЛЬНАЯ очередь: все FDR-significant пары ВСЕХ ракурсов (в V8-dev
 *    была только текущая поза — часть кандидатов недоступна).
 * 2. Лексика: «Принять к отчёту / Отклонить как артефакт / Нужны данные» —
 *    кандидат не «подтверждается» (вердикт-слова запрещены инвариантом).
 * 3. Сортировка evidence-score: status > FDR > поддержка(visibility) > z —
 *    не z alone (большой z при слабой поддержке не должен всплывать).
 * 4. Решения — из props (App), живые; журнал с ts/rationale/contractVersion.
 * 5. RU-подписи зон, onError у изображений, клавиатура ←/→ и 1/2/3.
 */
function score(p: PairConnection): number {
  const cls = classifyPair(p).kind
  return (cls === 'persistent' ? 400 : cls === 'candidate' ? 300 : 0)
    + (p.mtSignificantFdr10 ? 100 : 0)
    + (p.meshVisibleFraction ?? 0) * 50
    + Math.min(50, p.meshMaxRobustZ ?? 0)
}

export function Casework({ pairs, zones, decisions, onDecision, initialPairId, onClose }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>
  decisions: Record<string, DecisionEntry>; onDecision: (pairId: string, d: DecisionValue | null, rationale?: string) => void
  initialPairId: string | null; onClose: () => void
}) {
  const queue = useMemo(() => pairs.filter(p => p.mtSignificantFdr10).sort((a, b) => score(b) - score(a)), [pairs])
  const [index, setIndex] = useState(() => Math.max(0, queue.findIndex(p => p.pairId === initialPairId)))
  const current = queue[index]
  const pairZones = useMemo(() => (current ? zones.get(current.pairId) ?? [] : []).filter(z => z.status === 'measured' && z.rmse != null), [zones, current])
  const topZones = useMemo(() => [...pairZones].sort((a, b) => (b.rmse ?? 0) - (a.rmse ?? 0)).slice(0, 5), [pairZones])
  const decided = Object.values(decisions).filter(d => d).length

  // Клавиатура: ←/→ навигация, 1/2/3 решение, 0 сброс.
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

  const exportLog = () => {
    const log = { exportedAt: new Date().toISOString(), queueSize: queue.length, decisions }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([JSON.stringify(log, null, 2)], { type: 'application/json' }))
    a.download = 'deeputin_casework_log.json'
    a.click()
  }

  if (!queue.length) return <div className="section-overlay"><div className="sec-empty">Нет FDR-значимых кандидатов</div></div>
  if (!current) return null
  const cls = classifyPair(current)
  const dec = decisions[current.pairId]?.decision ?? null

  return (
    <div className="section-overlay" role="dialog" aria-modal="true" aria-label="Проверка кандидатов">
      <header className="sec-header">
        <h2>Проверка кандидатов</h2>
        <span className="sec-scope">все ракурсы · {index + 1} / {queue.length} · решено {decided}</span>
        <div className="cw-nav">
          <button disabled={index <= 0} onClick={() => setIndex(i => i - 1)}>← Назад</button>
          <button disabled={index >= queue.length - 1} onClick={() => setIndex(i => i + 1)}>Вперёд →</button>
          <button onClick={exportLog}>Экспорт журнала</button>
          <button onClick={onClose} aria-label="Закрыть">×</button>
        </div>
      </header>
      <div className="sec-body cw-body">
        <div className="cw-card">
          <div className="cw-statusline"><strong>{cls.label}</strong><span>{current.pairType} · {current.poseBin}</span></div>
          <div className="cw-ab">
            {(['A', 'B'] as const).map(side => {
              const photo = side === 'A' ? current.photoA : current.photoB
              const date = side === 'A' ? current.dateA : current.dateB
              const smile = side === 'A' ? current.smileDetectedA : current.smileDetectedB
              const jaw = side === 'A' ? current.jawOpenDetectedA : current.jawOpenDetectedB
              const align = side === 'A' ? current.alignmentQualityA : current.alignmentQualityB
              return <div key={side} className="cw-side">
                <strong>{side} · {date}</strong>
                <img src={`/storage/stage1/${photo}/thumb.jpg`} alt={`Кадр ${side} (${date})`}
                  onError={e => { const t = e.target as HTMLImageElement; t.style.visibility = 'hidden' }} />
                <span className="cw-meta">align {align?.toFixed(2) ?? '—'} · улыбка {smile ? '✓' : '—'} · челюсть {jaw ? '✓' : '—'}</span>
              </div>
            })}
          </div>
          <div className="cw-deltas">
            <span>z max {current.meshMaxRobustZ?.toFixed(2) ?? '—'}</span>
            <span>q {current.mtQValue?.toFixed(6) ?? '—'}</span>
            <span>видимость {current.meshVisibleFraction != null ? (current.meshVisibleFraction * 100).toFixed(0) + '%' : '—'}</span>
            <span>мимика {current.smileDetectedA !== current.smileDetectedB || current.jawOpenDetectedA !== current.jawOpenDetectedB ? '⚠ различается' : 'совпадает'}</span>
          </div>
          <div className="cw-zones">
            <h4>Топ-зоны (raw rmse; z зон некалиброван)</h4>
            {topZones.length === 0 && <p className="sec-note">Зональных измерений нет (зоны есть у 63 из 305 пар).</p>}
            {topZones.map(z => (
              <div key={z.zone} className="cw-zone-row">
                <span className="cw-zone-name">{zoneLabel(z.zone)}</span>
                <span>RMSE {z.rmse?.toFixed(4)}</span>
                <span>P95 {z.p95?.toFixed(4) ?? '—'}</span>
                <span>n={z.pointCount ?? '—'}</span>
              </div>
            ))}
          </div>
          <div className="cw-actions" role="group" aria-label="Решение по кандидату">
            <button className={`cw-btn ${dec === 'accepted' ? 'active ok' : ''}`} onClick={() => onDecision(current.pairId, 'accepted')}>✓ Принять к отчёту (1)</button>
            <button className={`cw-btn ${dec === 'rejected' ? 'active no' : ''}`} onClick={() => onDecision(current.pairId, 'rejected')}>✗ Отклонить как артефакт (2)</button>
            <button className={`cw-btn ${dec === 'more_data' ? 'active more' : ''}`} onClick={() => onDecision(current.pairId, 'more_data')}>? Нужны данные (3)</button>
            <button className="cw-btn" onClick={() => onDecision(current.pairId, null)}>Сбросить (0)</button>
          </div>
          <div className="cw-summary">
            Решено {decided}/{queue.length} · к отчёту {Object.values(decisions).filter(d => d.decision === 'accepted').length} · отклонено {Object.values(decisions).filter(d => d.decision === 'rejected').length} · нужны данные {Object.values(decisions).filter(d => d.decision === 'more_data').length}
          </div>
        </div>
      </div>
    </div>
  )
}
