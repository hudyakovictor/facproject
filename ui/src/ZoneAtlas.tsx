import { useMemo, useState } from 'react'
import type { PairConnection, ZoneMetric } from './types'
import { zoneLabel } from './timeline-data-contract'

/* ZoneAtlas V9 — эталон (фаза 2 плана). Исправления против V8-dev:
 * 1. Данные — из props (App), а не повторный fetch (единый источник).
 * 2. Агрегаты фильтруют status='measured' && rmse != null ДО усреднения —
 *    в V8-dev 97 строк insufficient_visibility с rmse=null занижали средние
 *    (null считался нулём — нарушение инварианта «null ≠ 0»).
 * 3. zoneLabel из контракта вместо локального ZONE_LABELS — одна терминология.
 * 4. Picker читаемый: «датаA → датаB · ракурс · ◆», FDR-кандидаты первыми.
 * 5. Явное покрытие: зоны есть у 63 из 305 пар — до анализа, не после.
 * 6. Ячейки «не измерено» визуально отличимы от малых значений.
 * robustZ зон НЕ показываем: некалиброван (см. types.ts).
 */
const ZONE_ORDER = ['x_high_low', 'x_high_center', 'x_high_high', 'x_center_low', 'x_center_center', 'x_center_high', 'x_low_low', 'x_low_center', 'x_low_high']

export function ZoneAtlas({ pairs, zones, selectedPairId, onSelectPair, onClose }: {
  pairs: PairConnection[]; zones: Map<string, ZoneMetric[]>; selectedPairId: string | null
  onSelectPair: (id: string) => void; onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const zonePairIds = useMemo(() => [...zones.keys()], [zones])
  const pairsWithZones = useMemo(() => {
    const set = new Set(zonePairIds)
    const list = pairs.filter(p => set.has(p.pairId))
    return [...list].sort((a, b) => Number(b.mtSignificantFdr10) - Number(a.mtSignificantFdr10) || a.dateB.localeCompare(b.dateB))
  }, [pairs, zonePairIds])
  const filtered = useMemo(() => pairsWithZones.filter(p => !query || (p.dateA + p.dateB + p.poseBin).includes(query)), [pairsWithZones, query])
  const currentId = selectedPairId && zones.has(selectedPairId) ? selectedPairId : filtered[0]?.pairId ?? null
  const pairZones = currentId ? zones.get(currentId) ?? [] : []
  const currentPair = pairs.find(p => p.pairId === currentId) ?? null

  // Агрегат: ТОЛЬКО measured-строки (null-гард); n показывает покрытие честно.
  const aggregates = useMemo(() => {
    const agg: Record<string, { sum: number; n: number; total: number }> = {}
    for (const z of ZONE_ORDER) agg[z] = { sum: 0, n: 0, total: 0 }
    for (const list of zones.values()) for (const z of list) {
      const cell = agg[z.zone]
      if (!cell) continue
      cell.total++
      if (z.status === 'measured' && z.rmse != null) { cell.sum += z.rmse; cell.n++ }
    }
    return agg
  }, [zones])
  const maxAvg = Math.max(0.001, ...ZONE_ORDER.map(z => { const a = aggregates[z]; return a.n ? a.sum / a.n : 0 }))

  return (
    <div className="section-overlay" role="dialog" aria-modal="true" aria-label="Зональный атлас">
      <header className="sec-header"><h2>Зональный атлас</h2><span className="sec-scope">все ракурсы · зоны у {zonePairIds.length} из {pairs.length} пар ({pairs.length ? Math.round(zonePairIds.length / pairs.length * 100) : 0}%)</span><button onClick={onClose} aria-label="Закрыть">×</button></header>
      <div className="sec-body za-body">
        <div className="za-picker">
          <input placeholder="Поиск по дате/ракурсу…" value={query} onChange={e => setQuery(e.target.value)} aria-label="Поиск пары" />
          <select value={currentId ?? ''} onChange={e => onSelectPair(e.target.value)} aria-label="Выбор пары">
            {filtered.map(p => <option key={p.pairId} value={p.pairId}>{p.dateA} → {p.dateB} · {p.poseBin}{p.mtSignificantFdr10 ? ' · ◆ FDR' : ''}</option>)}
          </select>
        </div>
        {currentPair && pairZones.length > 0 && (
          <div className="za-heat">
            <h3>{currentPair.dateA} → {currentPair.dateB} · {currentPair.poseBin} · {currentPair.pairType}</h3>
            <div className="za-3x3">
              {ZONE_ORDER.map(zn => {
                const z = pairZones.find(x => x.zone === zn)
                const measured = z?.status === 'measured' && z.rmse != null
                const maxR = Math.max(0.001, ...pairZones.filter(x => x.status === 'measured' && x.rmse != null).map(x => x.rmse!))
                const intensity = measured ? z.rmse! / maxR : 0
                return (
                  <div key={zn} className={`za-cell ${measured ? '' : 'na'}`} style={{ background: `rgba(94,159,232,${intensity})`, borderColor: z?.mtSignificantFdr10 ? '#de9255' : '#2a3340' }}>
                    <div className="za-cell-label">{zoneLabel(zn)}</div>
                    {measured ? <>
                      <div className="za-cell-val">RMSE {z.rmse!.toFixed(4)}</div>
                      <div className="za-cell-val">P95 {z.p95?.toFixed(4) ?? '—'}</div>
                      <div className="za-cell-val">Δ ({z.signedX?.toFixed(3)}, {z.signedY?.toFixed(3)}, {z.signedZ?.toFixed(3)})</div>
                      <div className="za-cell-val">n={z.pointCount ?? '—'}</div>
                      {z.mtSignificantFdr10 && <div className="za-fdr">FDR10</div>}
                    </> : <div className="za-cell-na">не измерено</div>}
                  </div>
                )
              })}
            </div>
          </div>
        )}
        <div className="za-agg">
          <h3>Средняя RMSE по зонам (только measured)</h3>
          <div className="za-3x3">
            {ZONE_ORDER.map(zn => {
              const a = aggregates[zn]
              const avg = a.n ? a.sum / a.n : null
              return (
                <div key={zn} className="za-cell" style={{ background: `rgba(94,159,232,${avg == null ? 0 : avg / maxAvg})` }}>
                  <div className="za-cell-label">{zoneLabel(zn)}</div>
                  <div className="za-cell-val">RMSE {avg == null ? '—' : avg.toFixed(4)}</div>
                  <div className="za-cell-val">n={a.n}/{a.total}</div>
                </div>
              )
            })}
          </div>
          <p className="sec-note">Показывается raw rmse: zone robustZ в текущем export некалиброван (insufficient_calibration) и не является z-score.</p>
        </div>
      </div>
    </div>
  )
}
