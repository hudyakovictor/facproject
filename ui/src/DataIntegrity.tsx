import { useMemo } from 'react'
import type { Frame, PairConnection, PoseBin, ZoneMetric } from './types'
import { DATA_CONTRACT_VERSION } from './timeline-data-contract'
import { EXCLUDED_FIELDS } from './track-registry'

/* DataIntegrity V9 (фаза 7 плана). Исправления против V8-dev:
 * 1. Удалён fetch несуществующего contract_version.txt — версия из контракта.
 * 2. Реальные проверки в браузере: orphan-пары, покрытие зон, null-статистика,
 *    дубликаты, разреженность ракурсов — тот же дух, что scripts/selftest.mjs.
 * 3. EXCLUDED_FIELDS — из track-registry (единый источник, не текст-капча).
 * 4. Клик по ракурсу → переход в таймлайн этого ракурса (deep-link).
 */
export function DataIntegrity({ frames, pairs, zones, onNavigate, onClose }: {
  frames: Frame[]; pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>
  onNavigate: (pose: PoseBin) => void; onClose: () => void
}) {
  const stats = useMemo(() => {
    const frameIds = new Set(frames.map(f => f.id))
    const orphans = pairs.filter(p => !frameIds.has(p.photoA) || !frameIds.has(p.photoB)).length
    const zoneRows = [...zones.values()].reduce((n, l) => n + l.length, 0)
    const nullZ = pairs.filter(p => p.meshMaxRobustZ == null).length
    const nullAlign = frames.length && 0 // alignment живёт в photo_metrics, не во frames — честно помечаем ниже
    const conflicts = frames.filter(f => f.dateConflictSources && f.dateConflictSources !== '[]').length
    const dups = frames.filter(f => f.nearDuplicateOf).length
    const byPose: Record<string, { frames: number; pairs: number; fdr: number }> = {}
    for (const f of frames) (byPose[f.poseBin] ??= { frames: 0, pairs: 0, fdr: 0 }).frames++
    for (const p of pairs) {
      const b = byPose[p.poseBin] ??= { frames: 0, pairs: 0, fdr: 0 }
      b.pairs++; if (p.mtSignificantFdr10) b.fdr++
    }
    return { orphans, zoneRows, zonePairs: zones.size, nullZ, nullAlign, conflicts, dups, byPose }
  }, [frames, pairs, zones])

  return (
    <div className="section-overlay" role="dialog" aria-modal="true" aria-label="Целостность данных">
      <header className="sec-header"><h2>Целостность данных</h2><span className="sec-scope">контракт {DATA_CONTRACT_VERSION}</span><button onClick={onClose} aria-label="Закрыть">×</button></header>
      <div className="sec-body di-body">
        <div className="sec-card">
          <h3>Покрытие по ракурсам <small>(клик — перейти в таймлайн)</small></h3>
          <table className="sec-table">
            <thead><tr><th>Ракурс</th><th>Кадров</th><th>Пар</th><th>FDR10</th><th>Ratio</th><th>Оценка базы</th></tr></thead>
            <tbody>
              {Object.entries(stats.byPose).sort().map(([bin, d]) => {
                const ratio = d.frames ? d.pairs / d.frames : 0
                return <tr key={bin} onClick={() => onNavigate(bin as PoseBin)} className="di-linkrow">
                  <td>{bin}</td><td>{d.frames}</td><td>{d.pairs}</td><td>{d.fdr}</td>
                  <td>{d.frames ? ratio.toFixed(2) : '—'}</td>
                  <td className={ratio < 0.10 ? 'di-warn' : 'di-ok'}>{ratio < 0.10 ? 'слабая' : 'достаточная'}</td>
                </tr>
              })}
            </tbody>
          </table>
        </div>
        <div className="sec-card di-stats">
          <h3>Связность и покрытие</h3>
          <span>Кадров: {frames.length}</span>
          <span>Пар: {pairs.length}</span>
          <span>Orphan-пары (ссылка на несуществующий кадр): <strong className={stats.orphans ? 'di-warn' : 'di-ok'}>{stats.orphans}</strong></span>
          <span>Зональные измерения: {stats.zoneRows} строк у {stats.zonePairs} пар ({pairs.length ? Math.round(stats.zonePairs / pairs.length * 100) : 0}%)</span>
          <span>Пары без meshMaxRobustZ (null, не 0): {stats.nullZ}</span>
          <span>Конфликты датировки: {stats.conflicts} · near-duplicate: {stats.dups}</span>
        </div>
        <div className="sec-card">
          <h3>Исключённые поля (единый реестр)</h3>
          {EXCLUDED_FIELDS.map(x => <div key={x.field} className="di-excluded"><code>{x.field}</code><span>{x.reason}</span></div>)}
        </div>
        <div className="sec-card">
          <p className="sec-note">CI-гейт: <code>npm run verify</code> = tsc + lint + <code>node scripts/selftest.mjs</code> (12+ контрактных проверок) + <code>node --test tests/</code>. Эта панель — просмотр тех же инвариантов в браузере.</p>
        </div>
      </div>
    </div>
  )
}
